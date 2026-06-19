from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _as_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_discussion_round(state: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    architect = state.get("architect_output") or {}
    cfo = state.get("cfo_output") or {}
    competitor = state.get("competitor_output") or {}
    round_index = int(state.get("review_loops") or 0)

    messages: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    estimated_duration = _as_number(cfo.get("estimated_duration_weeks"))
    complexity = str((state.get("rfp_analysis") or {}).get("estimated_complexity") or "medium").lower()
    target_duration = {"low": 6, "medium": 10, "high": 16, "very_high": 24}.get(complexity, 10)

    if estimated_duration is not None and estimated_duration < max(4, target_duration * 0.6):
        comment = (
            f"CFO timeline is optimistic at {estimated_duration:.0f} weeks for a {complexity} opportunity. "
            "Re-check integration, acceptance, and change-control assumptions."
        )
        messages.append(
            {
                "agent": "cfo",
                "comment": comment,
                "target_agent": "architect",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "round_index": round_index,
            }
        )
        conflicts.append(
            {
                "type": "timeline",
                "summary": comment,
                "severity": "high",
            }
        )

    if len(architect.get("technical_risks", [])) == 0 and estimated_duration is not None:
        comment = "Architect output is missing explicit technical risk items. Add delivery, security, and integration risk coverage."
        messages.append(
            {
                "agent": "competitor",
                "comment": comment,
                "target_agent": "architect",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "round_index": round_index,
            }
        )
        conflicts.append(
            {
                "type": "risk_coverage",
                "summary": comment,
                "severity": "medium",
            }
        )

    if not competitor.get("differentiators"):
        comment = "Competitor strategy needs sharper differentiators tied to proof, speed, and delivery control."
        messages.append(
            {
                "agent": "proposal",
                "comment": comment,
                "target_agent": "competitor",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    if not messages:
        messages.append(
            {
                "agent": "proposal",
                "comment": "No material conflicts detected in this discussion round.",
                "target_agent": "all",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "round_index": round_index,
            }
        )

    return messages, conflicts
