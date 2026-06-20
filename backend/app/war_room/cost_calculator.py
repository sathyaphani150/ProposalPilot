from __future__ import annotations

from typing import Any

# Placeholder rate card in USD/hour â€” replace with your actual internal rates.
RATE_CARD: dict[str, float] = {
    "Solution Architect": 120.0,
    "Senior Engineer": 95.0,
    "Engineer": 70.0,
    "QA Engineer": 60.0,
    "Project Manager": 90.0,
}

BASE_HOURS_BY_COMPLEXITY: dict[str, int] = {
    "low": 320,
    "medium": 640,
    "high": 1100,
    "very_high": 1700,
}

ROLE_SPLIT: dict[str, float] = {
    "Solution Architect": 0.10,
    "Senior Engineer": 0.40,
    "Engineer": 0.35,
    "QA Engineer": 0.10,
    "Project Manager": 0.05,
}


def compute_cost_estimate(complexity: str | None) -> dict[str, Any]:
    total_hours = BASE_HOURS_BY_COMPLEXITY.get((complexity or "medium").lower(), 640)
    effort_breakdown = [
        {"role": role, "hours": round(total_hours * pct)}
        for role, pct in ROLE_SPLIT.items()
    ]
    rate_card = [
        {"role": role, "rate": rate, "currency": "USD"}
        for role, rate in RATE_CARD.items()
    ]
    total_cost = sum(
        RATE_CARD[role] * round(total_hours * pct)
        for role, pct in ROLE_SPLIT.items()
    )
    return {
        "effort_breakdown": effort_breakdown,
        "rate_card": rate_card,
        "total_hours": total_hours,
        "total_cost_estimate": round(total_cost, 2),
    }
