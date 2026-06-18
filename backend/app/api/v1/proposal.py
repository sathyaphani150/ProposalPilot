from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.export import build_docx_bytes, build_pdf_bytes
from app.services.proposal_generator import (
    generate_proposal,
    get_latest_proposal,
    get_proposal_by_id,
)

router = APIRouter()


class ProposalGenerateRequest(BaseModel):
    analysis_id: uuid.UUID
    guidance: list[str] = Field(default_factory=list)


class ProposalExportRequest(BaseModel):
    proposal_id: uuid.UUID


@router.post("/proposal/generate", summary="Generate a proposal from the War Room outputs")
async def generate(request: ProposalGenerateRequest, db: AsyncSession = Depends(get_db)) -> dict:
    proposal = await generate_proposal(db, request.analysis_id, guidance=request.guidance)
    return proposal.to_dict()


@router.get("/proposal/session/{session_id}/latest", summary="Get the latest generated proposal for a session")
async def latest(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    proposal = await get_latest_proposal(db, session_id)
    if not proposal:
        return {"proposal": None}
    return {"proposal": proposal.to_dict()}


@router.get("/proposal/{proposal_id}", summary="Get a generated proposal by ID")
async def get_proposal(proposal_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    proposal = await get_proposal_by_id(db, proposal_id)
    return proposal.to_dict()


@router.post("/proposal/export/docx", summary="Export proposal as DOCX")
async def export_docx(request: ProposalExportRequest, db: AsyncSession = Depends(get_db)):
    proposal = await get_proposal_by_id(db, request.proposal_id)
    data = build_docx_bytes(proposal.content or {})
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="Proposal.docx"'},
    )


@router.post("/proposal/export/pdf", summary="Export proposal as PDF")
async def export_pdf(request: ProposalExportRequest, db: AsyncSession = Depends(get_db)):
    proposal = await get_proposal_by_id(db, request.proposal_id)
    data = build_pdf_bytes(proposal.content or {})
    return StreamingResponse(
        iter([data]),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="Proposal.pdf"'},
    )
