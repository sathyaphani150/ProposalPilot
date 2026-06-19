from __future__ import annotations

from typing import Any


def _duration_weeks(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_war_room_outputs(state: dict[str, Any]) -> dict[str, Any]:
    architect = state.get("architect_output") or {}
    cfo = state.get("cfo_output") or {}
    proposal = state.get("proposal_output") or {}
    conflicts = list(state.get("unresolved_conflicts") or [])

    timeline = _duration_weeks(cfo.get("estimated_duration_weeks"))
    assumptions = architect.get("assumptions") or []
    confidence = min(
        [item for item in [
            architect.get("confidence"),
            cfo.get("confidence"),
            proposal.get("confidence"),
        ] if isinstance(item, (int, float))] or [0.75]
    )

    recommendations = {
        "status": "approved" if not conflicts else "needs_review",
        "summary": proposal.get("executive_summary") or "Proposal generated.",
        "timeline_weeks": timeline,
        "approval_notes": [
            "Architecture, cost, competitor, and proposal outputs are aligned." if not conflicts else "Supervisor detected at least one material mismatch.",
            f"Architect assumptions captured: {len(assumptions)}" if assumptions else "Architect assumptions need sharpening.",
        ],
        "confidence": round(float(confidence), 2),
    }

    should_loop = bool(conflicts) and int(state.get("review_loops", 0)) < 3
    recommendations["should_loop"] = should_loop
    recommendations["loop_reason"] = conflicts[0]["summary"] if conflicts else None
    return recommendations
