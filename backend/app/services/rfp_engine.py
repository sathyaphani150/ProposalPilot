"""
ProposalPilot AI — RFP Understanding Engine
Structured LLM extraction of RFP documents into typed schema.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from loguru import logger

from app.services.llm_service import get_llm_service


# ── Output Schema ─────────────────────────────────────────────────────────
class RFPExtractionOutput(BaseModel):
    """Structured output from RFP analysis — strict schema for JSON mode."""

    business_problem: str = Field(
        description="Core business problem the client is trying to solve (1-3 sentences)"
    )
    functional_requirements: list[str] = Field(
        default_factory=list,
        description="List of explicit functional requirements from the RFP",
    )
    non_functional_requirements: list[str] = Field(
        default_factory=list,
        description="Performance, scalability, security, compliance NFRs",
    )
    data_needs: list[str] = Field(
        default_factory=list,
        description="Data sources, data volumes, data types mentioned",
    )
    integration_needs: list[str] = Field(
        default_factory=list,
        description="Systems, APIs, or services the solution must integrate with",
    )
    compliance_needs: list[str] = Field(
        default_factory=list,
        description="Regulatory, legal, or compliance requirements (GDPR, SOC2, etc.)",
    )
    timeline_risks: list[str] = Field(
        default_factory=list,
        description="Timeline constraints, deadlines, or schedule risks",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Critical information absent from the RFP that must be clarified",
    )
    scope_boundaries: list[str] = Field(
        default_factory=list,
        description="What is explicitly in-scope and out-of-scope",
    )
    domain_tags: list[str] = Field(
        default_factory=list,
        description="Domain/industry tags: fintech, healthcare, ecommerce, etc.",
    )
    estimated_complexity: str = Field(
        description="Overall complexity: low | medium | high | very_high"
    )


_SYSTEM_PROMPT = """\
You are an expert pre-sales solutions architect and RFP analyst at a top-tier technology consulting firm.
Your task is to perform a thorough, structured analysis of the provided RFP or client requirements document.

Extract all information precisely from the document. Do NOT invent or hallucinate details.
If a category has no information in the document, return an empty list or a note that it was not mentioned.

Be specific and actionable in your extractions — avoid vague statements.
For missing_information, focus on critical gaps that would prevent accurate scoping or estimation.
"""


async def analyze_rfp_document(raw_text: str) -> dict[str, Any]:
    """
    Run the RFP Understanding Engine on extracted document text.

    Args:
        raw_text: Clean text extracted from the uploaded RFP document.

    Returns:
        Dict matching the RFPAnalysis model fields.

    Raises:
        LLMExtractionError: If the LLM extraction fails after retries.
    """
    llm_service = get_llm_service()

    user_content = f"""
Analyze the following RFP / client requirements document:

<document>
{raw_text[:15_000]}  
</document>

Extract all required fields. Be precise, factual, and grounded in the document text.
"""

    logger.info(f"Running RFP extraction on {len(raw_text)} chars of text")

    result: RFPExtractionOutput = await llm_service.structured_extract(
        system_prompt=_SYSTEM_PROMPT,
        user_content=user_content,
        output_schema=RFPExtractionOutput,
        temperature=0.0,
    )

    return {
        "business_problem": result.business_problem,
        "functional_requirements": result.functional_requirements,
        "non_functional_requirements": result.non_functional_requirements,
        "data_needs": result.data_needs,
        "integration_needs": result.integration_needs,
        "compliance_needs": result.compliance_needs,
        "timeline_risks": result.timeline_risks,
        "missing_information": result.missing_information,
        "scope_boundaries": result.scope_boundaries,
        "domain_tags": result.domain_tags,
        "estimated_complexity": result.estimated_complexity,
        "raw_llm_output": result.model_dump(),
    }
