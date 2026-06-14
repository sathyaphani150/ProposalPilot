"""
ProposalPilot AI — Knowledge Base Router
Handles knowledge ingestion, searching, listing, and deletion.
"""
from __future__ import annotations

import json
import uuid
from typing import Any
from fastapi import APIRouter, Depends, File, Form, UploadFile, status, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import ValidationError
from app.schemas.knowledge import (
    KnowledgeItemListResponse,
    KnowledgeItemResponse,
    KnowledgeSearchMatch,
)
from app.services import knowledge_service
from app.services.document_parser import validate_upload_file

router = APIRouter()


def _parse_form_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = value.split(",")
    if not isinstance(parsed, list):
        parsed = [parsed]
    return [str(item).strip() for item in parsed if str(item).strip()]


def _parse_metadata(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


@router.post(
    "/knowledge/ingest",
    response_model=KnowledgeItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a document or project details into the Knowledge Base",
)
async def ingest_knowledge(
    file: UploadFile | None = File(default=None),
    item_type: str = Form(...),
    title: str = Form(...),
    description: str | None = Form(default=None),
    domain: str | None = Form(default=None),
    tech_stack: str | None = Form(default=None),  # Comma-separated or JSON array
    tags: str | None = Form(default=None),        # Comma-separated or JSON array
    extra_metadata: str | None = Form(default=None), # JSON object
    db: AsyncSession = Depends(get_db),
) -> KnowledgeItemResponse:
    """
    Ingest text description or parse file to index it into PostgreSQL and Qdrant vector store.
    """
    if not file and not (description and description.strip()):
        raise ValidationError("Provide either an uploaded file or a description to index.")

    tech_stack_list = _parse_form_list(tech_stack)
    tags_list = _parse_form_list(tags)
    extra_metadata_dict = _parse_metadata(extra_metadata)

    file_content = None
    filename = None
    if file:
        file_content = await file.read()
        file_size = len(file_content)
        validate_upload_file(file.filename or "unknown", file_size)
        filename = file.filename

    item = await knowledge_service.create_knowledge_item(
        db=db,
        item_type=item_type,
        title=title,
        description=description,
        domain=domain,
        tech_stack=tech_stack_list,
        tags=tags_list,
        extra_metadata=extra_metadata_dict,
        filename=filename,
        content=file_content,
    )
    return KnowledgeItemResponse.model_validate(item)


@router.get(
    "/knowledge/search",
    response_model=list[KnowledgeSearchMatch],
    summary="Search knowledge base with hybrid retrieval",
)
async def search_knowledge(
    q: str = Query(..., min_length=1),
    domain: str | None = Query(default=None),
    item_type: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=20),
) -> list[KnowledgeSearchMatch]:
    """
    Perform hybrid vector search + BM25 keyword matching on ingested documents.
    """
    results = await knowledge_service.search_knowledge(
        query=q,
        domain=domain,
        item_type=item_type,
        limit=limit,
    )
    
    matches = []
    for r in results:
        matches.append(
            KnowledgeSearchMatch(
                point_id=r["point_id"],
                score=r["score"],
                text=r["text"],
                doc_id=r["doc_id"],
                item_type=r.get("item_type"),
                title=r.get("title"),
                domain=r.get("domain"),
                tech_stack=r.get("tech_stack"),
                tags=r.get("tags"),
            )
        )
    return matches


@router.get(
    "/knowledge/items",
    response_model=KnowledgeItemListResponse,
    summary="List all knowledge base items",
)
async def list_knowledge_items(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> KnowledgeItemListResponse:
    """
    List relational records of all ingested knowledge items.
    """
    items, total = await knowledge_service.list_items(db, skip=skip, limit=limit)
    return KnowledgeItemListResponse(
        items=[KnowledgeItemResponse.model_validate(item) for item in items],
        total=total,
    )


@router.delete(
    "/knowledge/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a knowledge item from KB and Vector DB",
)
async def delete_knowledge_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Delete knowledge item record and all its associated vector points in Qdrant.
    """
    await knowledge_service.delete_knowledge_item(db, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
