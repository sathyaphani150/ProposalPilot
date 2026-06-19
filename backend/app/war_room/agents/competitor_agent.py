from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.war_room.llm_provider import get_war_room_llm_provider

SYSTEM_PROMPT = """
You are the Competitor Strategist on an internal proposal war room team.

Ground every claim in the RFP analysis, retrieved past-project matches, and call notes. Do not name or imply knowledge of specific real competitor companies unless one is explicitly named in the RFP text or call notes - speak in terms of competitor archetypes (e.g. "a generalist systems integrator", "a point-solution vendor") grounded in what the RFP is actually asking for.

differentiators: each item must trace to either a retrieved past-project match (name which one) or a stated capability - not aspirational claims. Max 5 items.
win_themes: max 4, each a one-sentence theme tied to a specific RFP requirement or evaluation signal, not generic "we deliver quality."
competitive_risks: name the specific RFP signal that creates the risk (e.g. a tight timeline, an unusual compliance ask) - not vague caution. Max 5 items.

If human_overrides includes positioning guidance (e.g. "use our recruitment project story"), it must appear directly in differentiators.

Return JSON matching the schema.
"""


class CompetitorOutput(BaseModel):
    differentiators: list[str] = Field(default_factory=list)
    win_themes: list[str] = Field(default_factory=list)
    competitive_risks: list[str] = Field(default_factory=list)
    value_proposition: str
    executive_messaging: str
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
    call_notes = state.get("call_notes")
    if isinstance(call_notes, str) and call_notes.strip():
        parts.append(call_notes.strip())
    return " | ".join(parts)


def _fallback(state: dict[str, Any]) -> CompetitorOutput:
    analysis = state.get("rfp_analysis") or {}
    similar_projects = state.get("similar_projects") or []
    session_title = str(state.get("session_title") or "the RFP")
    tags = [str(tag).replace("_", " ") for tag in (analysis.get("domain_tags") or [])[:4]]
    override_text = _override_text(state)
    strongest = similar_projects[0]["title"] if similar_projects else "internal delivery evidence"
    return CompetitorOutput(
        differentiators=[
            f"Grounded proposal strategy backed by internal evidence for {session_title}.",
            "Human-in-the-loop scope control before fixed commitments.",
            "Modular delivery model that keeps cost and risk visible.",
            f"Positioning aligned to {', '.join(tags) if tags else 'the stated opportunity'}.",
            *([f"Positioning override applied: {override_text}."] if override_text else []),
        ][:5],
        win_themes=[
            "credible delivery plan",
            "lower execution risk",
            "faster path to business value",
            "clear assumptions and commercial discipline",
        ][:4],
        competitive_risks=[
            f"Competitors may undercut price by hiding assumptions on {session_title}.",
            "Generic AI proposals may miss buyer-specific risks.",
        ][:5],
        value_proposition=(
            f"Use {strongest} as proof that the team can deliver adjacent work, then differentiate on process rigor and delivery control for {session_title}."
        ),
        executive_messaging=(
            f"We understand the buyer's business risk in {session_title} and can turn uncertainty into a controlled proposal and delivery plan."
        ),
        reasoning="Differentiation is anchored in evidence, not novelty claims.",
        confidence=0.77,
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
    return {"competitor_output": output.model_dump()}
