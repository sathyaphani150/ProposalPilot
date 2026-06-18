from __future__ import annotations

import json
import uuid
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.models import Proposal as ProposalRecord, RFPAnalysis, RFPSession, WarRoomSession
from app.services.architecture_recommender import recommend_architecture
from app.services.expertise_matcher import match_expertise
from app.services.knowledge_service import search_knowledge
from app.services.warroom_service import WarRoomResult, run_war_room
from app.services.llm_service import get_llm_service


class Proposal(BaseModel):
    executive_summary: str
    client_problem_statement: str
    proposed_solution: str
    relevant_experience: str
    technical_architecture: str
    technology_stack: str
    delivery_approach: str
    resource_matrix: str
    cost_estimation: str
    competitive_positioning: str
    compliance_matrix: str
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


def _build_context(
    analysis: RFPAnalysis,
    war_room: WarRoomResult,
    expertise_match: dict[str, Any],
    architecture_recommendation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "rfp_summary": analysis.business_problem or "",
        "analysis": {
            "business_problem": analysis.business_problem,
            "functional_requirements": analysis.functional_requirements or [],
            "non_functional_requirements": analysis.non_functional_requirements or [],
            "data_needs": analysis.data_needs or [],
            "integration_needs": analysis.integration_needs or [],
            "compliance_needs": analysis.compliance_needs or [],
            "timeline_risks": analysis.timeline_risks or [],
            "missing_information": analysis.missing_information or [],
            "scope_boundaries": analysis.scope_boundaries or [],
            "domain_tags": analysis.domain_tags or [],
            "estimated_complexity": analysis.estimated_complexity,
        },
        "expertise_match": expertise_match,
        "architecture_recommendation": architecture_recommendation,
        "war_room": {
            "architect": war_room.architect.model_dump(),
            "cfo": war_room.cfo.model_dump(),
            "competitor": war_room.competitor.model_dump(),
        },
    }


def _build_rfp_summary(analysis: RFPAnalysis) -> str:
    raw = analysis.raw_llm_output or {}
    executive = raw.get("executive_intelligence") if isinstance(raw.get("executive_intelligence"), dict) else {}
    parts = [
        analysis.business_problem or "",
        str(executive.get("executive_summary") or ""),
        " ".join(str(item) for item in (analysis.functional_requirements or [])[:4]),
        " ".join(str(item) for item in (analysis.integration_needs or [])[:3]),
        " ".join(str(item) for item in (analysis.data_needs or [])[:3]),
        " ".join(str(item) for item in (analysis.domain_tags or [])[:3]),
    ]
    return " ".join(part for part in parts if part).strip()


def _fallback_proposal(
    analysis: RFPAnalysis,
    war_room: WarRoomResult,
    expertise_match: dict[str, Any],
    architecture_recommendation: dict[str, Any],
) -> Proposal:
    stack = architecture_recommendation.get("reusable_components") or war_room.architect.technology_stack
    summary = war_room.proposal.executive_summary or f"Proposal for {analysis.business_problem or 'the opportunity'}."
    return Proposal(
        executive_summary=summary,
        client_problem_statement=analysis.business_problem or "Client problem needs validation.",
        proposed_solution=war_room.proposal.solution_overview or war_room.architect.solution_design,
        relevant_experience=", ".join(expertise_match.get("matched_projects") or []) or "Comparable internal experience is limited.",
        technical_architecture=architecture_recommendation.get("architecture") or war_room.architect.architecture_summary,
        technology_stack=", ".join(str(item) for item in stack if str(item).strip()) or "TBD",
        delivery_approach=war_room.cfo.delivery_model,
        resource_matrix=f"Team size {war_room.cfo.team_size}; effort {war_room.cfo.effort_months} months.",
        cost_estimation=war_room.cfo.estimated_cost,
        competitive_positioning=", ".join(war_room.competitor.differentiators[:4]),
        compliance_matrix=", ".join(str(item) for item in (analysis.compliance_needs or [])[:5]) or "TBD",
        assumptions=[
            *architecture_recommendation.get("assumptions", [])[:4],
            "Proposal should be validated with the client before contracting.",
        ],
        risks=[*war_room.architect.risks[:3], *war_room.cfo.cost_risks[:3]],
    )


async def generate_proposal(
    db: AsyncSession,
    analysis_id: uuid.UUID,
    *,
    guidance: list[str] | None = None,
) -> ProposalRecord:
    analysis_result = await db.execute(select(RFPAnalysis).where(RFPAnalysis.id == analysis_id))
    analysis = analysis_result.scalar_one_or_none()
    if not analysis:
        raise NotFoundError(f"Analysis {analysis_id} not found.")

    session_result = await db.execute(select(RFPSession).where(RFPSession.id == analysis.session_id))
    session = session_result.scalar_one_or_none()
    if not session:
        raise NotFoundError(f"Session {analysis.session_id} not found.")

    summary = _build_rfp_summary(analysis)
    similar_projects = await search_knowledge(summary, item_type="project", limit=5) if summary else []
    expertise_match = await match_expertise(summary, similar_projects)
    architecture_recommendation = await recommend_architecture(summary, expertise_match, similar_projects)
    war_room_result = await run_war_room(db, analysis_id, guidance=guidance or [])
    war_room_row = await db.execute(
        select(WarRoomSession)
        .where(WarRoomSession.rfp_session_id == session.id)
        .order_by(WarRoomSession.created_at.desc())
        .limit(1)
    )
    war_room_session = war_room_row.scalar_one_or_none()

    prompt_payload = _build_context(
        analysis,
        war_room_result,
        expertise_match.model_dump(),
        architecture_recommendation.model_dump(),
    )
    prompt = """
You are a proposal writer.

Generate a proposal draft using all agent outputs.

Return structured JSON.
"""
    try:
        draft: Proposal = await get_llm_service().structured_extract(
            system_prompt=prompt.strip(),
            user_content=json.dumps(prompt_payload, ensure_ascii=False),
            output_schema=Proposal,
            temperature=0.1,
        )
    except Exception as exc:
        logger.warning(f"Proposal generation fell back to heuristics: {exc}")
        draft = _fallback_proposal(analysis, war_room_result, expertise_match.model_dump(), architecture_recommendation.model_dump())

    version_result = await db.execute(
        select(func.count(ProposalRecord.id)).where(
            ProposalRecord.rfp_session_id == session.id,
            ProposalRecord.proposal_type == "final_proposal",
        )
    )
    version_count = int(version_result.scalar_one() or 0)

    # Reuse/replace final proposal record as the latest draft.
    proposal = ProposalRecord(
        rfp_session_id=session.id,
        war_room_session_id=war_room_session.id if war_room_session else None,
        proposal_type="final_proposal",
        version=version_count + 1,
        content=draft.model_dump(),
        is_published=False,
    )
    db.add(proposal)
    session.status = "proposal_ready"
    await db.flush()
    await db.refresh(proposal)
    return proposal


async def get_latest_proposal(db: AsyncSession, session_id: uuid.UUID) -> ProposalRecord | None:
    result = await db.execute(
        select(ProposalRecord)
        .where(
            ProposalRecord.rfp_session_id == session_id,
            ProposalRecord.proposal_type == "final_proposal",
        )
        .order_by(ProposalRecord.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_proposal_by_id(db: AsyncSession, proposal_id: uuid.UUID) -> ProposalRecord:
    result = await db.execute(select(ProposalRecord).where(ProposalRecord.id == proposal_id))
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise NotFoundError(f"Proposal {proposal_id} not found.")
    return proposal
