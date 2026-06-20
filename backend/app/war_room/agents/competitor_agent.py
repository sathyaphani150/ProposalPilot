from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.war_room.confidence import calculate_agent_confidence
from app.war_room.llm_provider import get_war_room_llm_provider

SYSTEM_PROMPT = """
You are the Competitor Strategist on an internal proposal war room team.
You bring experience reading RFP evaluation signals and positioning bids
to win, not just listing generic strengths.

Ground every claim in the RFP analysis, retrieved past-project matches,
and call notes. Do not name or imply knowledge of specific real competitor
companies unless one is explicitly named in the RFP text or call notes -
speak in terms of competitor archetypes (e.g. "a generalist systems
integrator", "a point-solution vendor", "an offshore low-cost provider")
grounded in what the RFP is actually asking for.

EVALUATION SIGNAL INFERENCE - if the RFP text or analysis suggests how
proposals will be scored (emphasis on price, technical depth, prior
experience, or timeline), infer which dimension the evaluator likely
weighs most and lead your positioning with that dimension.

POSITIONING STRATEGY - pick ONE primary stance and justify it against the
RFP's actual signals, don't hedge across all of them:
- Price leader: justify only if the RFP signals cost sensitivity.
- Technical/quality leader: justify with specific technical depth tied to
  the architect's output.
- Risk-reduction specialist: justify with evidence of a low-risk delivery
  approach (relevant past matches, clear methodology).
- Domain-niche specialist: justify only if a retrieved match shows real
  domain-specific experience.

OBJECTION PRE-EMPTION - identify the single most likely doubt an evaluator
would have about us winning this (e.g. "no direct experience in this
specific domain") and address it proactively rather than waiting to be
asked.

differentiators: each item must trace to either a retrieved past-project
match (name which one) or a stated capability - not aspirational claims.
Max 5 items.
win_themes: max 4, each a one-sentence theme tied to a specific RFP
requirement or evaluation signal.
competitive_risks: name the specific RFP signal creating the risk. Max 5.

If human_overrides includes positioning guidance (e.g. "use our
recruitment project story"), it must appear directly in differentiators.

OUTPUT FIELDS:
- positioning_strategy: one of the four stances above, one sentence why.
- differentiators, win_themes, competitive_risks: as above.

Return JSON matching the schema.
"""


class CompetitorOutput(BaseModel):
    positioning_strategy: str = ""
    differentiators: list[str] = Field(default_factory=list)
    win_themes: list[str] = Field(default_factory=list)
    competitive_risks: list[str] = Field(default_factory=list)
    value_proposition: str
    executive_messaging: str
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


def _fallback(state: dict[str, Any]) -> CompetitorOutput:
    analysis = state.get("rfp_analysis") or {}
    architect = state.get("architect_output") or {}
    similar_projects = state.get("similar_projects") or []
    session_title = str(state.get("session_title") or "the RFP")
    tags = [str(tag).replace("_", " ") for tag in (analysis.get("domain_tags") or [])[:4]]
    override_text = _override_text(state)
    strongest = similar_projects[0]["title"] if similar_projects else "internal delivery evidence"
    pricing_signals = " ".join(str(item) for item in (analysis.get("timeline_risks") or []) + (analysis.get("missing_information") or []))
    positioning_strategy = "Risk-reduction specialist: the opportunity benefits from a controlled delivery posture because unresolved scope and delivery questions remain."
    if similar_projects and tags:
        positioning_strategy = f"Domain-niche specialist: use {strongest} to prove relevant delivery experience in {tags[0]}."
    elif any(term in pricing_signals.lower() for term in ["budget", "cost", "price"]):
        positioning_strategy = "Price leader: the evaluator appears cost-sensitive, so commercial predictability should lead the narrative."
    elif architect.get("architecture_pattern"):
        positioning_strategy = "Technical/quality leader: the bid can lead with a concrete architecture and implementation discipline rather than generic claims."
    return CompetitorOutput(
        positioning_strategy=positioning_strategy,
        differentiators=[
            f"Grounded proposal strategy backed by internal evidence for {session_title}.",
            "Human-in-the-loop scope control before fixed commitments.",
            f"Technical direction anchored in {architect.get('architecture_pattern') or 'a concrete buildable architecture'}.",
            f"Positioning aligned to {', '.join(tags) if tags else 'the stated opportunity'}.",
            *([f"Positioning override applied: {override_text}."] if override_text else []),
        ][:5],
        win_themes=[
            "Lead with credible delivery proof tied to the buyer's stated requirements.",
            "Reduce execution risk by making assumptions, controls, and dependencies explicit.",
            "Show a faster path to business value through scoped delivery phases.",
            "Use commercial discipline as a differentiator rather than burying it in pricing detail.",
        ][:4],
        competitive_risks=[
            f"Competitors may undercut price by hiding assumptions around {', '.join(str(item) for item in (analysis.get('integration_needs') or [])[:2]) or 'integration scope'}.",
            f"Limited directly proven experience in {tags[0] if tags else 'this niche'} could become an evaluator concern without strong evidence mapping.",
        ][:5],
        value_proposition=(
            f"Use {strongest} as proof that the team can deliver adjacent work, then differentiate on process rigor and delivery control for {session_title}."
        ),
        executive_messaging=(
            f"We understand the buyer's business risk in {session_title} and can turn uncertainty into a controlled proposal and delivery plan."
        ),
        reasoning="Differentiation is anchored in evidence, not novelty claims.",
    )


async def run_competitor_agent(state: dict[str, Any]) -> dict[str, Any]:
    provider = get_war_room_llm_provider()
    analysis = state.get("rfp_analysis") or {}
    prompt = f"""
{SYSTEM_PROMPT}

Architect output: {state.get('architect_output') or {}}
CFO output: {state.get('cfo_output') or {}}
RFP analysis: {analysis}
Call notes: {state.get('call_notes') or ''}
Similar projects: {state.get('similar_projects') or []}
User overrides: {state.get('user_overrides') or []}
Return a JSON object matching the schema.
"""
    structured = await provider.structured_output(
        system_prompt=SYSTEM_PROMPT,
        user_content=prompt,
        output_schema=CompetitorOutput,
        temperature=0.1,
    )
    output = structured or _fallback(state)
    payload = output.model_dump()
    generated_by = "llm" if structured else "deterministic_fallback"
    payload["generated_by"] = generated_by
    payload["confidence"] = calculate_agent_confidence(
        agent="competitor",
        state=state,
        payload=payload,
        generated_by=generated_by,
    )
    return {"competitor_output": payload}
