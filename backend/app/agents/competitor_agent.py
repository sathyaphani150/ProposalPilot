# backend/app/agents/competitor_agent.py
"""
ProposalPilot AI — Competitor Strategist Agent
Analyzes competitive landscape, highlights differentiators, and crafts win themes.
"""

from typing import Any, Dict

from loguru import logger

from app.agents.base_agent import BaseAgent, AGENT_SYSTEM_PROMPTS
from app.agents.state import WarRoomState
from app.agents.rag_tool import search_rag


class CompetitorAgent(BaseAgent):
    """Competitor Strategist specialized agent."""

    def __init__(self):
        super().__init__(model_name="llama-3.3-70b-versatile")

    async def competitor_node(self, state: WarRoomState) -> Dict[str, Any]:
        """
        Main node for the Competitor Strategist Agent.
        """
        logger.info("🛡️ Competitor Agent started")

        # 1. Retrieve competitor / differentiator context
        comp_context = await search_rag(
            query="Cognine differentiators past wins competitor analysis case study",
            limit=6,
        )
        state.retrieved_context.extend(comp_context)

        # 2. Build context
        context = {
            "rfp_analysis": state.rfp_analysis,
            "retrieved_context": state.retrieved_context,
            "call_notes": state.call_notes,
            "human_overrides": state.human_overrides,
            "architect_output": state.architect_output or "",
            "cfo_output": state.cfo_output or "",
        }

        # 3. Prompts
        system_prompt = AGENT_SYSTEM_PROMPTS["competitor"]

        user_prompt = f"""
Analyze the competitive landscape for this RFP and develop a winning strategy.

Deliverables:
- Key competitors likely bidding
- Our key differentiators (grounded in past projects)
- Win themes and value propositions
- Competitive positioning statements
- Risks from competition
- Recommended bid strategy

Human Overrides: {state.human_overrides.get('guidance', 'None')}
"""

        # 4. Generate response
        output = await self.invoke_with_context(
            system_prompt=system_prompt,
            user_input=user_prompt,
            context=context,
            temperature=0.2,   # Slightly higher for strategic creativity
        )

        # 5. Update state
        state.competitor_output = output

        logger.info("✅ Competitor Agent completed")

        return {
            "competitor_output": output,
            "messages": [{"role": "competitor", "content": output[:400] + "..."}]
        }


# For direct testing
async def run_competitor(state: WarRoomState) -> Dict[str, Any]:
    agent = CompetitorAgent()
    return await agent.competitor_node(state)
