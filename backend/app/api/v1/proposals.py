"""
ProposalPilot AI - Proposal endpoints.
"""
from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import ValidationError
from app.services import proposal_service

router = APIRouter()


class ProposalGenerateRequest(BaseModel):
    type: Literal["prep_pack", "final_proposal"] = "prep_pack"


@router.post(
    "/proposals/{session_id}/generate",
    summary="Generate a prep pack or final proposal",
)
async def generate_proposal(
    session_id: uuid.UUID,
    request: ProposalGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if request.type != "prep_pack":
        raise ValidationError(
            "Final proposal generation is not implemented yet. Generate a prep pack first."
        )

    proposal = await proposal_service.generate_prep_pack(db, session_id)
    return proposal.to_dict()


@router.get(
    "/proposals/session/{session_id}/prep-pack",
    summary="Get the latest prep pack for a session",
)
async def get_latest_prep_pack(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    proposal = await proposal_service.get_latest_prep_pack(db, session_id)
    if not proposal:
        return {"proposal": None}
    return {"proposal": proposal.to_dict()}


@router.get(
    "/proposals/{proposal_id}",
    summary="Get a generated proposal by ID",
)
async def get_proposal(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    proposal = await proposal_service.get_proposal_or_404(db, proposal_id)
    return proposal.to_dict()
