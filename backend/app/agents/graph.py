# backend/app/agents/graph.py
"""
ProposalPilot AI — War Room LangGraph Orchestration
Main graph that ties together Supervisor + 4 specialized agents.
Supports human-in-the-loop and persistence.
"""

from typing import Any, Dict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langchain_core.runnables import RunnableConfig
from loguru import logger

from app.agents.architect_agent import ArchitectAgent
from app.agents.cfo_agent import CFOAgent
from app.agents.competitor_agent import CompetitorAgent
from app.agents.proposal_agent import ProposalAgent
from app.agents.state import WarRoomState
from app.agents.supervisor import SupervisorAgent


def route_to_next(state: WarRoomState) -> str:
    """Conditional edge router based on supervisor decision."""
    next_agent = state.next_agent
    if next_agent == "END" or state.is_complete:
        return END
    if next_agent:
        return next_agent
    return END


def compile_war_room_graph(checkpointer: MemorySaver | None = None):
    """
    Compile the complete multi-agent War Room graph.
    """
    workflow = StateGraph(WarRoomState)

    # Initialize agents
    supervisor = SupervisorAgent()
    architect = ArchitectAgent()
    cfo = CFOAgent()
    competitor = CompetitorAgent()
    proposal = ProposalAgent()

    # Add nodes
    workflow.add_node("supervisor", supervisor.supervisor_node)
    workflow.add_node("architect", architect.architect_node)
    workflow.add_node("cfo", cfo.cfo_node)
    workflow.add_node("competitor", competitor.competitor_node)
    workflow.add_node("proposal", proposal.proposal_node)

    # Set entry point
    workflow.set_entry_point("supervisor")

    # Add conditional edges from supervisor
    workflow.add_conditional_edges(
        "supervisor",
        route_to_next,
        {
            "architect": "architect",
            "cfo": "cfo",
            "competitor": "competitor",
            "proposal": "proposal",
            END: END,
        }
    )

    # Add edges from agents back to supervisor
    for agent_name in ["architect", "cfo", "competitor", "proposal"]:
        workflow.add_edge(agent_name, "supervisor")

    # Compile graph with optional persistence
    if checkpointer is None:
        checkpointer = MemorySaver()

    graph = workflow.compile(checkpointer=checkpointer)
    logger.info("✅ War Room LangGraph compiled successfully with 5 nodes (Supervisor + 4 Agents)")
    return graph


# Convenience function for services
async def run_war_room_graph(
    initial_state: WarRoomState,
    thread_id: str | None = None,
) -> WarRoomState:
    """
    Run the full War Room graph.
    """
    graph = compile_war_room_graph()

    config: RunnableConfig = {"configurable": {"thread_id": thread_id or initial_state.rfp_session_id}}

    try:
        result = await graph.ainvoke(initial_state.model_dump(), config=config)
        logger.info(f"War Room graph completed for session {initial_state.rfp_session_id}")
        return WarRoomState.model_validate(result)
    except Exception as e:
        logger.error(f"War Room graph failed: {e}")
        initial_state.error = str(e)
        return initial_state


# For streaming (future WebSocket support)
async def astream_war_room_graph(initial_state: WarRoomState):
    graph = compile_war_room_graph()
    config: RunnableConfig = {"configurable": {"thread_id": initial_state.rfp_session_id}}
    async for event in graph.astream_events(initial_state.model_dump(), config=config, version="v2"):
        yield event
