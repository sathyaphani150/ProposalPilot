from __future__ import annotations

import pytest

from app.war_room.discussion import build_discussion_round
from app.war_room.graph import run_war_room_graph
from app.war_room.supervisor import validate_war_room_outputs


def test_discussion_round_flags_timeline_conflict() -> None:
    state = {
        "rfp_analysis": {"estimated_complexity": "high"},
        "architect_output": {"technical_risks": ["Integration risk"]},
        "cfo_output": {"estimated_duration_weeks": 4},
        "competitor_output": {"differentiators": ["Grounded evidence"]},
    }

    messages, conflicts = build_discussion_round(state)

    assert messages
    assert any(message["target_agent"] == "architect" for message in messages)
    assert conflicts
    assert conflicts[0]["type"] == "timeline"


def test_supervisor_requests_loop_when_conflicts_exist() -> None:
    result = validate_war_room_outputs(
        {
            "architect_output": {"assumptions": ["Client will confirm access"], "confidence": 0.9},
            "cfo_output": {"estimated_duration_weeks": 4, "confidence": 0.7},
            "proposal_output": {"executive_summary": "Draft", "confidence": 0.8},
            "unresolved_conflicts": [{"summary": "Timeline mismatch"}],
            "review_loops": 0,
        }
    )

    assert result["status"] == "needs_review"
    assert result["should_loop"] is True


@pytest.mark.asyncio
async def test_war_room_graph_runs_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeProvider:
        async def structured_output(self, **_: object) -> None:
            return None

    fake_provider = _FakeProvider()
    monkeypatch.setattr("app.war_room.agents.architect_agent.get_war_room_llm_provider", lambda: fake_provider)
    monkeypatch.setattr("app.war_room.agents.cfo_agent.get_war_room_llm_provider", lambda: fake_provider)
    monkeypatch.setattr("app.war_room.agents.competitor_agent.get_war_room_llm_provider", lambda: fake_provider)
    monkeypatch.setattr("app.war_room.agents.proposal_agent.get_war_room_llm_provider", lambda: fake_provider)

    result = await run_war_room_graph(
        {
            "session_id": "session-1",
            "session_title": "Modernize Proposal Workflow",
            "client_name": "Acme",
            "call_notes": "Need faster proposal turnaround. Use an offshore-heavy delivery model.",
            "rfp_analysis": {
                "business_problem": "The client needs a faster proposal workflow.",
                "estimated_complexity": "medium",
                "functional_requirements": ["Automate proposal drafts"],
                "integration_needs": ["CRM integration"],
                "data_needs": ["Proposal history"],
                "compliance_needs": ["SOC 2"],
                "missing_information": ["Confirm approval owners"],
                "domain_tags": ["proposal", "automation"],
            },
            "retrieved_context": [],
            "similar_projects": [],
            "user_overrides": [],
            "discussion_log": [],
            "unresolved_conflicts": [],
            "final_recommendations": {},
            "review_loops": 0,
            "run_id": "test-run",
        }
    )

    assert result["architect_output"]["architecture_summary"]
    assert result["architect_output"]["assumptions"]
    assert "offshore" in result["architect_output"]["architecture_summary"].lower() or any(
        "offshore" in item.lower() for item in result["architect_output"]["recommended_stack"]
    )
    assert result["cfo_output"]["cost_estimate"]["currency"] == "USD"
    assert result["cfo_output"]["effort_breakdown"]
    assert result["cfo_output"]["rate_card"]
    assert any("offshore" in risk.lower() for risk in result["cfo_output"]["financial_risks"])
    assert len(result["competitor_output"]["differentiators"]) <= 5
    assert len(result["competitor_output"]["win_themes"]) <= 4
    assert result["proposal_output"]["executive_summary"]
    assert len(result["proposal_output"]["compliance_matrix"]) == 1
    assert "status" in result["final_recommendations"]
