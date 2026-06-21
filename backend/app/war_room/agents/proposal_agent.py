from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.war_room.confidence import calculate_agent_confidence
from app.war_room.llm_provider import get_war_room_llm_provider
from app.war_room.specificity_check import warn_if_generic_agent_output

SYSTEM_PROMPT = """
You are the Proposal Writer on an internal proposal war room team. You
receive the RFP analysis and the architect, CFO, and competitor outputs.
Your job is to synthesize them into ONE coherent, persuasive document in a
single consistent voice - not to concatenate the three upstream outputs
back-to-back. Do not introduce claims that aren't traceable to one of
those four inputs.

SOURCE-OF-TRUTH PRECEDENCE when inputs conflict: RFP analysis > architect
output (scope/technical claims) > CFO output (cost/timeline claims) >
competitor output (positioning claims). If the architect's scope and the
CFO's costed scope disagree, defer to the architect and flag the mismatch
in consistency_flags rather than averaging or guessing.

PERSUASION STRUCTURE:
- Open executive_summary with the client's business problem restated in
  plain, non-technical language - not RFP boilerplate.
- Lead with credibility (proof points from competitor_output and
  reusable_components from architect_output) before making forward-
  looking claims.
- Thread ONE consistent win theme (from competitor_output.win_themes)
  through executive_summary, proposed_solution_narrative, and
  competitive_positioning, so the document reads as one argument, not
  four stitched-together agent outputs.
- Write executive_summary for a non-technical decision-maker;
  proposed_solution_narrative may use more technical language;
  commercial_summary should lead with value/ROI framing before raw
  numbers.

RISK FRAMING - distinguish two kinds of risk in open_risks_and_assumptions:
proactive risks we're flagging to build trust (things we're managing) vs.
blocking risks that require discovery before commitment (sourced from the
RFP analysis's missing_information). Label which is which.

Structure the output in this section order: executive_summary,
client_problem_restatement, proposed_solution_narrative,
commercial_summary, competitive_positioning, compliance_matrix,
open_risks_and_assumptions.

compliance_matrix: one row per item in compliance_needs, mapped to how the
proposed solution addresses it. Use "Not yet addressed" rather than
omitting an item.

If human_overrides is present, confirm explicitly how the final narrative
reflects it.

All narrative fields must stay concrete to this RFP: executive_summary,
proposed_solution, architecture_section, delivery_approach, cost_section,
and competitive_positioning must each reference at least one specific
input fact where natural. Reject generic proposal language that could be
reused unchanged for a different client or domain.

Return JSON matching the schema.
"""


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
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    client_problem_restatement: str = ""
    compliance_matrix: list[dict[str, str]] = Field(default_factory=list)
    consistency_flags: list[str] = Field(default_factory=list)


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


def _build_compliance_matrix(analysis: dict[str, Any], proposal_text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in analysis.get("compliance_needs") or []:
        requirement = str(item).strip()
        if not requirement:
            continue
        lower = requirement.lower()
        if any(term in proposal_text.lower() for term in lower.split()[:3]):
            status = "Addressed"
            notes = "Mapped into the proposed solution narrative."
        else:
            status = "Not yet addressed"
            notes = "Needs explicit coverage in the final draft."
        rows.append({"requirement": requirement, "status": status, "notes": notes})
    return rows


def _format_cost_section(cost_estimate: Any) -> str:
    if not isinstance(cost_estimate, dict) or not cost_estimate:
        return "Commercial estimate to be confirmed after discovery."

    currency = str(cost_estimate.get("currency") or "USD")
    minimum = cost_estimate.get("minimum")
    recommended = cost_estimate.get("recommended")
    maximum = cost_estimate.get("maximum")
    total_hours = cost_estimate.get("total_hours")
    contingency = cost_estimate.get("contingency_buffer_pct")

    range_text = (
        f"{currency} {minimum:,} to {maximum:,}, with a recommended budget of {currency} {recommended:,}"
        if isinstance(minimum, int | float) and isinstance(maximum, int | float) and isinstance(recommended, int | float)
        else "Budget range to be confirmed"
    )
    effort_text = f" based on {total_hours:,} estimated hours" if isinstance(total_hours, int | float) else ""
    contingency_text = (
        f" and a {contingency}% contingency buffer"
        if isinstance(contingency, int | float)
        else ""
    )
    return f"{range_text}{effort_text}{contingency_text}."


def _fallback(state: dict[str, Any]) -> ProposalOutput:
    architect = state.get("architect_output") or {}
    cfo = state.get("cfo_output") or {}
    competitor = state.get("competitor_output") or {}
    analysis = state.get("rfp_analysis") or {}
    fallback_problem = analysis.get("business_problem") or "the buyer's opportunity"
    session_title = str(state.get("session_title") or "the RFP")
    override_text = _override_text(state)
    proposed_solution = "Deliver the solution in phased workstreams with early validation, controlled scope, and explicit decision gates."
    compliance_matrix = _build_compliance_matrix(analysis, proposed_solution)
    consistency_flags: list[str] = []
    if architect.get("technical_risks") and cfo.get("financial_risks"):
        consistency_flags.append("Architect and CFO both identify risk coverage; ensure the final draft keeps them aligned.")
    if override_text:
        consistency_flags.append(f"Human override reflected in final narrative: {override_text}.")
    return ProposalOutput(
        executive_summary=(
            f"The proposal positions a modular, evidence-backed delivery model for {session_title}. "
            f"Primary problem statement: {fallback_problem}."
        ),
        client_problem_restatement=f"{session_title} is asking for a controlled way to solve: {fallback_problem}.",
        proposed_solution=proposed_solution
        + (f" Human override reflected: {override_text}." if override_text else ""),
        architecture_section=architect.get("architecture_summary") or "Modular delivery architecture aligned to the RFP.",
        delivery_approach=(
            f"Target a {cfo.get('estimated_duration_weeks', 10)} week plan with discovery, build, test, and rollout phases for {session_title}."
        ),
        cost_section=_format_cost_section(cfo.get("cost_estimate")),
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
        compliance_matrix=compliance_matrix,
        consistency_flags=consistency_flags,
    )


async def run_proposal_agent(state: dict[str, Any]) -> dict[str, Any]:
    provider = get_war_room_llm_provider()
    prompt = f"""
{SYSTEM_PROMPT}

Architect output: {state.get('architect_output') or {}}
CFO output: {state.get('cfo_output') or {}}
Competitor output: {state.get('competitor_output') or {}}
RFP analysis: {state.get('rfp_analysis') or {}}
Discussion log: {state.get('discussion_log') or []}
Unresolved conflicts: {state.get('unresolved_conflicts') or []}
Call notes: {state.get('call_notes') or ''}
User overrides: {state.get('user_overrides') or []}
Return a JSON object matching the schema.
"""
    structured = await provider.structured_output(
        system_prompt=SYSTEM_PROMPT,
        user_content=prompt,
        output_schema=ProposalOutput,
        temperature=0.1,
    )
    output = structured or _fallback(state)
    if not output.client_problem_restatement:
        analysis = state.get("rfp_analysis") or {}
        output.client_problem_restatement = (
            f"{state.get('session_title') or 'the RFP'} is asking for a controlled way to solve: "
            f"{analysis.get('business_problem') or 'the stated business problem'}."
        )
    output.compliance_matrix = _build_compliance_matrix(state.get("rfp_analysis") or {}, output.proposed_solution)
    override_text = _override_text(state)
    if override_text and not any(override_text in flag for flag in output.consistency_flags):
        output.consistency_flags.append(f"Human override reflected in final narrative: {override_text}.")
    payload = output.model_dump()
    generated_by = "llm" if structured else "deterministic_fallback"
    payload["generated_by"] = generated_by
    if structured:
        warn_if_generic_agent_output("proposal", state, payload)
    payload["confidence"] = calculate_agent_confidence(
        agent="proposal",
        state=state,
        payload=payload,
        generated_by=generated_by,
    )
    return {"proposal_output": payload}
