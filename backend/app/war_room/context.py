from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RFPAnalysis, RFPSession
from app.services import knowledge_service

WAR_ROOM_CONTEXT_MATCH_LIMIT = 5


def _compact_items(items: list[Any], limit: int = 5) -> list[str]:
    values: list[str] = []
    for item in items[:limit]:
        text = str(item).strip()
        if text:
            values.append(text)
    return values


async def get_relevant_context(
    db: AsyncSession,
    *,
    session: RFPSession,
    analysis: RFPAnalysis,
    user_overrides: list[dict[str, Any]] | None = None,
    call_notes: str | None = None,
) -> dict[str, Any]:
    query_parts = [
        session.title,
        analysis.business_problem or "",
        " ".join(_compact_items(analysis.functional_requirements, 5)),
        " ".join(_compact_items(analysis.integration_needs, 4)),
        " ".join(_compact_items(analysis.data_needs, 4)),
        " ".join(_compact_items(analysis.compliance_needs, 4)),
        " ".join(_compact_items(analysis.domain_tags, 3)),
        call_notes or "",
        " ".join(str(item) for override in (user_overrides or []) for item in override.values() if isinstance(item, str)),
    ]
    query = " ".join(part for part in query_parts if part).strip()

    similar_projects: list[dict[str, Any]] = []
    retrieved_context: list[dict[str, Any]] = []
    if query:
        try:
            raw_projects = await knowledge_service.search_knowledge(query, limit=WAR_ROOM_CONTEXT_MATCH_LIMIT)
            analysis_dict = {
                "business_problem": analysis.business_problem,
                "functional_requirements": analysis.functional_requirements or [],
                "integration_needs": analysis.integration_needs or [],
                "data_needs": analysis.data_needs or [],
                "compliance_needs": analysis.compliance_needs or [],
                "domain_tags": analysis.domain_tags or [],
            }
            from app.services.rfp_engine import knowledge_evidence_from_matches
            similar_projects = knowledge_evidence_from_matches(raw_projects, analysis_dict)
        except Exception as exc:
            logger.warning(f"War Room context knowledge search failed for session {session.id}: {exc}")
            similar_projects = []

    retrieved_context.extend(similar_projects)

    return {
        "retrieved_context": retrieved_context,
        "similar_projects": similar_projects,
        "search_query": query,
    }
