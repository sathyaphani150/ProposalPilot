from __future__ import annotations

from typing import Any, TypedDict


class ProposalState(TypedDict, total=False):
    rfp_analysis: dict[str, Any]
    retrieved_context: list[dict[str, Any]]
    similar_projects: list[dict[str, Any]]
    user_overrides: list[dict[str, Any]]
    architect_output: dict[str, Any]
    cfo_output: dict[str, Any]
    competitor_output: dict[str, Any]
    proposal_output: dict[str, Any]
    discussion_log: list[dict[str, Any]]
    unresolved_conflicts: list[dict[str, Any]]
    final_recommendations: dict[str, Any]
    review_loops: int
    session_id: str
    call_notes: str
    session_title: str
    client_name: str | None
    run_id: str
