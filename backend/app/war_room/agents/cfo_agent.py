from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.war_room.cost_calculator import compute_cost_estimate
from app.war_room.llm_provider import get_war_room_llm_provider

SYSTEM_PROMPT = """
You are the CFO on an internal proposal war room team.

You will be given a pre-computed cost calculation (effort_breakdown by role/hours, and a rate_card) as DATA, not as something to invent. Your job is to explain, justify, and risk-adjust those numbers - not to produce your own independent estimate. If no calculation is provided, say so in financial_risks rather than fabricating numbers.

Reconcile against the architect's output explicitly: if the architect's recommended_stack or reusable_components implies more or less effort than the provided calculation assumed, say so in financial_risks.

If human_overrides contains commercial guidance (e.g. "reduce scope to MVP", "offshore-heavy model"), recompute your narrative around the overridden inputs you're given and state what changed.

Cost drivers in financial_risks must reference specific items from the RFP analysis (named integrations, compliance needs) - not generic "scope uncertainty."

Return JSON matching the schema.
"""


class CFOOutput(BaseModel):
    team_structure: list[str] = Field(default_factory=list)
    estimated_duration_weeks: float
    effort_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    rate_card: list[dict[str, Any]] = Field(default_factory=list)
    cost_estimate: dict[str, Any] = Field(default_factory=dict)
    financial_risks: list[str] = Field(default_factory=list)
    margin_assessment: str
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


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
    return " | ".join(parts)


def _fallback(state: dict[str, Any]) -> CFOOutput:
    analysis = state.get("rfp_analysis") or {}
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
        cost_estimate={
            "currency": "USD",
            "minimum": int(base_cost * 0.8),
            "recommended": base_cost,
            "maximum": int(base_cost * 1.35),
            "total_hours": calc["total_hours"],
        },
        financial_risks=[
            f"Integration uncertainty can expand delivery cost for {session_title}.",
            f"Scope growth without formal change control will compress margin for {client_name}.",
            *([f"Commercial override applied: {override_text}." ] if override_text else []),
        ],
        margin_assessment=(
            "Healthy if scope stays modular and discovery closes key unknowns early. "
            f"For {session_title}, the margin will be most sensitive to integration and compliance scope."
        ),
        reasoning=(
            f"Budget and duration are sized from {complexity} complexity, session scope, and the architect's modular delivery plan."
            + (f" Override changed the commercial stance toward: {override_text}." if override_text else "")
        ),
        confidence=0.74,
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
    return {"cfo_output": output.model_dump()}
