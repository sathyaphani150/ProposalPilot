"""
ProposalPilot AI — Knowledge Base Pydantic Schemas
Request/Response models for Knowledge Base items and search.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class KnowledgeItemCreate(BaseModel):
    item_type: str = Field(..., description="project | repo | doc | proposal | case_study | architecture")
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(default=None)
    domain: str | None = Field(default=None, max_length=255)
    tech_stack: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    extra_metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_type: str
    title: str
    description: str | None
    domain: str | None
    tech_stack: list[str]
    tags: list[str]
    original_filename: str | None
    chunk_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class KnowledgeItemListResponse(BaseModel):
    items: list[KnowledgeItemResponse]
    total: int


class KnowledgeSearchMatch(BaseModel):
    point_id: str
    score: float
    vector_score: float | None = None
    rerank_score: float | None = None
    confidence: float | None = None
    text: str
    doc_id: str
    project_name: str | None = None
    item_type: str | None = None
    title: str | None = None
    domain: str | None = None
    tech_stack: list[str] | None = None
    tags: list[str] | None = None


class RetrievalResult(BaseModel):
    project_name: str
    vector_score: float
    rerank_score: float
    confidence: float
