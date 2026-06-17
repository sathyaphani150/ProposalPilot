# backend/app/agents/architect_agent.py
"""
ProposalPilot AI — Tech Architect Agent
Responsible for solution design, architecture, tech stack, reusability, and feasibility.
"""

from typing import Any, Dict

from loguru import logger

from app.agents.base_agent import BaseAgent, AGENT_SYSTEM_PROMPTS
from app.agents.state import WarRoomState
from app.agents.rag_tool import search_similar_projects, search_rag


class ArchitectAgent(BaseAgent):
    """Tech Architect specialized agent."""

    def __init__(self):
        super().__init__(model_name="llama-3.3-70b-versatile")

    async def architect_node(self, state: WarRoomState) -> Dict[str, Any]:
        """
        Main node for the Architect Agent.
        """
        logger.info("🤖 Architect Agent started")

        # 1. Retrieve relevant context
        similar_projects = await search_similar_projects(state.rfp_analysis)
        state.retrieved_context = similar_projects

        # 2. Build context for LLM
        context = {
            "rfp_analysis": state.rfp_analysis,
            "retrieved_context": similar_projects,
            "call_notes": state.call_notes,
            "human_overrides": state.human_overrides,
        }

        # 3. System + User prompt
        system_prompt = AGENT_SYSTEM_PROMPTS["architect"]

        user_prompt = f"""
Analyze the RFP and generate a comprehensive technical architecture recommendation.

Current Iteration: {state.iteration}
Human Overrides: {state.human_overrides.get('guidance', 'None')}

Focus on:
- Recommended high-level architecture
- Technology stack (with justification from past projects)
- Key components & integration strategy
- Reusable assets from internal knowledge base
- Technical risks and mitigation
- Feasibility assessment
- Mermaid architecture diagram (if applicable)
"""

        # 4. Generate response
        output = await self.invoke_with_context(
            system_prompt=system_prompt,
            user_input=user_prompt,
            context=context,
            temperature=0.15,
        )

        # 5. Update state
        state.architect_output = output

        logger.info("✅ Architect Agent completed")

        return {
            "architect_output": output,
            "retrieved_context": similar_projects,
            "messages": [{"role": "architect", "content": output[:500] + "..."}]
        }


# For direct testing / fallback
async def run_architect(state: WarRoomState) -> Dict[str, Any]:
    agent = ArchitectAgent()
    return await agent.architect_node(state)
