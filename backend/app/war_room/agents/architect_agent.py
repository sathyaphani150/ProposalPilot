from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.war_room.llm_provider import get_war_room_llm_provider

SYSTEM_PROMPT = """
You are the Tech Architect on an internal proposal war room team.

EVIDENCE HIERARCHY - use in this order:
1. RFP analysis fields - ground truth.
2. Retrieved past-project matches - only claim reuse tied to a specific matched project; never imply experience not present in a match.
3. Call notes - client-confirmed, trust above your own inference.
4. Your own inference - only to fill structural gaps, and it MUST go in `assumptions`, never stated as fact elsewhere in the output.

If human_overrides contains architecture guidance, apply it and state in one sentence what changed because of it.

- architecture_summary: name the actual core workflow, 2-4 sentences.
- recommended_stack: max 6 items, each tied to a stated requirement.
- reusable_components: empty list if no retrieved match supports reuse - do not pad this list with generic claims.
- assumptions: every tier-4 inference goes here, nowhere else.

Return JSON matching the schema.
"""


class ArchitectOutput(BaseModel):
    architecture_summary: str
    recommended_stack: list[str] = Field(default_factory=list)
    reusable_components: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    technical_risks: list[str] = Field(default_factory=list)
    validation_questions: list[str] = Field(default_factory=list)
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


def _fallback(state: dict[str, Any]) -> ArchitectOutput:
    analysis = state.get("rfp_analysis") or {}
    context = state.get("similar_projects") or []
    session_title = str(state.get("session_title") or "the RFP")
    client_name = str(state.get("client_name") or "the client")
    business_problem = str(analysis.get("business_problem") or "an unclarified proposal opportunity")
    domain_tags = [str(tag).replace("_", " ") for tag in (analysis.get("domain_tags") or [])[:4]]
    override_text = _override_text(state)
    stack = ["FastAPI", "PostgreSQL", "LangGraph", "Qdrant"]
    if analysis.get("integration_needs"):
        stack.append("Adapter layer")
    if any("search" in tag.lower() or "retrieval" in tag.lower() for tag in domain_tags):
        stack.append("Semantic retrieval pipeline")
    if any("data" in tag.lower() or "analytics" in tag.lower() for tag in domain_tags):
        stack.append("Governed data services")
    if any("security" in tag.lower() or "compliance" in tag.lower() for tag in domain_tags):
        stack.append("Security control plane")
    return ArchitectOutput(
        architecture_summary=(
            f"Use an API-first modular architecture for {session_title} at {client_name}. "
            f"The current business problem is: {business_problem}. "
            "Keep workflow, retrieval, proposal assembly, and integration boundaries explicit so delivery can stay modular and controllable. "
            "Avoid over-engineering until scale, compliance, and source-system readiness are confirmed."
            + (f" Human override applied: {override_text}." if override_text else "")
        ),
        recommended_stack=stack[:6],
        reusable_components=[
            *[
                f"{project.get('title')} pattern"
                for project in (state.get("similar_projects") or [])[:2]
                if isinstance(project, dict) and project.get("title")
            ],
            "retrieval service",
            "document parsing pipeline",
            "proposal assembly templates",
            "agent state persistence",
        ][:6],
        assumptions=[
            f"{client_name} will confirm integration access and data ownership.",
            "Initial delivery can start with a modular monolith and evolve selectively.",
            f"Domain focus: {', '.join(domain_tags) if domain_tags else 'general proposal workflow'}.",
        ],
        technical_risks=[
            *(
                item
                for item in [
                    "Unverified external APIs can delay delivery." if analysis.get("integration_needs") else "",
                    "Compliance and security controls may require dedicated implementation time." if analysis.get("compliance_needs") else "",
                    "Weak retrieval evidence can reduce proposal credibility." if context else "",
                ]
                if item
            ),
            *[f"Timeline risk: {item}" for item in (analysis.get("timeline_risks") or [])[:2]],
        ],
        validation_questions=[
            f"Which systems are authoritative for the {', '.join(domain_tags[:2]) if domain_tags else 'core'} data domains?",
            "What non-functional requirements are truly mandatory for go-live?",
            "Which reusable assets from prior projects are most relevant to this opportunity?",
            f"What specifically makes {session_title} different from other opportunities in the pipeline?",
        ],
        reasoning=(
            f"Architecture decisions are grounded in {len(context)} context items, {len(domain_tags)} domain tags, and complexity {analysis.get('estimated_complexity') or 'medium'}."
            + (f" Override changed the scope toward: {override_text}." if override_text else "")
        ),
        confidence=0.78,
    )


async def run_architect_agent(state: dict[str, Any]) -> dict[str, Any]:
    provider = get_war_room_llm_provider()
    analysis = state.get("rfp_analysis") or {}
    prompt = f"""
{SYSTEM_PROMPT}

RFP analysis: {analysis}
Retrieved context: {state.get('retrieved_context') or []}
Call notes: {state.get('call_notes') or ''}
User overrides: {state.get('user_overrides') or []}
Return a JSON object matching the schema.
"""
    structured = await provider.structured_output(
        system_prompt=SYSTEM_PROMPT,
        user_content=prompt,
        output_schema=ArchitectOutput,
        temperature=0.1,
    )
    output = structured or _fallback(state)
    return {"architect_output": output.model_dump()}
