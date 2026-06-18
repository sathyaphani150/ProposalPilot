from __future__ import annotations

import json
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from app.services.expertise_matcher import ExpertiseMatch
from app.services.llm_service import get_llm_service


class ArchitectureRecommendation(BaseModel):
    architecture: str
    reusable_components: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    validation_questions: list[str] = Field(default_factory=list)


def _project_name(project: dict[str, Any]) -> str:
    return str(
        project.get("project_name")
        or project.get("title")
        or project.get("name")
        or "Internal knowledge item"
    ).strip()


def _project_assets(project: dict[str, Any]) -> list[str]:
    assets = [
        *(project.get("reusable_assets") or []),
        *(project.get("tech_stack") or []),
        *(project.get("tags") or []),
    ]
    cleaned = [str(item).strip() for item in assets if str(item).strip()]
    deduped: list[str] = []
    seen: set[str] = set()
    for item in cleaned:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _heuristic_recommendation(
    rfp_summary: str,
    expertise_match: ExpertiseMatch,
    similar_projects: list[dict[str, Any]],
) -> ArchitectureRecommendation:
    strongest_project = similar_projects[0] if similar_projects else {}
    project_name = _project_name(strongest_project) if strongest_project else "the closest internal reference"
    reusable_components = _project_assets(strongest_project)[:6]
    if not reusable_components:
        reusable_components = [
            "Authentication and access control",
            "Workflow orchestration layer",
            "Knowledge/retrieval service",
            "Reporting and audit logging",
        ]

    architecture = (
        "Recommend a modular, API-first architecture with a thin experience layer, "
        "a workflow/service orchestration layer, integration adapters for external systems, "
        "a governed data/reporting layer, and shared security/observability controls."
    )

    assumptions = [
        f"Treat {project_name} as supporting evidence only if its delivery pattern truly aligns with this RFP.",
        "Assume source-system access, API readiness, and data ownership must be validated before design lock.",
        "Assume cloud and security constraints will be confirmed during discovery rather than inferred.",
    ]
    if expertise_match.match_type == "No Match":
        assumptions.insert(0, "Assume internal delivery precedent is weak until more relevant KB evidence is added.")

    validation_questions = [
        "What cloud and hosting constraints must the solution follow?",
        "Which systems must integrate at launch versus later phases?",
        "What availability, security, and audit requirements are non-negotiable?",
        "Which reusable components can be carried over with minimal rework?",
        "What data ownership and migration constraints affect the architecture boundary?",
    ]

    return ArchitectureRecommendation(
        architecture=architecture,
        reusable_components=reusable_components,
        assumptions=assumptions,
        validation_questions=validation_questions,
    )


async def recommend_architecture(
    rfp_summary: str,
    expertise_match: ExpertiseMatch,
    similar_projects: list[dict[str, Any]],
) -> ArchitectureRecommendation:
    prompt = """
You are a principal solution architect.

Given:

1. Client requirements
2. Expertise match
3. Similar projects

Generate:

- Recommended architecture
- Reusable components
- Assumptions
- Validation questions

Return JSON only.
"""
    user_content = {
        "rfp_summary": rfp_summary,
        "expertise_match": expertise_match.model_dump(),
        "similar_projects": [
            {
                "project_name": _project_name(project),
                "confidence": float(project.get("confidence") or project.get("confidence_score") or project.get("vector_score") or 0.0),
                "reusable_assets": _project_assets(project)[:6],
                "relevance_summary": str(project.get("relevance_summary") or project.get("text") or "")[:500],
            }
            for project in similar_projects[:5]
        ],
    }

    try:
        result = await get_llm_service().structured_extract(
            system_prompt=prompt.strip(),
            user_content=json.dumps(user_content, ensure_ascii=False),
            output_schema=ArchitectureRecommendation,
            temperature=0.1,
        )
        return result
    except Exception as exc:
        logger.warning(f"Architecture recommendation fell back to heuristics: {exc}")
        return _heuristic_recommendation(rfp_summary, expertise_match, similar_projects)
