from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.architecture_recommender import ArchitectureRecommendation, recommend_architecture
from app.services.expertise_matcher import ExpertiseMatch

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


class ArchitectureRecommendRequest(BaseModel):
    rfp_summary: str
    expertise_match: ExpertiseMatch
    similar_projects: list[SimilarProjectInput] = Field(default_factory=list)


@router.post(
    "/architecture/recommend",
    response_model=ArchitectureRecommendation,
    summary="Generate an architecture recommendation",
)
async def recommend(request: ArchitectureRecommendRequest) -> ArchitectureRecommendation:
    return await recommend_architecture(
        request.rfp_summary,
        request.expertise_match,
        [project.model_dump() for project in request.similar_projects],
    )
