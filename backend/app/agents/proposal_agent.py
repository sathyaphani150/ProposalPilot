# backend/app/agents/proposal_agent.py
"""
ProposalPilot AI — Proposal Writer Agent
Synthesizes all previous agent outputs into a professional, cohesive proposal draft.
"""

from typing import Any, Dict

from loguru import logger

from app.agents.base_agent import BaseAgent, AGENT_SYSTEM_PROMPTS
from app.agents.state import WarRoomState
from app.agents.rag_tool import search_rag


class ProposalAgent(BaseAgent):
    """Proposal Writer specialized agent."""

    def __init__(self):
        super().__init__(model_name="llama-3.3-70b-versatile")

    async def proposal_node(self, state: WarRoomState) -> Dict[str, Any]:
        """
        Main node for the Proposal Writer Agent.
        """
        logger.info("✍️ Proposal Writer Agent started")

        # 1. Gather all previous outputs
        all_context = await search_rag(
            query="proposal structure executive summary compliance best practices",
            limit=4,
        )
        state.retrieved_context.extend(all_context)

        # 2. Build rich context
        context = {
            "rfp_analysis": state.rfp_analysis,
            "retrieved_context": state.retrieved_context,
            "call_notes": state.call_notes,
            "human_overrides": state.human_overrides,
            "architect_output": state.architect_output or "Not available",
            "cfo_output": state.cfo_output or "Not available",
            "competitor_output": state.competitor_output or "Not available",
        }

        # 3. Prompts
        system_prompt = AGENT_SYSTEM_PROMPTS["proposal"]

        user_prompt = f"""
Synthesize all agent outputs into a high-quality, cohesive proposal section.

Available Inputs:
- RFP Analysis
- Architect Recommendation
- CFO Commercial Plan
- Competitor Strategy
- Human Overrides: {state.human_overrides.get('guidance', 'None')}

Generate a professional proposal narrative covering:
- Executive Summary
- Client Problem Statement
- Proposed Solution & Architecture
- Relevant Past Experience
- Commercial Proposal (Cost + Resources)
- Competitive Advantage
- Risks, Assumptions & Mitigations
- Next Steps / Call to Action

Ensure consistency across all sections and strong storytelling.
"""

        # 4. Generate final proposal draft
        output = await self.invoke_with_context(
            system_prompt=system_prompt,
            user_input=user_prompt,
            context=context,
            temperature=0.18,
        )

        # 5. Update state
        state.proposal_output = output
        state.is_complete = True

        logger.info("✅ Proposal Writer Agent completed - War Room synthesis done")

        return {
            "proposal_output": output,
            "is_complete": True,
            "messages": [{"role": "proposal", "content": output[:600] + "..."}]
        }


# For direct testing
async def run_proposal(state: WarRoomState) -> Dict[str, Any]:
    agent = ProposalAgent()
    return await agent.proposal_node(state)
