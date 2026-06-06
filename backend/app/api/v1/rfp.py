"""
ProposalPilot AI — RFP Router
Handles RFP file upload, analysis triggers, and session management.
"""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import NotFoundError, RFPSessionNotFoundError
from app.models import RFPSession
from app.schemas.rfp import RFPSessionCreate, RFPSessionResponse, RFPSessionListResponse
from app.services.document_parser import validate_upload_file
from app.services import rfp_service
from app.config import get_settings
import aiofiles

settings = get_settings()
router = APIRouter()


@router.post(
    "/rfp/upload",
    response_model=RFPSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an RFP document",
)
async def upload_rfp(
    file: UploadFile = File(...),
    client_name: str | None = Form(default=None),
    title: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> RFPSessionResponse:
    """
    Upload an RFP document (PDF, DOCX, TXT, MD).
    Creates a session and returns session_id for tracking.
    """
    # Read content
    content = await file.read()
    file_size = len(content)

    # Validate file
    validate_upload_file(file.filename or "unknown", file_size)

    session = await rfp_service.create_rfp_session(
        db=db,
        filename=file.filename or "document",
        content=content,
        client_name=client_name,
        title=title or file.filename or "Untitled RFP",
    )
    return RFPSessionResponse.model_validate(session)


@router.post(
    "/rfp/{session_id}/analyze",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger RFP analysis",
)
async def analyze_rfp(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dispatch async RFP analysis task via Celery."""
    session = await rfp_service.get_session_or_404(db, session_id)
    task_id = await rfp_service.trigger_analysis(db, session)
    return {"message": "Analysis started", "task_id": task_id, "session_id": str(session_id)}


@router.get(
    "/rfp",
    response_model=RFPSessionListResponse,
    summary="List all RFP sessions",
)
async def list_rfp_sessions(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 20,
) -> RFPSessionListResponse:
    sessions, total = await rfp_service.list_sessions(db, skip=skip, limit=limit)
    return RFPSessionListResponse(
        items=[RFPSessionResponse.model_validate(s) for s in sessions],
        total=total,
    )


@router.get(
    "/rfp/{session_id}",
    response_model=RFPSessionResponse,
    summary="Get RFP session by ID",
)
async def get_rfp_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> RFPSessionResponse:
    session = await rfp_service.get_session_or_404(db, session_id)
    return RFPSessionResponse.model_validate(session)


@router.get(
    "/rfp/{session_id}/analysis",
    summary="Get structured analysis result",
)
async def get_rfp_analysis(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    analysis = await rfp_service.get_analysis(db, session_id)
    return analysis


@router.delete(
    "/rfp/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an RFP session",
)
async def delete_rfp_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await rfp_service.delete_session(db, session_id)
