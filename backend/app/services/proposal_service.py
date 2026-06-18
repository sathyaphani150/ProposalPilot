"""
ProposalPilot AI - proposal and prep-pack generation service.
"""
from __future__ import annotations

import uuid
import re
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError, ValidationError
from app.models import Proposal, RFPAnalysis, RFPSession
from app.services import knowledge_service
from app.services.llm_service import get_llm_service
from app.services.rfp_engine import analyze_rfp_document


class PrepPackLLMOutput(BaseModel):
    rfp_summary: str = Field(description="Executive-grade opportunity summary, not copied RFP text.")
    client_situation_assessment: str
    prospect_call_narrative: str
    value_propositions: list[str] = Field(default_factory=list)
    business_questions: list[str] = Field(default_factory=list)
    data_questions: list[str] = Field(default_factory=list)
    integration_questions: list[str] = Field(default_factory=list)
    architecture_questions: list[str] = Field(default_factory=list)
    implementation_questions: list[str] = Field(default_factory=list)
    discovery_questions: dict[str, list[str]] = Field(default_factory=dict)
    talking_points: list[str] = Field(default_factory=list)
    assumptions_to_validate: list[str] = Field(default_factory=list)
    risks_and_assumptions: list[str] = Field(default_factory=list)
    scope_guardrails: list[str] = Field(default_factory=list)
    solution_narrative: str
    proposed_architecture_direction: str
    competitive_considerations: list[str] = Field(default_factory=list)


_PREP_PACK_SYSTEM_PROMPT = """
You are a senior strategy consultant, pursuit lead, and solution architect preparing
company executives for an RFP discovery/qualification call.

Generate a consulting-grade prep pack. Do not summarize the RFP. Do not copy
tender/legal/procurement boilerplate. Do not invent facts. You may infer strategic
implications only when supported by the provided analysis/evidence.

The discovery questionnaire is the most important section. Questions must be
specific to the opportunity, executive-friendly, and useful for non-technical
stakeholders. Avoid generic questions unless they are tailored to the context.

Return valid JSON matching the schema. Keep content concise, dense, and actionable.
"""

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
                "project_name": match.get("project_name") or match.get("title") or "Internal knowledge item",
                "match_type": _match_type(score),
                "confidence_score": round(score, 3),
                "confidence": round(float(match.get("confidence") or score), 3),
                "vector_score": round(float(match.get("vector_score") or score), 3),
                "rerank_score": round(float(match.get("rerank_score") or 0), 3),
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
        cleaned.setdefault("architecture", [
            "What cloud preference, deployment model, and availability requirement should guide the design?",
            "Which scalability, observability, and disaster recovery targets are mandatory?",
        ])
        cleaned.setdefault("implementation_readiness", [
            "Is a dedicated product owner and delivery sponsor available now?",
            "Are requirements sufficiently finalized to move beyond discovery?",
        ])
        return cleaned

    return {
        "business": [
            "What measurable business outcome and success metric should drive the proposal?",
            "Which scope items are mandatory for the first release versus later phases?",
        ],
        "data": [
            "Expected data volume, quality, retention, and migration complexity?",
        ],
        "integration": [
            "Which source and target systems must be integrated at launch?",
        ],
        "architecture": [
            "What cloud preference, deployment model, and availability requirement should we design for?",
        ],
        "implementation_readiness": [
            "Is a dedicated product owner available and are requirements finalized?",
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


def _question_group(value: Any) -> list[str]:
    return _dedupe_text(_as_raw_string_list(value))[:8]


def _build_discovery_questions(payload: dict[str, Any]) -> dict[str, list[str]]:
    questions = _clean_question_groups(payload.get("discovery_questions"))
    if questions:
        return questions
    return {
        "business": _question_group(payload.get("business_questions")),
        "data": _question_group(payload.get("data_questions")),
        "integration": _question_group(payload.get("integration_questions")),
        "architecture": _question_group(payload.get("architecture_questions")),
        "implementation_readiness": _question_group(payload.get("implementation_questions")),
    }


def _sanitize_prep_output(output: PrepPackLLMOutput) -> dict[str, Any]:
    payload = output.model_dump()
    for key in (
        "value_propositions",
        "business_questions",
        "data_questions",
        "integration_questions",
        "architecture_questions",
        "implementation_questions",
        "talking_points",
        "assumptions_to_validate",
        "risks_and_assumptions",
        "scope_guardrails",
        "competitive_considerations",
    ):
        payload[key] = _dedupe_text(_as_raw_string_list(payload.get(key)))[:8]

    payload["discovery_questions"] = _build_discovery_questions(payload)
    discovery = payload["discovery_questions"]
    payload["business_questions"] = payload["business_questions"] or discovery.get("business", [])
    payload["data_questions"] = payload["data_questions"] or discovery.get("data", [])
    payload["integration_questions"] = payload["integration_questions"] or discovery.get("integration", [])
    payload["architecture_questions"] = payload["architecture_questions"] or discovery.get("architecture", [])
    payload["implementation_questions"] = payload["implementation_questions"] or discovery.get("implementation_readiness", [])

    for key in (
        "rfp_summary",
        "client_situation_assessment",
        "prospect_call_narrative",
        "solution_narrative",
        "proposed_architecture_direction",
    ):
        value = _clean_brief_item(str(payload.get(key) or ""))
        payload[key] = value or str(payload.get(key) or "").strip()[:900]

    return payload


async def _generate_llm_prep_pack_content(
    session: RFPSession,
    analysis: RFPAnalysis,
    formatted_matches: list[dict[str, Any]],
    fallback_content: dict[str, Any],
) -> dict[str, Any] | None:
    executive = _executive_intelligence(analysis)
    kb_evidence = [
        {
            "title": match.get("title"),
            "match_type": match.get("match_type"),
            "confidence_score": match.get("confidence_score"),
            "relevance_summary": match.get("relevance_summary"),
            "reusable_assets": match.get("reusable_assets"),
        }
        for match in formatted_matches[:4]
    ]
    analysis_payload = {
        "session_title": session.title,
        "client_name": session.client_name,
        "business_problem": analysis.business_problem,
        "capability_tags": analysis.domain_tags,
        "estimated_complexity": analysis.estimated_complexity,
        "executive_intelligence": executive,
        "functional_signals": _as_text_list(analysis.functional_requirements)[:6],
        "integration_signals": _as_text_list(analysis.integration_needs)[:6],
        "data_signals": _as_text_list(analysis.data_needs)[:6],
        "security_compliance_signals": _as_text_list(analysis.compliance_needs)[:6],
        "timeline_risk_signals": _as_text_list(analysis.timeline_risks)[:6],
        "missing_information": _as_text_list(analysis.missing_information)[:8],
        "kb_evidence": kb_evidence,
    }

    user_content = f"""
Create the executive prep pack for this opportunity.

Use this structured context:
{analysis_payload}

Requirements:
- Discovery questions must be specific to the opportunity context above.
- Include business, data, integration, architecture, and implementation readiness questions.
- Keep the legacy discovery_questions object aligned with those five categories where useful.
- Each question should help executives uncover hidden requirements, decision criteria, stakeholder alignment, risk, or future vision.
- If KB evidence is weak or absent, say so indirectly through cautious positioning; do not invent past experience.
- Do not copy raw RFP clauses.
"""
    try:
        result: PrepPackLLMOutput = await get_llm_service().structured_extract(
            system_prompt=_PREP_PACK_SYSTEM_PROMPT,
            user_content=user_content,
            output_schema=PrepPackLLMOutput,
            temperature=0.15,
        )
        payload = _sanitize_prep_output(result)
        if not payload.get("discovery_questions"):
            return None
        payload["similar_projects"] = fallback_content["similar_projects"]
        payload["past_expertise_story"] = fallback_content["past_expertise_story"]
        payload["quality_note"] = {
            **fallback_content["quality_note"],
            "generation_mode": "llm_grounded_prep_pack",
        }
        return payload
    except Exception as exc:
        logger.warning(f"LLM prep-pack generation unavailable; using deterministic fallback: {exc}")
        return None


async def _refresh_analysis_from_source(db: AsyncSession, session: RFPSession, existing: RFPAnalysis | None) -> RFPAnalysis:
    if not session.raw_text:
        if existing:
            return existing
        raise ValidationError("The uploaded RFP has no parsed text. Re-upload a text-readable PDF/DOCX before generating a prep pack.")

    analysis_data = await analyze_rfp_document(session.raw_text)
    if existing:
        for key, value in analysis_data.items():
            setattr(existing, key, value)
        await db.flush()
        await db.refresh(existing)
        return existing

    analysis = RFPAnalysis(session_id=session.id, **analysis_data)
    db.add(analysis)
    await db.flush()
    await db.refresh(analysis)
    return analysis


def _build_prep_pack_content(
    session: RFPSession,
    analysis: RFPAnalysis,
    matches: list[dict[str, Any]],
    *,
    query: str,
    retrieval_warning: str | None = None,
) -> dict[str, Any]:
    functional = _as_text_list(analysis.functional_requirements)
    nfrs = _as_text_list(analysis.non_functional_requirements)
    integrations = _as_text_list(analysis.integration_needs)
    data_needs = _as_text_list(analysis.data_needs)
    compliance = _as_text_list(analysis.compliance_needs)
    report = _executive_report(analysis)
    risk_assessment = report.get("risk_assessment")
    report_risks: list[Any] = risk_assessment if isinstance(risk_assessment, list) else []
    risks = _dedupe_text(
        [
            f"{item.get('risk_title')}: {item.get('impact')}"
            for item in report_risks
            if isinstance(item, dict) and item.get("risk_title")
        ]
        or _as_text_list(analysis.timeline_risks)
    )[:8]
    guardrails = _as_text_list(analysis.scope_boundaries)
    formatted_matches = _evidence_filtered_matches(matches, query)
    discovery_questions = _discovery_questions(analysis)

    best_match = formatted_matches[0] if formatted_matches else None
    if best_match:
        score = float(best_match.get("confidence_score") or 0)
        if best_match.get("match_type") == "adjacent" or score < 0.65:
            expertise_story = (
                f"Adjacent match only. {best_match['title']} supports marketplace/catalog/search-scale credibility, "
                "but it does not prove NLP-based query understanding, domain-specific operations, or the required search-stack integration expertise. "
                "Use as secondary evidence unless stronger KB proof is connected."
            )
        else:
            expertise_story = (
                f"We have a relevant internal reference: {best_match['title']} "
                f"({best_match['match_type']} match, confidence {best_match['confidence_score']}). "
                f"The reusable evidence is: {best_match['relevance_summary']}"
            )
    else:
        expertise_story = (
            "No strong prior internal match was found yet. Position this as a new delivery "
            "opportunity and ask targeted discovery questions before committing estimates."
        )

    content = {
        "rfp_summary": analysis.business_problem
        or f"{session.title} needs clarification before a proposal can be scoped.",
        "client_situation_assessment": _client_situation_assessment(analysis),
        "value_propositions": _value_propositions(analysis),
        "assumptions_to_validate": _assumptions_to_validate(analysis),
        "competitive_considerations": [
            "A stronger competitor will avoid generic feature claims and instead show how they control delivery risk, buyer dependencies, security obligations, and value realization.",
            "Differentiate by presenting a phased discovery-to-delivery approach with explicit assumptions, governance, and measurable outcomes.",
            "Avoid overclaiming prior experience unless the Knowledge Base evidence is materially relevant to this opportunity.",
        ],
        "similar_projects": formatted_matches,
        "past_expertise_story": expertise_story,
        "prospect_call_narrative": _executive_narrative(analysis, formatted_matches),
        "discovery_questions": discovery_questions,
        "business_questions": discovery_questions.get("business", []),
        "data_questions": discovery_questions.get("data", []),
        "integration_questions": discovery_questions.get("integration", []),
        "architecture_questions": discovery_questions.get("architecture", []),
        "implementation_questions": discovery_questions.get("implementation_readiness", []),
        "talking_points": _talking_points(analysis, functional, integrations, compliance, nfrs),
        "risks_and_assumptions": [
            *risks[:6],
            *[
                f"Assumption: {item}"
                for item in _as_text_list(analysis.missing_information)[:4]
            ],
        ],
        "scope_guardrails": guardrails
        or [
            "Do not commit to fixed pricing until data, integration, timeline, and acceptance criteria are confirmed.",
            "Keep first release scoped around the most valuable demonstrable workflow.",
        ],
        "proposed_architecture_direction": _architecture_direction(analysis, integrations, data_needs, compliance),
        "solution_narrative": (
            "Problem: the buyer has described a broad requirement with operational, technical, and commercial dependencies. "
            "Approach: validate outcomes, users, data, integrations, security, and acceptance gates before final scope. "
            "Solution: propose modular workstreams for workflow/user experience, integration, data/reporting, security, operations, and rollout governance. "
            "Business outcome: reduce delivery ambiguity, improve operational control, and create a credible path from RFP response to measurable implementation value."
        ),
        "quality_note": {
            "generation_mode": "deterministic_grounded",
            "retrieval_warning": retrieval_warning,
            "source": "RFP analysis plus internal KB search snippets",
        },
    }
    return content


async def generate_prep_pack(db: AsyncSession, session_id: uuid.UUID) -> Proposal:
    result = await db.execute(select(RFPSession).where(RFPSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise NotFoundError(f"RFP session {session_id} not found.")

    analysis_result = await db.execute(
        select(RFPAnalysis)
        .where(RFPAnalysis.session_id == session_id)
        .order_by(RFPAnalysis.created_at.desc())
        .limit(1)
    )
    analysis = await _refresh_analysis_from_source(
        db,
        session,
        analysis_result.scalar_one_or_none(),
    )

    query = _build_search_query(analysis)
    matches: list[dict[str, Any]] = []
    retrieval_warning = None
    if query:
        try:
            matches = await knowledge_service.search_knowledge(query, limit=8)
        except Exception as exc:
            logger.warning(f"Knowledge retrieval failed during prep-pack generation: {exc}")
            retrieval_warning = "Knowledge retrieval failed; prep pack uses only RFP analysis."

    fallback_content = _build_prep_pack_content(
        session,
        analysis,
        matches,
        query=query,
        retrieval_warning=retrieval_warning,
    )
    content = (
        await _generate_llm_prep_pack_content(
            session,
            analysis,
            fallback_content.get("similar_projects", []),
            fallback_content,
        )
        or fallback_content
    )

    version_result = await db.execute(
        select(func.count(Proposal.id)).where(
            Proposal.rfp_session_id == session_id,
            Proposal.proposal_type == "prep_pack",
        )
    )
    version = int(version_result.scalar_one() or 0) + 1

    proposal = Proposal(
        rfp_session_id=session_id,
        proposal_type="prep_pack",
        version=version,
        content=content,
    )
    db.add(proposal)
    session.status = "prep_ready"
    await db.flush()
    await db.refresh(proposal)
    return proposal


async def get_proposal_or_404(db: AsyncSession, proposal_id: uuid.UUID) -> Proposal:
    result = await db.execute(select(Proposal).where(Proposal.id == proposal_id))
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise NotFoundError(f"Proposal {proposal_id} not found.")
    return proposal


async def get_latest_prep_pack(db: AsyncSession, session_id: uuid.UUID) -> Proposal | None:
    result = await db.execute(
        select(Proposal)
        .where(
            Proposal.rfp_session_id == session_id,
            Proposal.proposal_type == "prep_pack",
        )
        .order_by(Proposal.version.desc(), Proposal.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
