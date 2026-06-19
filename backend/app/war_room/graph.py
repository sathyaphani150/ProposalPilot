from __future__ import annotations

from typing import Any, Literal

try:
    from langgraph.graph import END, StateGraph
    _LANGGRAPH_AVAILABLE = True
except Exception:  # pragma: no cover - fallback for version skew in local envs
    END = "END"  # type: ignore[assignment]
    StateGraph = None  # type: ignore[assignment]
    _LANGGRAPH_AVAILABLE = False

from app.war_room.agents import (
    run_architect_agent,
    run_cfo_agent,
    run_competitor_agent,
    run_proposal_agent,
)
from app.war_room.discussion import build_discussion_round
from app.war_room.state import ProposalState
from app.war_room.supervisor import validate_war_room_outputs


async def _discussion_node(state: ProposalState) -> dict[str, Any]:
    messages, conflicts = build_discussion_round(state)
    discussion_log = list(state.get("discussion_log") or [])
    discussion_log.extend(messages)
    unresolved_conflicts = list(state.get("unresolved_conflicts") or [])
    unresolved_conflicts.extend(conflicts)
    return {
        "discussion_log": discussion_log,
        "unresolved_conflicts": unresolved_conflicts,
    }


async def _supervisor_node(state: ProposalState) -> dict[str, Any]:
    final_recommendations = validate_war_room_outputs(state)
    review_loops = int(state.get("review_loops") or 0)
    if final_recommendations.get("should_loop"):
        review_loops += 1
    unresolved_conflicts = list(state.get("unresolved_conflicts") or [])
    if not final_recommendations.get("should_loop"):
        unresolved_conflicts = []
    return {
        "final_recommendations": final_recommendations,
        "review_loops": review_loops,
        "unresolved_conflicts": unresolved_conflicts,
    }


def _route_after_supervisor(state: ProposalState) -> Literal["loop", "end"]:
    if state.get("final_recommendations", {}).get("should_loop"):
        return "loop"
    return "end"


def build_war_room_graph():
    if not _LANGGRAPH_AVAILABLE:
        return _FallbackWarRoomGraph()

    graph = StateGraph(ProposalState)
    graph.add_node("architect", run_architect_agent)
    graph.add_node("cfo", run_cfo_agent)
    graph.add_node("competitor", run_competitor_agent)
    graph.add_node("discussion", _discussion_node)
    graph.add_node("proposal", run_proposal_agent)
    graph.add_node("supervisor", _supervisor_node)

    graph.set_entry_point("architect")
    graph.add_edge("architect", "cfo")
    graph.add_edge("cfo", "competitor")
    graph.add_edge("competitor", "discussion")
    graph.add_edge("discussion", "proposal")
    graph.add_edge("proposal", "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {"loop": "architect", "end": END},
    )
    return graph.compile()


_compiled_graph = None


class _FallbackWarRoomGraph:
    async def ainvoke(self, state: ProposalState) -> ProposalState:
        current_state: ProposalState = dict(state)
        while True:
            architect_update = await run_architect_agent(current_state)
            current_state.update(architect_update)

            cfo_update = await run_cfo_agent(current_state)
            current_state.update(cfo_update)

            competitor_update = await run_competitor_agent(current_state)
            current_state.update(competitor_update)

            discussion_update = await _discussion_node(current_state)
            current_state.update(discussion_update)

            proposal_update = await run_proposal_agent(current_state)
            current_state.update(proposal_update)

            supervisor_update = await _supervisor_node(current_state)
            current_state.update(supervisor_update)

            if not current_state.get("final_recommendations", {}).get("should_loop"):
                return current_state

    async def astream(self, state: ProposalState, *, config: dict[str, Any] | None = None, stream_mode: str = "updates"):
        current_state: ProposalState = dict(state)
        while True:
            architect_update = await run_architect_agent(current_state)
            current_state.update(architect_update)
            yield {"architect": architect_update}

            cfo_update = await run_cfo_agent(current_state)
            current_state.update(cfo_update)
            yield {"cfo": cfo_update}

            competitor_update = await run_competitor_agent(current_state)
            current_state.update(competitor_update)
            yield {"competitor": competitor_update}

            discussion_update = await _discussion_node(current_state)
            current_state.update(discussion_update)
            yield {"discussion": discussion_update}

            proposal_update = await run_proposal_agent(current_state)
            current_state.update(proposal_update)
            yield {"proposal": proposal_update}

            supervisor_update = await _supervisor_node(current_state)
            current_state.update(supervisor_update)
            yield {"supervisor": supervisor_update}

            if not current_state.get("final_recommendations", {}).get("should_loop"):
                return


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_war_room_graph()
    return _compiled_graph


async def run_war_room_graph(state: ProposalState) -> ProposalState:
    graph = get_compiled_graph()
    result = await graph.ainvoke(state)
    return result
