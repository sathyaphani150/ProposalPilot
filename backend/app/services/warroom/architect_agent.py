from __future__ import annotations

import json
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from app.services.llm_service import get_llm_service
from app.services.warroom.base import AgentResult, _clean_list, guidance_text


class ArchitectResult(AgentResult):
    agent_name: str = Field(default="architect")
    solution_design: str
    technology_stack: list[str] = Field(default_factory=list)
    architecture_summary: str
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


def _fallback_result(
    rfp_summary: str,
    architecture_recommendation: dict[str, Any],
    guidance: list[str] | None,
) -> ArchitectResult:
    architecture_text = str(architecture_recommendation.get("architecture") or "").strip()
    components = _clean_list(architecture_recommendation.get("reusable_components"), max_items=6)
    assumptions = _clean_list(architecture_recommendation.get("assumptions"), max_items=6)
    validation_questions = _clean_list(architecture_recommendation.get("validation_questions"), max_items=6)
    design = architecture_text or (
        "Use a modular API-first architecture with a presentation layer, orchestration services, "
        "integration adapters, and governed data/reporting components."
    )
    if guidance:
        design += f" User guidance indicates: {'; '.join(_clean_list(guidance, max_items=4))}."
    return ArchitectResult(
        summary="Principal architecture direction for the proposal.",
        recommendations=validation_questions[:4] or components[:4],
        risks=[
            "Validate external system access and deployment constraints before locking the design.",
            "Keep the delivery boundary simple until scope and platform decisions are confirmed.",
        ],
        solution_design=design,
        technology_stack=components[:6] or ["API layer", "Workflow services", "Integration adapters", "Reporting"],
        architecture_summary=f"{architecture_text or design} Based on RFP summary: {rfp_summary[:280]}",
        assumptions=assumptions or ["Architecture should be confirmed with the client before final proposal sign-off."],
    )


async def run_architect_agent(
    *,
    rfp_summary: str,
    architecture_recommendation: dict[str, Any],
    guidance: list[str] | None = None,
) -> ArchitectResult:
    prompt = """
You are a principal solution architect.

Design the solution architecture.

Consider:
- Client requirements
- Architecture recommendation
- User guidance

Return JSON only.
"""
    payload = {
        "rfp_summary": rfp_summary,
        "architecture_recommendation": architecture_recommendation,
        "additional_user_guidance": guidance or [],
        "guidance_text": guidance_text(guidance),
    }
    try:
        result = await get_llm_service().structured_extract(
            system_prompt=prompt.strip(),
            user_content=json.dumps(payload, ensure_ascii=False),
            output_schema=ArchitectResult,
            temperature=0.1,
        )
        return result
    except Exception as exc:
        logger.warning(f"Architect agent fell back to heuristics: {exc}")
        return _fallback_result(rfp_summary, architecture_recommendation, guidance)
