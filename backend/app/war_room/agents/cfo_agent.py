from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.war_room.llm_provider import get_war_room_llm_provider


class CFOOutput(BaseModel):
    team_structure: list[str] = Field(default_factory=list)
    estimated_duration_weeks: float
    effort_breakdown: dict[str, int] = Field(default_factory=dict)
    cost_estimate: dict[str, Any] = Field(default_factory=dict)
    financial_risks: list[str] = Field(default_factory=list)
    margin_assessment: str
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


def _fallback(state: dict[str, Any]) -> CFOOutput:
    analysis = state.get("rfp_analysis") or {}
    session_title = str(state.get("session_title") or "the RFP")
    client_name = str(state.get("client_name") or "the client")
    complexity = str(analysis.get("estimated_complexity") or "medium").lower()
    weeks_map = {"low": 6, "medium": 10, "high": 16, "very_high": 24}
    weeks = weeks_map.get(complexity, 10)
    scope_multiplier = 1 + min(
        (len(analysis.get("functional_requirements") or []) + len(analysis.get("integration_needs") or [])) / 20,
        0.35,
    )
    base_cost = int({"low": 65000, "medium": 125000, "high": 245000, "very_high": 420000}.get(complexity, 125000) * scope_multiplier)
    return CFOOutput(
        team_structure=[
            f"delivery lead for {session_title}",
            "solution architect",
            "product analyst",
            "engineering lead",
            "QA and release support",
        ],
        estimated_duration_weeks=float(weeks + max(0, len(analysis.get("integration_needs") or []) // 2)),
        effort_breakdown={
            "discovery": 10 + len(analysis.get("missing_information") or []) * 2,
            "build": 36 + len(analysis.get("functional_requirements") or []) * 2,
            "qa": 14 + len(analysis.get("non_functional_requirements") or []),
            "deployment": 8 + len(analysis.get("integration_needs") or []),
        },
        cost_estimate={
            "currency": "USD",
            "minimum": int(base_cost * 0.8),
            "recommended": base_cost,
            "maximum": int(base_cost * 1.35),
        },
        financial_risks=[
            f"Integration uncertainty can expand delivery cost for {session_title}.",
            f"Scope growth without formal change control will compress margin for {client_name}.",
        ],
        margin_assessment=(
            "Healthy if scope stays modular and discovery closes key unknowns early. "
            f"For {session_title}, the margin will be most sensitive to integration and compliance scope."
        ),
        reasoning=(
            f"Budget and duration are sized from {complexity} complexity, session scope, and the architect's modular delivery plan."
        ),
        confidence=0.74,
    )


async def run_cfo_agent(state: dict[str, Any]) -> dict[str, Any]:
    provider = get_war_room_llm_provider()
    prompt = f"""
You are the CFO Agent in a proposal war room.
Architect output: {state.get('architect_output') or {}}
RFP analysis: {state.get('rfp_analysis') or {}}
User overrides: {state.get('user_overrides') or []}
Return a JSON object matching the schema.
"""
    structured = await provider.structured_output(
        system_prompt="You produce credible delivery economics and staffing guidance.",
        user_content=prompt,
        output_schema=CFOOutput,
        temperature=0.1,
    )
    output = structured or _fallback(state)
    return {"cfo_output": output.model_dump()}
