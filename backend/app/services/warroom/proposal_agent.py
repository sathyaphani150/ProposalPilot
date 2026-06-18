from __future__ import annotations

import json
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from app.services.llm_service import get_llm_service
from app.services.warroom.base import AgentResult, _clean_list, guidance_text
from app.services.warroom.architect_agent import ArchitectResult
from app.services.warroom.cfo_agent import CFOResult
from app.services.warroom.competitor_agent import CompetitorResult


class ProposalDraft(AgentResult):
    agent_name: str = Field(default="proposal")
    executive_summary: str
    solution_overview: str
    differentiators: list[str] = Field(default_factory=list)


def _fallback_result(
    rfp_summary: str,
    architect_result: dict[str, Any],
    cfo_result: dict[str, Any],
    competitor_result: dict[str, Any],
    guidance: list[str] | None,
) -> ProposalDraft:
    differentiators = _clean_list(competitor_result.get("differentiators"), max_items=5)
    if guidance:
        differentiators.extend(_clean_list(guidance, max_items=4))
    architecture = str(architect_result.get("architecture_summary") or architect_result.get("solution_design") or "").strip()
    cost = str(cfo_result.get("estimated_cost") or "Commercial estimate pending").strip()
    return ProposalDraft(
        summary="Draft proposal bringing architecture, delivery, and win strategy together.",
        recommendations=["Package the story around outcomes, clarity, and controlled risk."],
        risks=_clean_list(cfo_result.get("cost_risks"), max_items=5),
        executive_summary=f"Proposal built from the RFP context and grounded delivery evidence. {rfp_summary[:220]}",
        solution_overview=f"{architecture} Commercial planning case: {cost}.",
        differentiators=differentiators[:6] or [
            "Grounded proposal narrative",
            "Guidance-aware delivery plan",
            "Explicit cost and risk controls",
        ],
    )


async def run_proposal_agent(
    *,
    rfp_summary: str,
    architect_result: ArchitectResult | dict[str, Any],
    cfo_result: CFOResult | dict[str, Any],
    competitor_result: CompetitorResult | dict[str, Any],
    guidance: list[str] | None = None,
) -> ProposalDraft:
    prompt = """
You are a proposal writer.

Generate a proposal draft using all agent outputs.

Return structured JSON.
"""
    payload = {
        "rfp_summary": rfp_summary,
        "architect_result": architect_result.model_dump() if isinstance(architect_result, ArchitectResult) else architect_result,
        "cfo_result": cfo_result.model_dump() if isinstance(cfo_result, CFOResult) else cfo_result,
        "competitor_result": competitor_result.model_dump() if isinstance(competitor_result, CompetitorResult) else competitor_result,
        "additional_user_guidance": guidance or [],
        "guidance_text": guidance_text(guidance),
    }
    try:
        result = await get_llm_service().structured_extract(
            system_prompt=prompt.strip(),
            user_content=json.dumps(payload, ensure_ascii=False),
            output_schema=ProposalDraft,
            temperature=0.1,
        )
        return result
    except Exception as exc:
        logger.warning(f"Proposal agent fell back to heuristics: {exc}")
        return _fallback_result(rfp_summary, payload["architect_result"], payload["cfo_result"], payload["competitor_result"], guidance)
