"""
ProposalPilot AI - War Room endpoints.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import war_room_service

router = APIRouter()


class WarRoomStartRequest(BaseModel):
    call_notes: str | None = None


@router.post("/war-room/{session_id}/start", summary="Start deterministic War Room")
async def start_war_room(
    session_id: uuid.UUID,
    request: WarRoomStartRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    war_room = await war_room_service.start_war_room(
        db,
        session_id,
        call_notes=request.call_notes,
    )
    return war_room.to_dict()


@router.get("/war-room/{session_id}/status", summary="Get latest War Room status")
async def get_war_room_status(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    war_room = await war_room_service.get_latest_war_room(db, session_id)
    if not war_room:
        return {"war_room": None}
    return {"war_room": war_room.to_dict()}


@router.post("/war-room/{session_id}/override", summary="Apply human override and regenerate")
async def apply_war_room_override(
    session_id: uuid.UUID,
    overrides: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict:
    war_room = await war_room_service.apply_override(db, session_id, overrides)
    return war_room.to_dict()
