from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.expertise_matcher import ExpertiseMatch, match_expertise

router = APIRouter()


class SimilarProjectInput(BaseModel):
    project_name: str | None = None
    title: str | None = None
    match_type: str | None = None
    confidence: float | None = None
    confidence_score: float | None = None
    vector_score: float | None = None
    rerank_score: float | None = None
    relevance_summary: str | None = None
    reusable_assets: list[str] = Field(default_factory=list)
    doc_id: str | None = None
    item_type: str | None = None
    domain: str | None = None
    text: str | None = None
    tags: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)


class ExpertiseMatchRequest(BaseModel):
    rfp_summary: str
    similar_projects: list[SimilarProjectInput] = Field(default_factory=list)


@router.post(
    "/expertise/match",
    response_model=ExpertiseMatch,
    summary="Classify organizational expertise against similar projects",
)
async def expertise_match(request: ExpertiseMatchRequest) -> ExpertiseMatch:
    return await match_expertise(
        request.rfp_summary,
        [project.model_dump() for project in request.similar_projects],
    )
