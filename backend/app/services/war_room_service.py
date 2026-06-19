"""War room orchestration service."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError, ValidationError
from app.models import (
    RFPAnalysis,
    RFPSession,
    WarRoomMessage,
    WarRoomOutput,
    WarRoomSession,
)
from app.war_room import ProposalState, run_war_room_graph
from app.war_room.context import get_relevant_context


def _ensure_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _ensure_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalize_overrides(overrides: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not overrides:
        return []
    return [{"agent": "human", "override": overrides, "timestamp": datetime.now(timezone.utc).isoformat()}]


async def _load_session_context(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    call_notes: str | None,
    human_overrides: dict[str, Any] | None,
) -> tuple[RFPSession, RFPAnalysis, dict[str, Any]]:
    session_result = await db.execute(select(RFPSession).where(RFPSession.id == session_id))
    session = session_result.scalar_one_or_none()
    if not session:
        raise NotFoundError(f"RFP session {session_id} not found.")

    analysis_result = await db.execute(
        select(RFPAnalysis)
        .where(RFPAnalysis.session_id == session_id)
        .order_by(RFPAnalysis.created_at.desc())
        .limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()
    if not analysis:
        raise ValidationError("Run RFP analysis before starting the War Room.")

    context = await get_relevant_context(
        db,
        session=session,
        analysis=analysis,
        user_overrides=_normalize_overrides(human_overrides),
        call_notes=call_notes,
    )
    return session, analysis, context


def _build_initial_state(
    *,
    session: RFPSession,
    analysis: RFPAnalysis,
    context: dict[str, Any],
    call_notes: str | None,
    human_overrides: dict[str, Any] | None,
) -> ProposalState:
    return ProposalState(
        session_id=str(session.id),
        session_title=session.title,
        client_name=session.client_name,
        call_notes=call_notes or "",
        rfp_analysis=analysis.to_dict(),
        retrieved_context=_ensure_list(context.get("retrieved_context")),
        similar_projects=_ensure_list(context.get("similar_projects")),
        user_overrides=_normalize_overrides(human_overrides),
        discussion_log=[],
        unresolved_conflicts=[],
        final_recommendations={},
        review_loops=0,
        run_id=str(uuid.uuid4()),
    )


def _persist_war_room(
    *,
    db: AsyncSession,
    session: RFPSession,
    state: ProposalState,
    call_notes: str | None,
    human_overrides: dict[str, Any] | None,
) -> WarRoomSession:
    war_room = WarRoomSession(
        rfp_session_id=session.id,
        status="complete",
        call_notes=call_notes,
        human_overrides=human_overrides or {},
        agent_outputs={
            "architect": _ensure_dict(state.get("architect_output")),
            "cfo": _ensure_dict(state.get("cfo_output")),
            "competitor": _ensure_dict(state.get("competitor_output")),
            "proposal": _ensure_dict(state.get("proposal_output")),
            "final_recommendations": _ensure_dict(state.get("final_recommendations")),
            "supervisor": _ensure_dict(state.get("final_recommendations")),
        },
        matched_projects=_ensure_list(state.get("similar_projects")),
        review_loops=int(state.get("review_loops") or 0),
        final_recommendations=_ensure_dict(state.get("final_recommendations")),
        completed_at=datetime.now(timezone.utc),
    )
    db.add(war_room)
    session.status = "war_room_done"

    for message in _ensure_list(state.get("discussion_log")):
        war_room.messages.append(
            WarRoomMessage(
                agent=str(message.get("agent") or "system"),
                target_agent=str(message.get("target_agent") or "all"),
                comment=str(message.get("comment") or ""),
                message_type=str(message.get("message_type") or "discussion"),
                round_index=int(message.get("round_index") or 0),
                payload=message,
            )
        )

    for output_type in ("architect", "cfo", "competitor", "proposal", "final_recommendations"):
        payload = _ensure_dict(state.get(f"{output_type}_output")) if output_type != "final_recommendations" else _ensure_dict(state.get("final_recommendations"))
        source_agent = output_type if output_type != "final_recommendations" else "supervisor"
        confidence = payload.get("confidence")
        war_room.outputs.append(
            WarRoomOutput(
                output_type=output_type,
                source_agent=source_agent,
                payload=payload,
                confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
            )
        )

    return war_room


def _serialize_outputs(state: ProposalState) -> dict[str, Any]:
    return {
        "architect": _ensure_dict(state.get("architect_output")),
        "cfo": _ensure_dict(state.get("cfo_output")),
        "competitor": _ensure_dict(state.get("competitor_output")),
        "proposal": _ensure_dict(state.get("proposal_output")),
        "final_recommendations": _ensure_dict(state.get("final_recommendations")),
        "supervisor": _ensure_dict(state.get("final_recommendations")),
    }


async def _execute_graph(war_room_id: uuid.UUID, initial_state: ProposalState) -> None:
    from app.database import AsyncSessionLocal

    try:
        result_state = await run_war_room_graph(initial_state)
        async with AsyncSessionLocal() as background_db:
            result = await background_db.execute(
                select(WarRoomSession).where(WarRoomSession.id == war_room_id)
            )
            war_room = result.scalar_one_or_none()
            if not war_room:
                return
            war_room.status = "complete"
            war_room.agent_outputs = _serialize_outputs(result_state)
            war_room.matched_projects = _ensure_list(result_state.get("similar_projects"))
            war_room.review_loops = int(result_state.get("review_loops") or 0)
            war_room.final_recommendations = _ensure_dict(result_state.get("final_recommendations"))
            war_room.completed_at = datetime.now(timezone.utc)
            war_room.error_message = None

            if war_room.messages:
                war_room.messages.clear()
            for message in _ensure_list(result_state.get("discussion_log")):
                war_room.messages.append(
                    WarRoomMessage(
                        agent=str(message.get("agent") or "system"),
                        target_agent=str(message.get("target_agent") or "all"),
                        comment=str(message.get("comment") or ""),
                        message_type=str(message.get("message_type") or "discussion"),
                        round_index=int(message.get("round_index") or 0),
                        payload=message,
                    )
                )

            if war_room.outputs:
                war_room.outputs.clear()
            for output_type, payload in _serialize_outputs(result_state).items():
                source_agent = output_type if output_type != "final_recommendations" else "supervisor"
                confidence = payload.get("confidence")
                war_room.outputs.append(
                    WarRoomOutput(
                        output_type=output_type,
                        source_agent=source_agent,
                        payload=payload,
                        confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
                    )
                )

            await background_db.commit()
    except Exception as exc:
        async with AsyncSessionLocal() as background_db:
            result = await background_db.execute(
                select(WarRoomSession).where(WarRoomSession.id == war_room_id)
            )
            war_room = result.scalar_one_or_none()
            if war_room:
                war_room.status = "failed"
                war_room.error_message = str(exc)
                await background_db.commit()


async def start_war_room(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    call_notes: str | None = None,
    human_overrides: dict[str, Any] | None = None,
) -> WarRoomSession:
    session, analysis, context = await _load_session_context(
        db,
        session_id,
        call_notes=call_notes,
        human_overrides=human_overrides,
    )

    initial_state = _build_initial_state(
        session=session,
        analysis=analysis,
        context=context,
        call_notes=call_notes,
        human_overrides=human_overrides,
    )
    session.status = "war_room_running"
    logger.info(
        "Running war room graph for session {} with {} context items",
        session_id,
        len(initial_state.get("retrieved_context") or []),
    )
    final_state = await run_war_room_graph(initial_state)
    war_room = _persist_war_room(
        db=db,
        session=session,
        state=final_state,
        call_notes=call_notes,
        human_overrides=human_overrides,
    )
    await db.flush()
    return war_room


async def get_latest_war_room(db: AsyncSession, session_id: uuid.UUID) -> WarRoomSession | None:
    result = await db.execute(
        select(WarRoomSession)
        .options(
            selectinload(WarRoomSession.messages),
            selectinload(WarRoomSession.outputs),
        )
        .where(WarRoomSession.rfp_session_id == session_id)
        .order_by(WarRoomSession.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def apply_override(
    db: AsyncSession,
    session_id: uuid.UUID,
    overrides: dict[str, Any],
) -> WarRoomSession:
    latest = await get_latest_war_room(db, session_id)
    call_notes = latest.call_notes if latest else None
    merged_overrides = dict(latest.human_overrides if latest else {})
    merged_overrides.update(overrides)
    return await start_war_room(
        db,
        session_id,
        call_notes=call_notes,
        human_overrides=merged_overrides,
    )
