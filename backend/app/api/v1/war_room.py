"""War room API endpoints."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.war_room import WarRoomOverrideRequest, WarRoomRunRequest
from app.services import war_room_service

router = APIRouter()


class LegacyWarRoomStartRequest(BaseModel):
    call_notes: str | None = None


def _serialize_war_room(war_room) -> dict[str, Any]:
    payload = war_room.to_dict()
    agent_outputs = payload.get("agent_outputs") or {}
    return {
        "war_room": payload,
        "discussion_log": payload.get("discussion_log") or [],
        "architect_output": agent_outputs.get("architect") or {},
        "cfo_output": agent_outputs.get("cfo") or {},
        "competitor_output": agent_outputs.get("competitor") or {},
        "proposal_output": agent_outputs.get("proposal") or {},
        "supervisor_output": agent_outputs.get("supervisor")
        or agent_outputs.get("final_recommendations")
        or {},
        "final_recommendations": agent_outputs.get("final_recommendations")
        or payload.get("final_recommendations")
        or {},
    }


@router.post("/war-room/run", summary="Run the LangGraph war room")
async def run_war_room(
    request: WarRoomRunRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    war_room = await war_room_service.start_war_room(
        db,
        request.session_id,
        call_notes=request.call_notes,
        human_overrides=request.user_overrides or None,
    )
    return _serialize_war_room(war_room)


@router.post("/war-room/override", summary="Apply a human override and rerun the war room")
async def override_war_room(
    request: WarRoomOverrideRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    override = request.override
    if isinstance(override, str):
        override = {"guidance": override}
    war_room = await war_room_service.apply_override(db, request.session_id, override)
    return _serialize_war_room(war_room)


@router.post("/war-room/{session_id}/start", summary="Backwards-compatible war room start")
async def start_war_room_legacy(
    session_id: uuid.UUID,
    request: LegacyWarRoomStartRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    war_room = await war_room_service.start_war_room(
        db,
        session_id,
        call_notes=request.call_notes,
    )
    return _serialize_war_room(war_room)


@router.get("/war-room/{session_id}/status", summary="Get latest war room status")
async def get_war_room_status(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    war_room = await war_room_service.get_latest_war_room(db, session_id)
    if not war_room:
        return {"war_room": None}
    return _serialize_war_room(war_room)


@router.post("/war-room/{session_id}/override", summary="Backwards-compatible human override")
async def apply_war_room_override(
    session_id: uuid.UUID,
    overrides: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    war_room = await war_room_service.apply_override(db, session_id, overrides)
    return _serialize_war_room(war_room)
