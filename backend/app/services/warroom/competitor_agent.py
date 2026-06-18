from __future__ import annotations

import json
from typing import Any

from loguru import logger
from pydantic import Field

from app.services.llm_service import get_llm_service
from app.services.warroom.base import AgentResult, _clean_list, guidance_text


class CompetitorResult(AgentResult):
    agent_name: str = Field(default="competitor")
    competitors: list[str] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
    win_strategy: list[str] = Field(default_factory=list)


def _fallback_result(
    rfp_summary: str,
    guidance: list[str] | None,
) -> CompetitorResult:
    guidance_items = _clean_list(guidance, max_items=5)
    differentiators = [
        "Grounded delivery approach with explicit assumptions and validation points.",
        "Clear path from discovery to proposal to implementation without over-engineering.",
        "Ability to tailor scope around client guidance and budget constraints.",
    ]
    if guidance_items:
        differentiators.append(f"User guidance applied: {'; '.join(guidance_items[:3])}.")
    return CompetitorResult(
        summary="Competitive positioning and win themes for the opportunity.",
        recommendations=["Lead with credibility, simplification, and measurable outcomes."],
        risks=["Generic competitors may overpromise and under-specify delivery controls."],
        competitors=["Incumbent SI", "Large offshore integrator", "Niche platform partner"],
        differentiators=differentiators,
        win_strategy=[
            "Use architecture and delivery realism as the primary win theme.",
            "Show how guidance has reduced cost and complexity without compromising outcomes.",
            f"Reference the buyer context carefully: {rfp_summary[:220]}",
        ],
    )


async def run_competitor_agent(
    *,
    rfp_summary: str,
    architect_result: dict[str, Any],
    cfo_result: dict[str, Any],
    guidance: list[str] | None = None,
) -> CompetitorResult:
    prompt = """
You are a proposal strategist.

Identify:

- Potential competitors
- Competitive advantages
- Win themes
- Differentiators

Return JSON only.
"""
    payload = {
        "rfp_summary": rfp_summary,
        "architect_result": architect_result,
        "cfo_result": cfo_result,
        "additional_user_guidance": guidance or [],
        "guidance_text": guidance_text(guidance),
    }
    try:
        result = await get_llm_service().structured_extract(
            system_prompt=prompt.strip(),
            user_content=json.dumps(payload, ensure_ascii=False),
            output_schema=CompetitorResult,
            temperature=0.1,
        )
        return result
    except Exception as exc:
        logger.warning(f"Competitor agent fell back to heuristics: {exc}")
        return _fallback_result(rfp_summary, guidance)
