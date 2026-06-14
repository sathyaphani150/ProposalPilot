"""
ProposalPilot AI - deterministic baseline War Room service.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError, ValidationError
from app.models import RFPAnalysis, RFPSession, WarRoomSession
from app.services.proposal_service import get_latest_prep_pack


def _items(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _lines(title: str, values: list[str], fallback: str) -> str:
    rows = values[:6] or [fallback]
    return title + "\n" + "\n".join(f"- {row}" for row in rows)


def _currency_range(complexity: str | None) -> dict[str, Any]:
    ranges = {
        "low": (35_000, 55_000, 80_000, 6),
        "medium": (75_000, 120_000, 175_000, 10),
        "high": (150_000, 240_000, 360_000, 16),
        "very_high": (275_000, 420_000, 650_000, 24),
    }
    minimum, recommended, maximum, weeks = ranges.get((complexity or "medium").lower(), ranges["medium"])
    return {
        "currency": "USD",
        "minimum": minimum,
        "recommended": recommended,
        "maximum": maximum,
        "duration_weeks": weeks,
        "note": "Directional estimate only; validate integrations, data scope, SLAs, and team model before committing.",
    }


def _build_agent_outputs(
    session: RFPSession,
    analysis: RFPAnalysis,
    prep_pack: dict[str, Any] | None,
    *,
    call_notes: str | None,
    human_overrides: dict[str, Any] | None = None,
) -> dict[str, str]:
    functional = _items(analysis.functional_requirements)
    nfrs = _items(analysis.non_functional_requirements)
    integrations = _items(analysis.integration_needs)
    data_needs = _items(analysis.data_needs)
    compliance = _items(analysis.compliance_needs)
    risks = _items(analysis.timeline_risks)
    missing = _items(analysis.missing_information)
    guardrails = _items(analysis.scope_boundaries)
    matches = (prep_pack or {}).get("similar_projects") or []
    best_match = matches[0] if matches else None
    overrides = human_overrides or {}

    estimate = _currency_range(analysis.estimated_complexity)

    architect = "\n\n".join(
        [
            f"Recommended direction for {session.title}: modular API-first delivery with clear ingestion, workflow, retrieval, and export boundaries.",
            _lines("Core capabilities to design around:", functional, "Confirm MVP user workflows before architecture lock."),
            _lines("Integration/data constraints:", integrations + data_needs, "Validate source systems, API access, sample data, and ownership."),
            _lines("Non-functional controls:", nfrs + compliance, "Define security, observability, and performance acceptance criteria."),
            "Architecture risk: do not overbuild agent orchestration until grounding, retrieval, and export are stable.",
        ]
    )

    cfo = "\n\n".join(
        [
            f"Directional commercial range: {estimate['currency']} {estimate['minimum']:,} - {estimate['maximum']:,}; recommended planning case {estimate['currency']} {estimate['recommended']:,}.",
            f"Indicative duration: {estimate['duration_weeks']} weeks.",
            _lines("Cost drivers:", integrations + data_needs + compliance, "Unknown integration/data/compliance scope can move cost materially."),
            _lines("Commercial risks:", risks + missing, "Hold pricing assumptions until discovery answers are confirmed."),
            "Margin guardrail: price discovery, architecture, and implementation separately if client uncertainty remains high.",
        ]
    )

    competitor = "\n\n".join(
        [
            "Win strategy: lead with speed-to-clarity, grounded internal evidence, and transparent assumptions.",
            (
                f"Proof point: {best_match.get('title')} is a {best_match.get('match_type')} match with "
                f"{round(float(best_match.get('confidence_score', 0)) * 100)}% confidence."
                if best_match
                else "Proof point gap: add or capture a relevant past-project story before final proposal."
            ),
            _lines("Differentiators to emphasize:", [
                "Evidence-backed prep pack instead of generic proposal drafting.",
                "Human override loop for scope, architecture, and commercial strategy.",
                "Clear assumption and risk register before fixed commitments.",
            ], "Use grounded delivery credibility rather than broad AI claims."),
            _lines("Competitor pressure points:", guardrails + missing, "Competitors may overpromise; win by being precise and credible."),
        ]
    )

    proposal = "\n\n".join(
        [
            f"Executive proposal angle: {analysis.business_problem or 'Client problem requires clarification.'}",
            _lines("Include in proposed solution:", functional, "Define MVP scope around the highest-value workflow."),
            _lines("Assumptions/exclusions:", guardrails + missing, "List assumptions explicitly in the proposal."),
            _lines("Risk mitigation:", risks + compliance, "Map each risk to a discovery question or delivery control."),
            "Next proposal step: convert the prep pack, call notes, and War Room outputs into a final proposal package.",
        ]
    )

    supervisor_notes = [
        "War Room baseline completed from RFP analysis, prep pack, and optional call notes.",
        "All outputs are directional and should be validated with the client before pricing or scope commitment.",
    ]
    if call_notes:
        supervisor_notes.append(f"Call notes included: {call_notes[:700]}")
    if overrides:
        supervisor_notes.append(f"Human overrides applied: {overrides}")

    return {
        "architect": architect,
        "cfo": cfo,
        "competitor": competitor,
        "proposal": proposal,
        "supervisor": "\n".join(f"- {note}" for note in supervisor_notes),
    }


async def start_war_room(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    call_notes: str | None = None,
    human_overrides: dict[str, Any] | None = None,
) -> WarRoomSession:
    session_result = await db.execute(select(RFPSession).where(RFPSession.id == session_id))
    session = session_result.scalar_one_or_none()
    if not session:
        raise NotFoundError(f"RFP session {session_id} not found.")

    analysis_result = await db.execute(
        select(RFPAnalysis)
        .where(RFPAnalysis.session_id == session_id)
        .order_by(RFPAnalysis.created_at.desc())
        .limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()
    if not analysis:
        raise ValidationError("Run RFP analysis before starting the War Room.")

    prep_pack = await get_latest_prep_pack(db, session_id)
    content = prep_pack.content if prep_pack else None
    agent_outputs = _build_agent_outputs(
        session,
        analysis,
        content,
        call_notes=call_notes,
        human_overrides=human_overrides,
    )

    war_room = WarRoomSession(
        rfp_session_id=session_id,
        status="complete",
        call_notes=call_notes,
        human_overrides=human_overrides or {},
        agent_outputs=agent_outputs,
        matched_projects=(content or {}).get("similar_projects", []),
        completed_at=datetime.now(timezone.utc),
    )
    db.add(war_room)
    session.status = "war_room_done"
    await db.flush()
    await db.refresh(war_room)
    return war_room


async def get_latest_war_room(db: AsyncSession, session_id: uuid.UUID) -> WarRoomSession | None:
    result = await db.execute(
        select(WarRoomSession)
        .where(WarRoomSession.rfp_session_id == session_id)
        .order_by(WarRoomSession.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def apply_override(
    db: AsyncSession,
    session_id: uuid.UUID,
    overrides: dict[str, Any],
) -> WarRoomSession:
    latest = await get_latest_war_room(db, session_id)
    call_notes = latest.call_notes if latest else None
    merged_overrides = dict(latest.human_overrides if latest else {})
    merged_overrides.update(overrides)
    return await start_war_room(
        db,
        session_id,
        call_notes=call_notes,
        human_overrides=merged_overrides,
    )
