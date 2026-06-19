from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.war_room.llm_provider import get_war_room_llm_provider


class CompetitorOutput(BaseModel):
    differentiators: list[str] = Field(default_factory=list)
    win_themes: list[str] = Field(default_factory=list)
    competitive_risks: list[str] = Field(default_factory=list)
    value_proposition: str
    executive_messaging: str
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


def _fallback(state: dict[str, Any]) -> CompetitorOutput:
    analysis = state.get("rfp_analysis") or {}
    similar_projects = state.get("similar_projects") or []
    session_title = str(state.get("session_title") or "the RFP")
    tags = [str(tag).replace("_", " ") for tag in (analysis.get("domain_tags") or [])[:4]]
    strongest = similar_projects[0]["title"] if similar_projects else "internal delivery evidence"
    return CompetitorOutput(
        differentiators=[
            f"Grounded proposal strategy backed by internal evidence for {session_title}.",
            "Human-in-the-loop scope control before fixed commitments.",
            "Modular delivery model that keeps cost and risk visible.",
            f"Positioning aligned to {', '.join(tags) if tags else 'the stated opportunity'}.",
        ],
        win_themes=[
            "credible delivery plan",
            "lower execution risk",
            "faster path to business value",
            "clear assumptions and commercial discipline",
        ],
        competitive_risks=[
            f"Competitors may undercut price by hiding assumptions on {session_title}.",
            "Generic AI proposals may miss buyer-specific risks.",
        ],
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
    prompt = f"""
You are the Competitor Strategist Agent.
Architect output: {state.get('architect_output') or {}}
CFO output: {state.get('cfo_output') or {}}
Similar projects: {state.get('similar_projects') or []}
User overrides: {state.get('user_overrides') or []}
Return a JSON object matching the schema.
"""
    structured = await provider.structured_output(
        system_prompt="You develop proposal positioning and win themes.",
        user_content=prompt,
        output_schema=CompetitorOutput,
        temperature=0.1,
    )
    output = structured or _fallback(state)
    return {"competitor_output": output.model_dump()}
