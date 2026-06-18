from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError, ValidationError
from app.models import Proposal, RFPAnalysis, RFPSession, WarRoomSession
from app.services.architecture_recommender import recommend_architecture
from app.services.expertise_matcher import match_expertise
from app.services.knowledge_service import search_knowledge
from app.services.warroom import (
    ArchitectResult,
    CFOResult,
    CompetitorResult,
    ProposalDraft,
    run_architect_agent,
    run_cfo_agent,
    run_competitor_agent,
    run_proposal_agent,
)


class UserGuidance(BaseModel):
    guidance: list[str] = Field(default_factory=list)


class WarRoomResult(BaseModel):
    architect: ArchitectResult
    cfo: CFOResult
    competitor: CompetitorResult
    proposal: ProposalDraft


def _clean_guidance(guidance: list[str] | None) -> list[str]:
    if not guidance:
        return []
    return [str(item).strip() for item in guidance if str(item).strip()]


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


async def _load_analysis(db: AsyncSession, analysis_id: uuid.UUID) -> RFPAnalysis:
    result = await db.execute(select(RFPAnalysis).where(RFPAnalysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise NotFoundError(f"Analysis {analysis_id} not found.")
    return analysis


async def _search_similar_projects(analysis: RFPAnalysis) -> list[dict[str, Any]]:
    query = _build_rfp_summary(analysis)
    if not query:
        return []
    try:
        return await search_knowledge(query, item_type="project", limit=5)
    except Exception as exc:
        logger.warning(f"War Room knowledge retrieval failed: {exc}")
        return []


async def _persist_war_room(
    db: AsyncSession,
    *,
    session: RFPSession,
    analysis: RFPAnalysis,
    guidance: list[str],
    similar_projects: list[dict[str, Any]],
    result: WarRoomResult,
) -> WarRoomSession:
    existing = await db.execute(
        select(WarRoomSession)
        .where(WarRoomSession.rfp_session_id == session.id)
        .order_by(WarRoomSession.created_at.desc())
        .limit(1)
    )
    latest = existing.scalar_one_or_none()
    if latest:
        latest.status = "complete"
        latest.human_overrides = {"guidance": guidance}
        latest.agent_outputs = {
            "architect": result.architect.model_dump(),
            "cfo": result.cfo.model_dump(),
            "competitor": result.competitor.model_dump(),
            "proposal": result.proposal.model_dump(),
        }
        latest.matched_projects = similar_projects
        latest.completed_at = datetime.now(timezone.utc)
        session.status = "war_room_done"
        await db.flush()
        await db.refresh(latest)
        return latest

    war_room = WarRoomSession(
        rfp_session_id=session.id,
        status="complete",
        human_overrides={"guidance": guidance},
        agent_outputs={
            "architect": result.architect.model_dump(),
            "cfo": result.cfo.model_dump(),
            "competitor": result.competitor.model_dump(),
            "proposal": result.proposal.model_dump(),
        },
        matched_projects=similar_projects,
    )
    db.add(war_room)
    session.status = "war_room_done"
    await db.flush()
    await db.refresh(war_room)
    return war_room


async def run_war_room(
    db: AsyncSession,
    analysis_id: uuid.UUID,
    *,
    guidance: list[str] | None = None,
) -> WarRoomResult:
    analysis = await _load_analysis(db, analysis_id)
    session_result = await db.execute(select(RFPSession).where(RFPSession.id == analysis.session_id))
    session = session_result.scalar_one_or_none()
    if not session:
        raise NotFoundError(f"Session {analysis.session_id} not found.")

    clean_guidance = _clean_guidance(guidance)
    similar_projects = await _search_similar_projects(analysis)
    expertise = await match_expertise(_build_rfp_summary(analysis), similar_projects)
    architecture = await recommend_architecture(_build_rfp_summary(analysis), expertise, similar_projects)

    architect = await run_architect_agent(
        rfp_summary=_build_rfp_summary(analysis),
        architecture_recommendation=architecture.model_dump(),
        guidance=clean_guidance,
    )
    cfo = await run_cfo_agent(
        architect_result=architect.model_dump(),
        guidance=clean_guidance,
    )
    competitor = await run_competitor_agent(
        rfp_summary=_build_rfp_summary(analysis),
        architect_result=architect.model_dump(),
        cfo_result=cfo.model_dump(),
        guidance=clean_guidance,
    )
    proposal = await run_proposal_agent(
        rfp_summary=_build_rfp_summary(analysis),
        architect_result=architect,
        cfo_result=cfo,
        competitor_result=competitor,
        guidance=clean_guidance,
    )

    result = WarRoomResult(
        architect=architect,
        cfo=cfo,
        competitor=competitor,
        proposal=proposal,
    )
    await _persist_war_room(
        db,
        session=session,
        analysis=analysis,
        guidance=clean_guidance,
        similar_projects=similar_projects,
        result=result,
    )
    return result


async def rerun_war_room(
    db: AsyncSession,
    analysis_id: uuid.UUID,
    guidance: list[str],
) -> WarRoomResult:
    return await run_war_room(db, analysis_id, guidance=guidance)
