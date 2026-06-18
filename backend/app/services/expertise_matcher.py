from __future__ import annotations

from typing import Any

import json
from loguru import logger
from pydantic import BaseModel, Field

from app.services.llm_service import get_llm_service


class ExpertiseMatch(BaseModel):
    match_type: str
    confidence: float
    reasoning: str
    matched_projects: list[str] = Field(default_factory=list)


def _project_name(project: dict[str, Any]) -> str:
    return str(
        project.get("project_name")
        or project.get("title")
        or project.get("name")
        or "Internal knowledge item"
    ).strip()


def _project_confidence(project: dict[str, Any]) -> float:
    for key in ("confidence", "confidence_score", "vector_score", "score"):
        try:
            value = float(project.get(key) or 0.0)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return max(0.0, min(value, 1.0))
    return 0.0


def _project_summary(project: dict[str, Any]) -> str:
    parts = [
        _project_name(project),
        str(project.get("item_type") or ""),
        str(project.get("domain") or ""),
        str(project.get("text") or project.get("relevance_summary") or ""),
        " ".join(project.get("tech_stack") or []),
        " ".join(project.get("tags") or []),
    ]
    return " ".join(part for part in parts if part).strip()


def _top_projects(similar_projects: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    ordered = sorted(similar_projects, key=_project_confidence, reverse=True)
    return ordered[:limit]


def _heuristic_match(rfp_summary: str, similar_projects: list[dict[str, Any]]) -> ExpertiseMatch:
    projects = _top_projects(similar_projects)
    if not projects:
        return ExpertiseMatch(
            match_type="No Match",
            confidence=0.12,
            reasoning="No comparable internal projects were returned, so there is not enough evidence to claim prior expertise.",
            matched_projects=[],
        )

    top_confidence = _project_confidence(projects[0])
    names = [_project_name(project) for project in projects if _project_confidence(project) >= 0.35]

    if top_confidence >= 0.85:
        match_type = "Exact Match"
        confidence = min(0.96, round(top_confidence + 0.03, 2))
        reasoning = (
            f"The strongest internal reference is {names[0] if names else _project_name(projects[0])}, "
            "which aligns closely with the RFP themes and delivery pattern."
        )
    elif top_confidence >= 0.65:
        match_type = "Partial Match"
        confidence = round(top_confidence, 2)
        reasoning = (
            f"The KB contains relevant delivery evidence, led by {names[0] if names else _project_name(projects[0])}, "
            "but the fit is not strong enough to call it an exact precedent."
        )
    elif top_confidence >= 0.4:
        match_type = "Adjacent Match"
        confidence = round(max(0.4, top_confidence), 2)
        reasoning = (
            f"The closest evidence is adjacent only, with {names[0] if names else _project_name(projects[0])} providing supporting context "
            "but not a direct one-to-one match to the RFP scope."
        )
    else:
        match_type = "No Match"
        confidence = round(max(0.2, top_confidence), 2)
        reasoning = (
            "The retrieved projects are too weakly related to claim transferable expertise with confidence."
        )

    return ExpertiseMatch(
        match_type=match_type,
        confidence=confidence,
        reasoning=reasoning,
        matched_projects=names,
    )


async def match_expertise(rfp_summary: str, similar_projects: list[dict[str, Any]]) -> ExpertiseMatch:
    prompt = """
You are a delivery director.

Analyze the RFP summary and similar projects.

Classify into one:

- Exact Match
- Partial Match
- Adjacent Match
- No Match

Provide:

1. Match type
2. Confidence score between 0 and 1
3. Reasoning
4. Matching project names

Return JSON only.
"""
    user_content = {
        "rfp_summary": rfp_summary,
        "similar_projects": [
            {
                "project_name": _project_name(project),
                "confidence": _project_confidence(project),
                "summary": _project_summary(project)[:500],
            }
            for project in _top_projects(similar_projects, limit=5)
        ],
    }

    try:
        result = await get_llm_service().structured_extract(
            system_prompt=prompt.strip(),
            user_content=json.dumps(user_content, ensure_ascii=False),
            output_schema=ExpertiseMatch,
            temperature=0.0,
        )
        return result
    except Exception as exc:
        logger.warning(f"Expertise matching fell back to heuristics: {exc}")
        return _heuristic_match(rfp_summary, similar_projects)
