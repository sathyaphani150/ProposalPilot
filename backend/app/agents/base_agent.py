# backend/app/agents/base_agent.py
"""
ProposalPilot AI — Base Agent Utilities
Common functionality, prompt templates, and LLM configuration for all War Room agents.
"""

from typing import Any, Dict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from app.services.llm_service import get_llm_service
from app.agents.error_handler import agent_retry, log_agent_execution


class BaseAgent:
    """Base class with common methods for all War Room agents."""

    def __init__(self, model_name: str = "llama-3.3-70b-versatile"):
        self.model_name = model_name

    def get_llm(self, temperature: float = 0.1, streaming: bool = False) -> BaseChatModel:
        """Get configured LLM for this agent."""
        return get_llm_service().get_chat_model(
            temperature=temperature,
            streaming=streaming,
        )

    @agent_retry(max_attempts=3)
    async def invoke_with_context(
        self,
        system_prompt: str,
        user_input: str,
        context: Dict[str, Any],
        temperature: float = 0.1,
    ) -> str:
        """Invoke LLM with structured context (RFP + RAG + overrides)."""
        log_agent_execution(self.__class__.__name__.replace("Agent", "").lower(), context)

        llm = self.get_llm(temperature=temperature)

        context_str = self._format_context(context)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"{user_input}\n\n=== AVAILABLE CONTEXT ===\n{context_str}"),
        ]

        try:
            response = await llm.ainvoke(messages)
            return str(response.content).strip()
        except Exception as e:
            logger.error(f"LLM invocation failed in {self.__class__.__name__}: {e}")
            raise


    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format all available context for the LLM."""
        parts = []

        if "rfp_analysis" in context:
            rfp = context["rfp_analysis"]
            parts.append(f"**RFP Business Problem:** {rfp.get('business_problem', 'N/A')}")
            parts.append(f"**Domain:** {', '.join(rfp.get('domain_tags', []))}")
            parts.append(f"**Key Requirements:** {rfp.get('functional_requirements', [])}")

        if "retrieved_context" in context and context["retrieved_context"]:
            parts.append("\n**RELEVANT PAST PROJECTS:**")
            for item in context["retrieved_context"][:5]:
                parts.append(f"- {item.get('title', 'Untitled')}: {item.get('text', '')[:350]}...")

        if "call_notes" in context and context["call_notes"]:
            parts.append(f"\n**CALL NOTES:**\n{context['call_notes']}")

        if "human_overrides" in context and context["human_overrides"]:
            parts.append(f"\n**HUMAN OVERRIDES:**\n{context['human_overrides']}")

        return "\n\n".join(parts)

# Reusable System Prompts
AGENT_SYSTEM_PROMPTS = {
    "architect": """You are the **Tech Architect Agent** for ProposalPilot AI.
You design scalable, secure, and delivery-ready technical solutions based on the RFP and past project experience.
Always ground your recommendations in retrieved past projects when possible.
Focus on: architecture patterns, tech stack, integration strategy, reusability, risks, and feasibility.""",

    "cfo": """You are the **CFO / Commercial Agent** for ProposalPilot AI.
You provide realistic costing, resource planning, margin analysis, and commercial risk assessment.
Use standard Cognine rate cards and delivery models (onshore/offshore).
Always provide minimum / recommended / maximum pricing ranges.""",

    "competitor": """You are the **Competitor Strategist Agent** for ProposalPilot AI.
You analyze competitive landscape, highlight our differentiators, and craft win themes.
Emphasize Cognine's strengths: engineering excellence, AI-driven delivery, domain expertise.""",

    "proposal": """You are the **Proposal Writer Agent** for ProposalPilot AI.
You synthesize all agent outputs into a coherent, professional, and compliant proposal narrative.
Ensure consistency, clear value proposition, and strong storytelling.""",
}
