# backend/app/agents/supervisor.py
"""
ProposalPilot AI — War Room Supervisor Agent
Orchestrates the multi-agent workflow and handles routing + human overrides.
"""

from typing import Any, Dict, Literal

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger

from app.agents.base_agent import BaseAgent, AGENT_SYSTEM_PROMPTS
from app.agents.state import WarRoomState


class SupervisorAgent(BaseAgent):
    """Supervisor that routes between agents and handles completion."""

    def __init__(self):
        super().__init__(model_name="llama-3.3-70b-versatile")  # Strong reasoning model

    async def supervisor_node(self, state: WarRoomState) -> Dict[str, Any]:
        """
        Main supervisor logic — decides next agent or END.
        """
        state.iteration += 1
        logger.info(f"Supervisor iteration {state.iteration} | Next: {state.next_agent}")

        # 1. Apply human overrides if present
        if state.human_overrides:
            await self._apply_overrides(state)

        # 2. Check if we should end
        if self._should_end(state):
            state.is_complete = True
            state.next_agent = "END"
            logger.info("Supervisor decided to END War Room")
            return {"next_agent": "END", "is_complete": True}

        # 3. Decide next agent
        next_agent = await self._route_next_agent(state)
        state.next_agent = next_agent

        return {
            "next_agent": next_agent,
            "messages": [HumanMessage(content=f"Supervisor routing to: {next_agent}")]
        }

    async def _route_next_agent(self, state: WarRoomState) -> str:
        """Use LLM to intelligently route to next agent."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", SUPERVISOR_PROMPT),
            ("human", "Current state summary: {state_summary}")
        ])

        llm = self.get_llm(temperature=0.0)  # Deterministic routing

        # Build concise state summary for routing
        summary = self._build_state_summary(state)

        response = await llm.ainvoke(
            prompt.format_messages(state_summary=summary)
        )

        # Parse response (expecting simple string: "architect", "cfo", etc.)
        content = str(response.content).strip().lower()

        valid_agents = ["architect", "cfo", "competitor", "proposal"]
        for agent in valid_agents:
            if agent in content:
                return agent

        # Default fallback order
        order = ["architect", "cfo", "competitor", "proposal"]
        for agent in order:
            if not getattr(state, f"{agent}_output", None):
                return agent

        return "proposal"  # Final synthesis

    def _should_end(self, state: WarRoomState) -> bool:
        """Decide if all agents have contributed and proposal is ready."""
        if state.iteration > 12:  # Safety limit
            return True

        required = ["architect_output", "cfo_output", "competitor_output", "proposal_output"]
        return all(getattr(state, field, None) for field in required)

    async def _apply_overrides(self, state: WarRoomState):
        """Inject human guidance into the state."""
        guidance = state.human_overrides.get("guidance", "")
        if guidance:
            logger.info(f"Applying human override: {guidance[:100]}...")
            # This will be picked up by agents via context

    def _build_state_summary(self, state: WarRoomState) -> str:
        """Create concise summary for routing decision."""
        completed = []
        for agent in ["architect", "cfo", "competitor", "proposal"]:
            if getattr(state, f"{agent}_output", None):
                completed.append(agent)

        return f"""
Completed agents: {completed}
Human overrides present: {bool(state.human_overrides)}
Call notes present: {bool(state.call_notes)}
Iteration: {state.iteration}
        """.strip()


# Supervisor System Prompt
SUPERVISOR_PROMPT = """You are the **War Room Supervisor** for ProposalPilot AI.

Your job is to coordinate 4 specialized agents:
- architect: Technical solution design
- cfo: Commercial & costing strategy  
- competitor: Win strategy & differentiation
- proposal: Final proposal synthesis

Decide the next agent to run based on what is still missing.
Respond with ONLY the name of the next agent (one word).

If all agents have produced high-quality output, respond with "END".
""" 
