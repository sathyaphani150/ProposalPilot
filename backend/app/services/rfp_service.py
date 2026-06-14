"""
ProposalPilot AI — RFP Service Layer
Business logic for session creation, file storage, and analysis orchestration.
"""
from __future__ import annotations

import os
import uuid
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

settings = get_settings()


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
    db: AsyncSession, *, skip: int = 0, limit: int = 20
) -> tuple[list[RFPSession], int]:
    """Return paginated sessions ordered by creation date descending."""
    total_result = await db.execute(select(func.count(RFPSession.id)))
    total: int = total_result.scalar_one()

    result = await db.execute(
        select(RFPSession)
        .order_by(RFPSession.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    sessions = list(result.scalars().all())
    return sessions, total


async def trigger_analysis(db: AsyncSession, session: RFPSession) -> str:
    """
    Update session status to 'analyzing' and dispatch Celery task.
    Returns the Celery task ID.
    """
    session.status = "analyzing"
    await db.flush()

    # Import here to avoid circular dependency
    from app.tasks.ingestion_tasks import analyze_rfp_task
    task = analyze_rfp_task.delay(str(session.id))
    logger.info(f"Dispatched analysis task {task.id} for session {session.id}")
    return task.id


async def get_analysis(db: AsyncSession, session_id: uuid.UUID) -> dict:
    """Return the structured analysis result for a session."""
    result = await db.execute(
        select(RFPAnalysis)
        .where(RFPAnalysis.session_id == session_id)
        .order_by(RFPAnalysis.created_at.desc())
        .limit(1)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        session = await get_session_or_404(db, session_id)
        return {
            "session_id": str(session_id),
            "status": session.status,
            "analysis": None,
        }
    return {
        "session_id": str(session_id),
        "status": "analyzed",
        "analysis": analysis.to_dict(),
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
