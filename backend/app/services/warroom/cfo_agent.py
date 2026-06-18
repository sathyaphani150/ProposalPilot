from __future__ import annotations

import json
from typing import Any

from loguru import logger
from pydantic import Field

from app.services.llm_service import get_llm_service
from app.services.warroom.base import AgentResult, _clean_list, guidance_text


class CFOResult(AgentResult):
    agent_name: str = Field(default="cfo")
    team_size: int
    effort_months: int
    estimated_cost: str
    cost_risks: list[str] = Field(default_factory=list)
    delivery_model: str


def _fallback_result(
    architect_result: dict[str, Any],
    guidance: list[str] | None,
) -> CFOResult:
    stack = _clean_list(architect_result.get("technology_stack"), max_items=4)
    team_size = 5 + min(len(stack), 3)
    effort_months = 3 + min(len(stack), 4)
    cost = f"USD {team_size * effort_months * 18000:,.0f}"
    risks = [
        "Integration complexity can materially change effort and budget.",
        "Delay in client decisions will push the schedule and inflate delivery cost.",
    ]
    if guidance:
        guidance_items = _clean_list(guidance, max_items=4)
        if any("mvp" in item.lower() for item in guidance_items):
            team_size = max(3, team_size - 2)
            effort_months = max(2, effort_months - 1)
            cost = f"USD {team_size * effort_months * 16000:,.0f}"
            risks.append("MVP scope reduction may reduce delivery risk but increase phase-2 dependency.")
    return CFOResult(
        summary="Planning estimate for delivery capacity and commercial risk.",
        recommendations=["Validate scope, integrations, and acceptance criteria before pricing."],
        risks=risks,
        team_size=team_size,
        effort_months=effort_months,
        estimated_cost=cost,
        cost_risks=risks,
        delivery_model="Hybrid delivery with strong solution and delivery governance.",
    )


async def run_cfo_agent(
    *,
    architect_result: dict[str, Any],
    guidance: list[str] | None = None,
) -> CFOResult:
    prompt = """
You are a delivery and finance director.

Estimate:

- Team size
- Duration
- Cost estimate
- Delivery risks

Return JSON only.
"""
    payload = {
        "architect_result": architect_result,
        "additional_user_guidance": guidance or [],
        "guidance_text": guidance_text(guidance),
    }
    try:
        result = await get_llm_service().structured_extract(
            system_prompt=prompt.strip(),
            user_content=json.dumps(payload, ensure_ascii=False),
            output_schema=CFOResult,
            temperature=0.1,
        )
        return result
    except Exception as exc:
        logger.warning(f"CFO agent fell back to heuristics: {exc}")
        return _fallback_result(architect_result, guidance)
