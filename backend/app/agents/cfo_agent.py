# backend/app/agents/cfo_agent.py
"""
ProposalPilot AI — CFO / Commercial Agent
Responsible for resource estimation, costing, margin analysis, and commercial strategy.
"""

from typing import Any, Dict

from loguru import logger

from app.agents.base_agent import BaseAgent, AGENT_SYSTEM_PROMPTS
from app.agents.state import WarRoomState
from app.agents.rag_tool import search_rag


class CFOAgent(BaseAgent):
    """CFO / Pricing specialized agent."""

    def __init__(self):
        super().__init__(model_name="llama-3.3-70b-versatile")

    async def cfo_node(self, state: WarRoomState) -> Dict[str, Any]:
        """
        Main node for the CFO Agent.
        """
        logger.info("💰 CFO Agent started")

        # 1. Retrieve commercial / past project context
        commercial_context = await search_rag(
            query="past project costing resource allocation delivery model margin",
            item_type="project",
            limit=5,
        )
        state.retrieved_context.extend(commercial_context)

        # 2. Build context
        context = {
            "rfp_analysis": state.rfp_analysis,
            "retrieved_context": state.retrieved_context,
            "call_notes": state.call_notes,
            "human_overrides": state.human_overrides,
            "architect_output": state.architect_output or "No architecture output yet.",
        }

        # 3. Prompts
        system_prompt = AGENT_SYSTEM_PROMPTS["cfo"]

        user_prompt = f"""
Based on the RFP analysis and Architect's recommendation, generate a complete commercial proposal section.

Key deliverables:
- Resource matrix (Role | Level | Hours | Rate | Total)
- Overall cost estimation (Min / Recommended / Max)
- Delivery model recommendation (Onshore/Offshore mix)
- Margin analysis and pricing strategy
- Commercial risks and mitigation
- Assumptions affecting cost

Human Overrides: {state.human_overrides.get('guidance', 'None')}
Previous Architect Output (for alignment): {state.architect_output[:800] if state.architect_output else 'N/A'}
"""

        # 4. Generate
        output = await self.invoke_with_context(
            system_prompt=system_prompt,
            user_input=user_prompt,
            context=context,
            temperature=0.1,   # Lower temperature for numbers
        )

        # 5. Update state
        state.cfo_output = output

        logger.info("✅ CFO Agent completed")

        return {
            "cfo_output": output,
            "messages": [{"role": "cfo", "content": output[:400] + "..."}]
        }


# For direct testing
async def run_cfo(state: WarRoomState) -> Dict[str, Any]:
    agent = CFOAgent()
    return await agent.cfo_node(state)
