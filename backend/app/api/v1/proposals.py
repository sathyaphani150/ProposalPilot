"""
ProposalPilot AI - Proposal endpoints.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import proposal_service

router = APIRouter()


@router.post(
    "/proposals/{session_id}/generate",
    summary="Generate a final proposal",
)
async def generate_proposal(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    proposal = await proposal_service.generate_final_proposal(db, session_id)
    return {"proposal": proposal_service.proposal_to_public_dict(proposal)}


@router.get(
    "/proposals/session/{session_id}/final",
    summary="Get the latest final proposal for a session",
)
async def get_latest_final_proposal(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    proposal = await proposal_service.get_latest_final_proposal(db, session_id)
    if not proposal:
        return {"proposal": None}
    return {"proposal": proposal_service.proposal_to_public_dict(proposal)}


@router.get(
    "/proposals/{proposal_id}",
    summary="Get a generated proposal by ID",
)
async def get_proposal(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    proposal = await proposal_service.get_proposal_or_404(db, proposal_id)
    return proposal_service.proposal_to_public_dict(proposal)
