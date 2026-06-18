from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.warroom_service import run_war_room, rerun_war_room

router = APIRouter()


class WarRoomRunRequest(BaseModel):
    analysis_id: uuid.UUID


class WarRoomRerunRequest(BaseModel):
    analysis_id: uuid.UUID
    guidance: list[str] = Field(default_factory=list)


@router.post("/warroom/run", summary="Run the War Room agents")
async def run(request: WarRoomRunRequest, db: AsyncSession = Depends(get_db)) -> dict:
    result = await run_war_room(db, request.analysis_id)
    return result.model_dump()


@router.post("/warroom/rerun", summary="Re-run the War Room agents with guidance")
async def rerun(request: WarRoomRerunRequest, db: AsyncSession = Depends(get_db)) -> dict:
    result = await rerun_war_room(db, request.analysis_id, request.guidance)
    return result.model_dump()
