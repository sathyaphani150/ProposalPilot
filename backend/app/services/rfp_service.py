"""
ProposalPilot AI — RFP Service Layer
Business logic for session creation, file storage, and analysis orchestration.
"""
from __future__ import annotations

import os
import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.exceptions import RFPSessionNotFoundError
from app.models import RFPSession, RFPAnalysis
from app.services.document_parser import parse_document
from app.services.leadership_output import sanitize_analysis_payload_for_leadership
from app.services.rfp_engine import analyze_rfp_document

settings = get_settings()
STUCK_ANALYSIS_RECOVERY_SECONDS = 45
DEFAULT_RFP_PAGE_SIZE = 20
_ANALYSIS_TASKS: dict[str, asyncio.Task[None]] = {}


_GENERIC_REGRESSION_TAGS = {
    "mobile",
    "web_portal",
    "integration",
    "data",
    "reporting",
    "workflow",
}


def _analysis_needs_recovery(
    raw_llm_output: dict[str, object] | None,
    missing_information: list[object] | None,
    domain_tags: list[str] | None,
    raw_text: str | None,
) -> bool:
    raw = raw_llm_output or {}
    tags = set(domain_tags or [])
    intelligence = raw.get("rfp_intelligence")
    if not isinstance(intelligence, dict) or not intelligence:
        return True
    if not intelligence.get("sentiment_analysis") or not intelligence.get("must_ask_questions"):
        return True
    if raw_text and len(raw_text) >= 1_000 and not missing_information:
        return True
    if tags and tags <= _GENERIC_REGRESSION_TAGS and not missing_information:
        return True
    return False


async def _recover_analysis_if_needed(db: AsyncSession, analysis: RFPAnalysis, session: RFPSession) -> RFPAnalysis:
    if not session.raw_text or not _analysis_needs_recovery(
        analysis.raw_llm_output,
        analysis.missing_information,
        analysis.domain_tags,
        session.raw_text,
    ):
        return analysis

    logger.info(f"Recovering stale RFP analysis for session {session.id}")
    analysis_data = await analyze_rfp_document(session.raw_text)
    for key, value in analysis_data.items():
        setattr(analysis, key, value)
    session.status = "analyzed"
    await db.flush()
    await db.refresh(analysis)
    return analysis


def _analysis_has_been_stuck(session: RFPSession) -> bool:
    if session.status != "analyzing" or not session.updated_at:
        return False
    updated_at = session.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - updated_at).total_seconds() >= STUCK_ANALYSIS_RECOVERY_SECONDS


async def _run_and_store_analysis(
    db: AsyncSession,
    session: RFPSession,
    *,
    regenerate: bool,
) -> RFPAnalysis | None:
    if not session.raw_text:
        session.status = "analysis_failed"
        await db.flush()
        return None

    logger.info(f"Running direct RFP analysis recovery for session {session.id}")
    analysis_data = await analyze_rfp_document(session.raw_text, regenerate=regenerate)

    existing_result = await db.execute(
        select(RFPAnalysis).where(RFPAnalysis.session_id == session.id)
    )
    for existing in existing_result.scalars().all():
        await db.delete(existing)
    await db.flush()

    analysis = RFPAnalysis(session_id=session.id, **analysis_data)
    db.add(analysis)
    session.status = "analyzed"
    await db.flush()
    await db.refresh(analysis)
    return analysis


def _discard_finished_task(task_key: str, task: asyncio.Task[None]) -> None:
    _ANALYSIS_TASKS.pop(task_key, None)
    try:
        task.result()
    except asyncio.CancelledError:
        logger.warning(f"RFP analysis background task was cancelled for session {task_key}")
    except Exception as exc:
        logger.exception(f"RFP analysis background task failed for session {task_key}: {exc}")


async def _run_analysis_in_background(session_id: str, *, regenerate: bool) -> None:
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(RFPSession).where(RFPSession.id == uuid.UUID(session_id)))
        session = result.scalar_one_or_none()
        if not session:
            logger.warning(f"Skipping background analysis for missing session {session_id}")
            return

        try:
            analysis = await _run_and_store_analysis(db, session, regenerate=regenerate)
            await db.commit()
            if analysis:
                logger.info(f"Completed background RFP analysis for session {session_id}")
            else:
                logger.warning(f"Background RFP analysis produced no result for session {session_id}")
        except Exception as exc:
            await db.rollback()
            logger.exception(f"Background RFP analysis failed for session {session_id}: {exc}")
            failure_result = await db.execute(select(RFPSession).where(RFPSession.id == uuid.UUID(session_id)))
            failure_session = failure_result.scalar_one_or_none()
            if failure_session:
                failure_session.status = "analysis_failed"
                await db.commit()


def _schedule_analysis_task(session_id: uuid.UUID, *, regenerate: bool) -> str:
    task_key = str(session_id)
    existing_task = _ANALYSIS_TASKS.get(task_key)
    if existing_task and not existing_task.done():
        return f"in_process:{task_key}"

    task = asyncio.create_task(_run_analysis_in_background(task_key, regenerate=regenerate))
    _ANALYSIS_TASKS[task_key] = task
    task.add_done_callback(lambda done_task: _discard_finished_task(task_key, done_task))
    return f"in_process:{task_key}"


async def create_rfp_session(
    db: AsyncSession,
    *,
    filename: str,
    content: bytes,
    client_name: str | None,
    title: str,
) -> RFPSession:
    """
    Save the uploaded file, extract text, create and return the RFP session.
    """
    session_id = uuid.uuid4()
    ext = Path(filename).suffix.lower()
    safe_filename = f"{session_id}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    # Persist file to disk
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # Parse text immediately (lightweight, sync under the hood)
    try:
        raw_text = await parse_document(file_path)
    except Exception as e:
        logger.warning(f"Text extraction failed for {filename}: {e} — storing without text")
        raw_text = None

    session = RFPSession(
        id=session_id,
        title=title,
        client_name=client_name,
        status="uploaded",
        original_filename=filename,
        file_path=file_path,
        file_size_bytes=len(content),
        raw_text=raw_text,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    logger.info(f"Created RFP session {session.id} for '{filename}'")
    return session


async def get_session_or_404(db: AsyncSession, session_id: uuid.UUID) -> RFPSession:
    """Fetch session by ID or raise 404."""
    result = await db.execute(
        select(RFPSession).where(RFPSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise RFPSessionNotFoundError(f"Session {session_id} not found.")
    return session


async def list_sessions(
    db: AsyncSession, *, skip: int = 0, limit: int = DEFAULT_RFP_PAGE_SIZE
) -> tuple[list[RFPSession], int, dict[str, int]]:
    """Return paginated sessions ordered by creation date descending."""
    total_result = await db.execute(select(func.count(RFPSession.id)))
    total: int = total_result.scalar_one()

    status_counts_result = await db.execute(
        select(RFPSession.status, func.count(RFPSession.id)).group_by(RFPSession.status)
    )
    status_counts = {
        str(status): int(count)
        for status, count in status_counts_result.all()
    }

    result = await db.execute(
        select(RFPSession)
        .order_by(RFPSession.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    sessions = list(result.scalars().all())
    return sessions, total, status_counts


async def trigger_analysis(db: AsyncSession, session: RFPSession) -> str:
    """
    Start RFP analysis without blocking the upload flow.

    The frontend depends on this endpoint returning quickly so it can poll the
    analysis endpoint. The actual model work runs in-process with its own DB
    session, avoiding stale Celery queues while keeping the API responsive.
    """
    existing_result = await db.execute(
        select(RFPAnalysis).where(RFPAnalysis.session_id == session.id)
    )
    regenerate = bool(existing_result.scalars().first())

    session.status = "analyzing"
    await db.commit()

    task_id = _schedule_analysis_task(session.id, regenerate=regenerate)
    logger.info(f"Scheduled background RFP analysis for session {session.id}")
    return task_id


async def get_analysis(db: AsyncSession, session_id: uuid.UUID) -> dict:
    """Return the structured analysis result for a session."""
    result = await db.execute(
        select(RFPAnalysis)
        .where(RFPAnalysis.session_id == session_id)
        .order_by(RFPAnalysis.created_at.desc())
        .limit(1)
    )
    analysis = result.scalar_one_or_none()
    session = await get_session_or_404(db, session_id)
    if not analysis:
        if _analysis_has_been_stuck(session):
            analysis = await _run_and_store_analysis(db, session, regenerate=True)
            await db.commit()
            if analysis:
                return {
                    "session_id": str(session_id),
                    "status": "analyzed",
                    "analysis": sanitize_analysis_payload_for_leadership(analysis.to_dict()),
                }
        return {
            "session_id": str(session_id),
            "status": session.status,
            "analysis": None,
        }
    if session.status == "analyzing":
        session.status = "analyzed"
        await db.commit()
        await db.refresh(session)
    analysis = await _recover_analysis_if_needed(db, analysis, session)
    return {
        "session_id": str(session_id),
        "status": "analyzed",
        "analysis": sanitize_analysis_payload_for_leadership(analysis.to_dict()),
    }


async def delete_session(db: AsyncSession, session_id: uuid.UUID) -> None:
    """Delete a session and its uploaded file."""
    session = await get_session_or_404(db, session_id)

    # Remove file from disk
    try:
        if session.file_path and Path(session.file_path).exists():
            Path(session.file_path).unlink()
    except Exception as e:
        logger.warning(f"Could not delete file {session.file_path}: {e}")

    await db.delete(session)
    logger.info(f"Deleted RFP session {session_id}")
