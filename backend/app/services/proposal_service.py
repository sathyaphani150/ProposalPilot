"""
ProposalPilot AI - final proposal generation service.
"""
from __future__ import annotations

import uuid
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError, ValidationError
from app.models import Proposal, RFPAnalysis, RFPSession, WarRoomSession

_TENDER_ADMIN_NOISE_TERMS = {
    "audited",
    "balance sheet",
    "statutory auditor",
    "turnover",
    "net worth",
    "emd",
    "earnest money",
    "pre-bid",
    "bid submission",
    "bid opening",
    "cppp",
    "annexure",
    "no liability",
    "bidder shall bear",
    "new delhi",
    "address",
    "contact details",
}


def _is_tender_admin_noise(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in _TENDER_ADMIN_NOISE_TERMS)


def _as_text_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    else:
        items = [str(value).strip()]
    return [_clean_brief_item(item) for item in items if _clean_brief_item(item)]


def _as_raw_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _clean_brief_item(text: str) -> str:
    text = re.sub(r"\.{4,}\s*\d+", "", text)
    text = re.sub(r"\s{2,}", " ", text).strip(" -:\t")
    if len(text) < 16:
        return ""
    lower = text.lower()
    headings = {
        "functional requirements",
        "non-functional requirements",
        "resource requirements",
        "checklist of documents",
        "documentation",
        "system documentation",
        "scope of work",
    }
    boilerplate_terms = {
        "procedure & submission",
        "procedure and submission",
        "format for bid",
        "bid-security declaration",
        "performance bank guarantee",
        "evaluated bid score",
        "technical score",
        "bid price",
        "read in consonance",
        "addendum",
        "addenda",
        "bidder should enclose",
    }
    if lower in headings or any(term in lower for term in boilerplate_terms) or _is_tender_admin_noise(text):
        return ""
    return text[:420]


def _first(items: list[str], fallback: str) -> str:
    return items[0] if items else fallback


def _match_type(score: float) -> str:
    if score >= 0.78:
        return "exact"
    if score >= 0.58:
        return "partial"
    if score >= 0.22:
        return "adjacent"
    return "none"


def _safe_score(raw_score: Any) -> float:
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(score, 1.0))


def _build_search_query(analysis: RFPAnalysis) -> str:
    executive = _executive_intelligence(analysis)
    parts = [
        analysis.business_problem or "",
        executive.get("executive_summary", ""),
        " ".join(_as_text_list(analysis.functional_requirements)[:5]),
        " ".join(_as_text_list(analysis.integration_needs)[:4]),
        " ".join(_as_text_list(analysis.data_needs)[:3]),
        " ".join(_as_text_list(analysis.compliance_needs)[:4]),
        " ".join(_as_text_list(analysis.domain_tags)),
    ]
    return " ".join(part for part in parts if part).strip()


_STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "shall", "will", "must", "should",
    "rfp", "bid", "bids", "bidder", "proposal", "document", "section", "scope", "work",
    "services", "service", "project", "requirements", "requirement", "system", "solution",
    "provide", "including", "through", "within", "under", "their", "there", "where", "which",
}


def _important_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower())
    return {
        token
        for token in tokens
        if token not in _STOPWORDS and len(token) >= 4 and not token.isdigit()
    }


def _is_relevant_match(query_tokens: set[str], match: dict[str, Any], score: float) -> bool:
    haystack = " ".join(
        str(match.get(key) or "")
        for key in ("title", "domain", "item_type", "text")
    )
    for key in ("tech_stack", "tags"):
        value = match.get(key) or []
        if isinstance(value, list):
            haystack += " " + " ".join(str(item) for item in value)
    overlap = query_tokens & _important_tokens(haystack)
    return len(overlap) >= 2 or (score >= 0.72 and len(overlap) >= 1)


def _format_matches(matches: list[dict[str, Any]], *, query: str, min_score: float = 0.38) -> list[dict[str, Any]]:
    formatted = []
    seen_docs: set[str] = set()
    query_tokens = _important_tokens(query)
    for match in matches:
        doc_id = str(match.get("doc_id") or "")
        if doc_id and doc_id in seen_docs:
            continue
        if doc_id:
            seen_docs.add(doc_id)

        score = _safe_score(match.get("score"))
        if score < min_score:
            continue
        if query_tokens and not _is_relevant_match(query_tokens, match, score):
            continue
        text = str(match.get("text") or "").strip()
        tech_stack = _as_raw_string_list(match.get("tech_stack"))
        tags = _as_raw_string_list(match.get("tags"))
        formatted.append(
            {
                "doc_id": doc_id,
                "title": match.get("title") or "Internal knowledge item",
                "match_type": _match_type(score),
                "confidence_score": round(score, 3),
                "relevance_summary": text[:650],
                "reusable_assets": [*tech_stack[:4], *tags[:4]][:6],
                "evidence": {
                    "chunk_index": match.get("chunk_index", 0),
                    "snippet": text[:900],
                },
            }
        )
        if len(formatted) >= 5:
            break
    return formatted


def _evidence_filtered_matches(matches: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    return _format_matches(matches, query=query, min_score=0.38)


def _executive_intelligence(analysis: RFPAnalysis) -> dict[str, Any]:
    raw = analysis.raw_llm_output or {}
    value = raw.get("executive_intelligence")
    return value if isinstance(value, dict) else {}


def _executive_report(analysis: RFPAnalysis) -> dict[str, Any]:
    raw = analysis.raw_llm_output or {}
    value = raw.get("executive_report")
    return value if isinstance(value, dict) else {}


def _executive_narrative(analysis: RFPAnalysis, matches: list[dict[str, Any]]) -> str:
    executive = _executive_intelligence(analysis)
    summary = str(executive.get("executive_summary") or "").strip()
    focus = ", ".join(str(tag).replace("_", " ") for tag in (analysis.domain_tags or [])[:3]) if analysis.domain_tags else "the buyer's priority workflow"
    strongest_match = f" The closest internal reference is {matches[0]['title']}." if matches else ""
    if summary:
        return (
            f"{summary} {strongest_match} "
            "Use the call to validate the strategic problem, decision criteria, buyer-owned dependencies, and commercial risk before discussing delivery estimates."
        )
    if matches:
        return (
            f"Lead the call as an outcome and risk-discovery conversation around {focus}.{strongest_match} "
            "Use that evidence carefully, then validate which parts genuinely transfer to this buyer's operating model. "
            "Avoid committing price, timeline, architecture, or staffing until success metrics, scope boundaries, data readiness, integrations, security obligations, and acceptance criteria are confirmed."
        )
    return (
        f"Lead the call as an outcome and risk-discovery conversation around {focus}. "
        "The RFP should be converted into a scoped opportunity by validating business outcomes, users, workflow priority, data readiness, integrations, security obligations, operating ownership, timeline dependencies, and acceptance criteria."
    )


def _architecture_direction(analysis: RFPAnalysis, integrations: list[str], data_needs: list[str], compliance: list[str]) -> str:
    focus = ", ".join(str(tag).replace("_", " ") for tag in (analysis.domain_tags or [])[:2]) if analysis.domain_tags else "the target workflow"
    return (
        f"Recommend a modular architecture for {focus} with clear boundaries between user experience, workflow services, integration adapters, data/reporting, security controls, observability, and support operations. "
        "Keep external systems behind adapters and avoid coupling proposal estimates to undocumented APIs or unverified data assumptions. Validate business workflow, data ownership, integration readiness, security obligations, deployment model, acceptance criteria, and support responsibilities before finalizing solution design."
    )


def _talking_points(
    analysis: RFPAnalysis,
    functional: list[str],
    integrations: list[str],
    compliance: list[str],
    nfrs: list[str],
) -> list[str]:
    executive = _executive_intelligence(analysis)
    recommendations = [
        str(item)
        for item in executive.get("recommendations", [])
        if str(item).strip()
    ]
    points = [
        "Open with business outcomes, decision criteria, and the operational problem before discussing technology.",
        "Confirm the highest-priority users, workflows, MVP boundary, and non-negotiable success metrics.",
        "Validate data ownership, data quality, reporting needs, and integration readiness before committing scope or dates.",
        "Separate fixed delivery scope from support, maintenance, change requests, migration, training, and commercial tender obligations.",
        "Identify security, compliance, audit, deployment, UAT, and acceptance gates early.",
    ]

    return _dedupe_text([*recommendations[:4], *points])[:8]


def _dedupe_text(items: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = _clean_brief_item(item)
        normalized = re.sub(r"[^a-z0-9]+", " ", cleaned.lower()).strip()
        if not cleaned or normalized in seen:
            continue
        seen.add(normalized)
        output.append(cleaned)
    return output


def _discovery_questions(analysis: RFPAnalysis) -> dict[str, list[str]]:
    missing = _as_text_list(analysis.missing_information)
    report = _executive_report(analysis)
    call_prep = report.get("prospect_call_prep") if isinstance(report.get("prospect_call_prep"), dict) else {}
    if call_prep:
        return {
            "business": _dedupe_text(_as_text_list(call_prep.get("must_ask_discovery_questions")))[:8],
            "integration": _dedupe_text(_as_text_list(call_prep.get("technical_questions")))[:8],
            "commercial": _dedupe_text(_as_text_list(call_prep.get("commercial_questions")))[:8],
            "governance": _dedupe_text(_as_text_list(call_prep.get("risk_questions")))[:8],
            "operations": _dedupe_text(_as_text_list(call_prep.get("assumptions_to_validate")))[:8],
        }

    executive = _executive_intelligence(analysis)
    drivers = [str(item) for item in executive.get("business_drivers", []) if str(item).strip()]
    risks = [str(item) for item in executive.get("risks_and_dependencies", []) if str(item).strip()]

    functional = _as_text_list(analysis.functional_requirements)
    integrations = _as_text_list(analysis.integration_needs)
    data_needs = _as_text_list(analysis.data_needs)
    compliance = _as_text_list(analysis.compliance_needs)
    nfrs = _as_text_list(analysis.non_functional_requirements)
    timelines = _as_text_list(analysis.timeline_risks)
    boundaries = _as_text_list(analysis.scope_boundaries)

    groups = {
        "business": [
            *missing[:3],
            *[f"What metric should prove this business driver: {item}" for item in drivers[:2]],
        ],
        "operations": [
            *[f"Which release phase should include this scope item: {item}" for item in functional[:3]],
            *[f"What operating owner, support window, and acceptance path apply to: {item}" for item in boundaries[:2]],
        ],
        "data": [
            *[f"What source owner, quality threshold, retention rule, and sign-off process apply to: {item}" for item in data_needs[:4]],
        ],
        "integration": [
            *[f"What API documentation, sandbox access, payload examples, and approval timeline exist for: {item}" for item in integrations[:4]],
        ],
        "governance": [
            *[f"What control evidence, approval owner, and test criteria are required for: {item}" for item in [*compliance, *nfrs][:4]],
            *[f"How should we mitigate this dependency or risk before pricing: {item}" for item in risks[:2]],
        ],
        "commercial": [
            *[f"How should this timeline or dependency affect milestones, pricing assumptions, or change control: {item}" for item in timelines[:3]],
            *missing[3:6],
        ],
    }
    cleaned = {
        key: _dedupe_text([question for question in questions if not _is_tender_admin_noise(question)])[:8]
        for key, questions in groups.items()
    }
    if any(cleaned.values()):
        return cleaned

    return {
        "business": [
            "What measurable business outcome and success metric should drive the proposal?",
            "Which scope items are mandatory for the first release versus later phases?",
        ],
        "governance": [
            "Who owns acceptance criteria, UAT sign-off, security approval, and go-live readiness?",
        ],
        "commercial": [
            "Which assumptions must be protected before committing to fixed price, fixed timeline, or managed-service obligations?",
        ],
    }


def _client_situation_assessment(analysis: RFPAnalysis) -> str:
    executive = _executive_intelligence(analysis)
    summary = str(executive.get("executive_summary") or analysis.business_problem or "").strip()
    gaps = _as_text_list(analysis.missing_information)
    if summary:
        base = summary
    else:
        base = "The RFP does not provide enough business context to confidently infer the buyer's current situation."
    if gaps:
        return base + " The first executive call should focus on closing the highest-risk gaps: " + "; ".join(gaps[:3]) + "."
    return base


def _value_propositions(analysis: RFPAnalysis) -> list[str]:
    tags = set(analysis.domain_tags or [])
    values = [
        "Convert a broad RFP into a controlled delivery roadmap with clear phases, assumptions, and decision gates.",
        "Reduce delivery risk by validating buyer-owned data, integration, security, and acceptance dependencies before estimation.",
        "Improve executive visibility through measurable success criteria, reporting expectations, and governance cadence.",
    ]
    if "integration" in tags:
        values.append("De-risk external-system dependency through API readiness checks, adapter-based architecture, and integration test planning.")
    if "data" in tags or "reporting" in tags:
        values.append("Turn data migration/reporting requirements into governed source ownership, reconciliation, and KPI definitions.")
    if "security" in tags:
        values.append("Treat security, auditability, monitoring, and access control as architecture-level requirements instead of late-stage compliance tasks.")
    return _dedupe_text(values)[:6]


def _assumptions_to_validate(analysis: RFPAnalysis) -> list[str]:
    return _dedupe_text(
        [
            *_as_text_list(analysis.missing_information),
            "Buyer will provide timely access to source systems, documentation, decision makers, and test environments.",
            "Acceptance criteria, UAT ownership, security approvals, and production release gates can be agreed before delivery starts.",
            "Scope changes, optional modules, support expectations, and integration delays will be governed through formal change control.",
        ]
    )[:8]


def _clean_question_groups(groups: Any) -> dict[str, list[str]]:
    if not isinstance(groups, dict):
        return {}
    cleaned: dict[str, list[str]] = {}
    for group, items in groups.items():
        if not isinstance(items, list):
            continue
        key = re.sub(r"[^a-z0-9_]+", "_", str(group).lower()).strip("_") or "questions"
        values = _dedupe_text([str(item) for item in items])[:8]
        if values:
            cleaned[key] = values
    return cleaned


def proposal_to_public_dict(proposal: Proposal) -> dict[str, Any]:
    """Serialize a generated final proposal."""
    return proposal.to_dict()


async def get_proposal_or_404(db: AsyncSession, proposal_id: uuid.UUID) -> Proposal:
    result = await db.execute(select(Proposal).where(Proposal.id == proposal_id))
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise NotFoundError(f"Proposal {proposal_id} not found.")
    return proposal


async def generate_final_proposal(db: AsyncSession, session_id: uuid.UUID) -> Proposal:
    session_result = await db.execute(select(RFPSession).where(RFPSession.id == session_id))
    session = session_result.scalar_one_or_none()
    if not session:
        raise NotFoundError(f"RFP session {session_id} not found.")

    war_room_result = await db.execute(
        select(WarRoomSession)
        .where(
            WarRoomSession.rfp_session_id == session_id,
            WarRoomSession.status == "complete",
        )
        .order_by(WarRoomSession.completed_at.desc(), WarRoomSession.created_at.desc())
        .limit(1)
    )
    war_room = war_room_result.scalar_one_or_none()
    if not war_room:
        raise ValidationError("Complete the War Room before generating the final proposal.")

    outputs = war_room.agent_outputs or {}
    proposal_output = outputs.get("proposal") or {}
    architect_output = outputs.get("architect") or {}
    cfo_output = outputs.get("cfo") or {}

    content = {
        "executive_summary": proposal_output.get("executive_summary", ""),
        "client_problem_statement": proposal_output.get("client_problem_restatement", ""),
        "proposed_solution": (
            proposal_output.get("proposed_solution_narrative")
            or proposal_output.get("proposed_solution", "")
        ),
        "technical_architecture": (
            proposal_output.get("architecture_section")
            or architect_output.get("architecture_summary", "")
        ),
        "technology_stack": architect_output.get("recommended_stack", []),
        "delivery_approach": proposal_output.get("delivery_approach", ""),
        "commercial_summary": (
            proposal_output.get("commercial_summary")
            or proposal_output.get("cost_section", "")
        ),
        "resource_and_effort": {
            "team_structure": cfo_output.get("team_structure", []),
            "estimated_duration_weeks": cfo_output.get("estimated_duration_weeks"),
            "effort_breakdown": cfo_output.get("effort_breakdown", []),
            "pricing_model": cfo_output.get("pricing_model_recommendation", ""),
            "cost_estimate": cfo_output.get("cost_estimate", {}),
        },
        "competitive_positioning": proposal_output.get("competitive_positioning", ""),
        "compliance_matrix": proposal_output.get("compliance_matrix", []),
        "risks": proposal_output.get("risks", []),
        "assumptions": proposal_output.get("assumptions", []),
        "exclusions": proposal_output.get("exclusions", []),
        "consistency_flags": proposal_output.get("consistency_flags", []),
    }

    version_result = await db.execute(
        select(func.count(Proposal.id)).where(
            Proposal.rfp_session_id == session_id,
            Proposal.proposal_type == "final_proposal",
        )
    )
    proposal = Proposal(
        rfp_session_id=session_id,
        war_room_session_id=war_room.id,
        proposal_type="final_proposal",
        version=int(version_result.scalar_one() or 0) + 1,
        content=content,
    )
    db.add(proposal)
    session.status = "proposal_ready"
    await db.flush()
    await db.refresh(proposal)
    return proposal


async def get_latest_final_proposal(db: AsyncSession, session_id: uuid.UUID) -> Proposal | None:
    result = await db.execute(
        select(Proposal)
        .where(
            Proposal.rfp_session_id == session_id,
            Proposal.proposal_type == "final_proposal",
        )
        .order_by(Proposal.version.desc(), Proposal.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
