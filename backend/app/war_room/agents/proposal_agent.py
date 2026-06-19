from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.war_room.llm_provider import get_war_room_llm_provider


class ProposalOutput(BaseModel):
    executive_summary: str
    proposed_solution: str
    architecture_section: str
    delivery_approach: str
    cost_section: str
    competitive_positioning: str
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


def _fallback(state: dict[str, Any]) -> ProposalOutput:
    architect = state.get("architect_output") or {}
    cfo = state.get("cfo_output") or {}
    competitor = state.get("competitor_output") or {}
    analysis = state.get("rfp_analysis") or {}
    fallback_problem = analysis.get("business_problem") or "the buyer's opportunity"
    session_title = str(state.get("session_title") or "the RFP")
    return ProposalOutput(
        executive_summary=(
            f"The proposal positions a modular, evidence-backed delivery model for {session_title}. "
            f"Primary problem statement: {fallback_problem}."
        ),
        proposed_solution="Deliver the solution in phased workstreams with early validation, controlled scope, and explicit decision gates.",
        architecture_section=architect.get("architecture_summary") or "Modular delivery architecture aligned to the RFP.",
        delivery_approach=(
            f"Target a {cfo.get('estimated_duration_weeks', 10)} week plan with discovery, build, test, and rollout phases for {session_title}."
        ),
        cost_section=str(cfo.get("cost_estimate") or {}),
        competitive_positioning=competitor.get("value_proposition")
        or "Differentiate through delivery control and grounded evidence.",
        risks=[
            *list(architect.get("technical_risks") or []),
            *list(cfo.get("financial_risks") or []),
        ],
        assumptions=list(architect.get("assumptions") or []),
        exclusions=[
            "Any scope not validated during discovery",
            "Third-party API or data-source delays outside buyer control",
        ],
        reasoning=(
            "The final proposal consolidates architecture, economics, and positioning into one cohesive narrative. "
            f"Session-specific grounding comes from {session_title} and the extracted RFP analysis."
        ),
        confidence=0.79,
    )


async def run_proposal_agent(state: dict[str, Any]) -> dict[str, Any]:
    provider = get_war_room_llm_provider()
    prompt = f"""
You are the Proposal Agent.
Architect output: {state.get('architect_output') or {}}
CFO output: {state.get('cfo_output') or {}}
Competitor output: {state.get('competitor_output') or {}}
Discussion log: {state.get('discussion_log') or []}
Unresolved conflicts: {state.get('unresolved_conflicts') or []}
Return a JSON object matching the schema.
"""
    structured = await provider.structured_output(
        system_prompt="You consolidate committee outputs into a final proposal strategy.",
        user_content=prompt,
        output_schema=ProposalOutput,
        temperature=0.1,
    )
    output = structured or _fallback(state)
    return {"proposal_output": output.model_dump()}
