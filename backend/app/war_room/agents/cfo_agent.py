from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.war_room.confidence import calculate_agent_confidence
from app.war_room.cost_calculator import compute_cost_estimate
from app.war_room.llm_provider import get_war_room_llm_provider
from app.war_room.specificity_check import warn_if_generic_agent_output

SYSTEM_PROMPT = """
You are the CFO on an internal proposal war room team. You bring deep
experience in IT services costing, staffing models, and commercial risk
management for consulting engagements.

If pre-computed cost calculation data (effort_breakdown by role/hours, and
a rate_card) is present in your input, treat it as authoritative DATA -
explain, justify, and risk-adjust it rather than inventing your own
numbers. If no such data is present, estimate effort_breakdown and
rate_card yourself using a standard delivery team pyramid (roughly 10%
architect, 40% senior engineer, 35% engineer, 10% QA, 5% PM, scaled up or
down for stated complexity), and list every estimation assumption
explicitly in financial_risks so it reads as an estimate, not a fact.

PRICING MODEL RECOMMENDATION - recommend one of:
- Fixed price: when the architect's scope is well-defined and
  missing_information / timeline_risks from the RFP analysis are low.
- Time & Materials: when there's significant missing_information or
  scope ambiguity.
- Hybrid (fixed for defined phases, T&M for undefined ones): when part of
  the engagement is clear and part isn't.
State which one and why in one sentence.

CONTINGENCY GUIDANCE - recommend a contingency buffer scaled to the
number of items in missing_information and timeline_risks: roughly 10%
for low uncertainty, 15-20% for moderate, 25%+ for high. State the
recommended buffer and what's driving it.

MARGIN GUARDRAIL - do not let a "reduce scope to MVP" or similar override
push the recommended price below a sustainable margin floor; if an
override would force that, say so explicitly in margin_assessment rather
than silently complying.

Reconcile against the architect's output: if recommended_stack or
reusable_components implies materially more or less effort than your
numbers assume, flag it in financial_risks.

If human_overrides contains commercial guidance, recompute your narrative
around the overridden inputs and state what changed.

OUTPUT FIELDS:
- team_structure: as before.
- effort_breakdown: [{"role": str, "hours": int}], reflecting the staffing
  pyramid above.
- rate_card: [{"role": str, "rate": float, "currency": str}].
- pricing_model_recommendation: one sentence - model + one-line why.
- cost_estimate: as before, including the contingency buffer applied.
- financial_risks: must reference specific RFP items, not generic
  "scope uncertainty" language.
  Each financial_risks entry must name the RFP-derived driver behind the
  risk: a named integration, named compliance framework, or specific scope
  item from the analysis. Reject broad risk categories unless they point
  to the exact RFP signal creating the commercial exposure.
- margin_assessment: include the guardrail check above.

Return JSON matching the schema.
"""


class CFOOutput(BaseModel):
    team_structure: list[str] = Field(default_factory=list)
    estimated_duration_weeks: float
    effort_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    rate_card: list[dict[str, Any]] = Field(default_factory=list)
    pricing_model_recommendation: str = ""
    cost_estimate: dict[str, Any] = Field(default_factory=dict)
    financial_risks: list[str] = Field(default_factory=list)
    margin_assessment: str
    reasoning: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


def _override_text(state: dict[str, Any]) -> str:
    overrides = state.get("user_overrides") or []
    parts: list[str] = []
    for item in overrides:
        if not isinstance(item, dict):
            continue
        override = item.get("override")
        if isinstance(override, dict):
            parts.extend(
                str(value).strip()
                for value in override.values()
                if isinstance(value, str) and value.strip()
            )
        elif isinstance(override, str) and override.strip():
            parts.append(override.strip())
    call_notes = state.get("call_notes")
    if isinstance(call_notes, str) and call_notes.strip():
        parts.append(call_notes.strip())
    return " | ".join(parts)


def _fallback(state: dict[str, Any]) -> CFOOutput:
    analysis = state.get("rfp_analysis") or {}
    architect = state.get("architect_output") or {}
    session_title = str(state.get("session_title") or "the RFP")
    client_name = str(state.get("client_name") or "the client")
    complexity = str(analysis.get("estimated_complexity") or "medium").lower()
    calc = compute_cost_estimate(complexity)
    weeks_map = {"low": 6, "medium": 10, "high": 16, "very_high": 24}
    weeks = weeks_map.get(complexity, 10)
    scope_multiplier = 1 + min(
        (len(analysis.get("functional_requirements") or []) + len(analysis.get("integration_needs") or [])) / 20,
        0.35,
    )
    base_cost = int(calc["total_cost_estimate"] * scope_multiplier)
    override_text = _override_text(state)
    uncertainty_count = len(analysis.get("missing_information") or []) + len(analysis.get("timeline_risks") or [])
    contingency_pct = 0.1 if uncertainty_count <= 2 else 0.18 if uncertainty_count <= 5 else 0.25
    pricing_model = "Hybrid (fixed for discovery/build foundation, T&M for evolving integrations)"
    if "fixed-price" in override_text.lower() or "fixed price" in override_text.lower():
        pricing_model = "Fixed price because the override explicitly pushes for commercial certainty despite scoped assumptions."
    elif uncertainty_count >= 4:
        pricing_model = "Time & Materials because unresolved scope and delivery unknowns are still material."
    elif uncertainty_count <= 1:
        pricing_model = "Fixed price because scope signals and delivery assumptions are comparatively stable."
    base_recommended = int(base_cost * (1 + contingency_pct))
    architect_stack_size = len(architect.get("recommended_stack") or [])
    return CFOOutput(
        team_structure=[
            f"delivery lead for {session_title}",
            "solution architect",
            "product analyst",
            "engineering lead",
            "QA and release support",
        ],
        estimated_duration_weeks=float(weeks + max(0, len(analysis.get("integration_needs") or []) // 2)),
        effort_breakdown=calc["effort_breakdown"],
        rate_card=calc["rate_card"],
        pricing_model_recommendation=pricing_model,
        cost_estimate={
            "currency": "USD",
            "minimum": int(base_recommended * 0.8),
            "recommended": base_recommended,
            "maximum": int(base_recommended * 1.2),
            "total_hours": calc["total_hours"],
            "contingency_buffer_pct": int(contingency_pct * 100),
        },
        financial_risks=[
            f"Integration uncertainty across {', '.join(str(item) for item in (analysis.get('integration_needs') or [])[:2]) or 'named interfaces'} can expand delivery cost for {session_title}.",
            f"Compliance obligations such as {', '.join(str(item) for item in (analysis.get('compliance_needs') or [])[:2]) or 'required controls'} will add design, QA, and governance effort.",
            *([f"Architect scope implies {architect_stack_size} core stack elements; verify the current estimate fully covers that implementation footprint."] if architect_stack_size >= 5 else []),
            *([f"Commercial override applied: {override_text}." ] if override_text else []),
        ],
        margin_assessment=(
            "Healthy if scope stays modular and discovery closes key unknowns early. "
            f"For {session_title}, the margin will be most sensitive to integration and compliance scope."
            + (
                " The requested commercial posture may pressure margin below a comfortable floor unless scope is tightly constrained."
                if any(term in override_text.lower() for term in ["mvp", "reduce scope", "fixed-price", "fixed price"])
                else ""
            )
        ),
        reasoning=(
            f"Budget and duration are sized from {complexity} complexity, a {int(contingency_pct * 100)}% contingency buffer, session scope, and the architect's delivery plan."
            + (f" Override changed the commercial stance toward: {override_text}." if override_text else "")
        ),
    )


async def run_cfo_agent(state: dict[str, Any]) -> dict[str, Any]:
    provider = get_war_room_llm_provider()
    analysis = state.get("rfp_analysis") or {}
    complexity = str(analysis.get("estimated_complexity") or "medium")
    calc = compute_cost_estimate(complexity)
    prompt = f"""
{SYSTEM_PROMPT}

Architect output: {state.get('architect_output') or {}}
RFP analysis: {analysis}
Call notes: {state.get('call_notes') or ''}
User overrides: {state.get('user_overrides') or []}
Pre-computed cost calculation data: {calc}
Return a JSON object matching the schema.
"""
    structured = await provider.structured_output(
        system_prompt=SYSTEM_PROMPT,
        user_content=prompt,
        output_schema=CFOOutput,
        temperature=0.1,
    )
    output = structured or _fallback(state)
    payload = output.model_dump()
    generated_by = "llm" if structured else "deterministic_fallback"
    payload["generated_by"] = generated_by
    if structured:
        warn_if_generic_agent_output("cfo", state, payload)
    payload["confidence"] = calculate_agent_confidence(
        agent="cfo",
        state=state,
        payload=payload,
        generated_by=generated_by,
    )
    return {"cfo_output": payload}
