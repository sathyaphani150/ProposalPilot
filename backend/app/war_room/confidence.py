from __future__ import annotations

from typing import Any


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _bounded(value: float) -> float:
    return round(max(0.25, min(0.95, value)), 2)


def _coverage_ratio(payload: dict[str, Any], keys: list[str]) -> float:
    if not keys:
        return 0.0
    present = 0
    for key in keys:
        value = payload.get(key)
        if _has_text(value) or bool(_as_list(value)) or bool(_as_dict(value)):
            present += 1
    return present / len(keys)


def _upstream_average(state: dict[str, Any], keys: list[str]) -> float | None:
    values: list[float] = []
    for key in keys:
        confidence = _as_dict(state.get(key)).get("confidence")
        if isinstance(confidence, (int, float)):
            values.append(float(confidence))
    if not values:
        return None
    return sum(values) / len(values)


def calculate_agent_confidence(
    *,
    agent: str,
    state: dict[str, Any],
    payload: dict[str, Any],
    generated_by: str,
) -> float:
    """Calibrate agent confidence from source evidence and uncertainty.

    This score intentionally measures confidence in the generated recommendation,
    not model certainty. It rewards grounded inputs and complete outputs, and
    penalizes unresolved RFP gaps, timeline risks, and deterministic fallback use.
    """

    analysis = _as_dict(state.get("rfp_analysis"))
    similar_projects = _as_list(state.get("similar_projects"))
    retrieved_context = _as_list(state.get("retrieved_context"))
    missing_information = _as_list(analysis.get("missing_information"))
    timeline_risks = _as_list(analysis.get("timeline_risks"))
    integration_needs = _as_list(analysis.get("integration_needs"))
    compliance_needs = _as_list(analysis.get("compliance_needs"))

    score = 0.36
    if generated_by == "llm":
        score += 0.08

    if _has_text(analysis.get("business_problem")):
        score += 0.08
    if _as_list(analysis.get("functional_requirements")):
        score += 0.06
    if integration_needs:
        score += 0.04
    if compliance_needs:
        score += 0.03
    if similar_projects:
        score += min(0.10, 0.035 * len(similar_projects))
    if retrieved_context:
        score += min(0.08, 0.02 * len(retrieved_context))
    if _has_text(state.get("call_notes")):
        score += 0.04

    required_keys = {
        "architect": [
            "architecture_summary",
            "architecture_pattern",
            "recommended_stack",
            "assumptions",
            "technical_risks",
            "validation_questions",
            "reasoning",
        ],
        "cfo": [
            "team_structure",
            "estimated_duration_weeks",
            "effort_breakdown",
            "pricing_model_recommendation",
            "cost_estimate",
            "financial_risks",
            "margin_assessment",
            "reasoning",
        ],
        "competitor": [
            "positioning_strategy",
            "differentiators",
            "win_themes",
            "competitive_risks",
            "value_proposition",
            "executive_messaging",
            "reasoning",
        ],
        "proposal": [
            "executive_summary",
            "client_problem_restatement",
            "proposed_solution",
            "architecture_section",
            "delivery_approach",
            "cost_section",
            "competitive_positioning",
            "risks",
            "assumptions",
            "reasoning",
        ],
    }.get(agent, [])
    score += 0.18 * _coverage_ratio(payload, required_keys)

    if agent in {"cfo", "competitor", "proposal"}:
        upstream = _upstream_average(
            state,
            ["architect_output", "cfo_output", "competitor_output"]
            if agent == "proposal"
            else ["architect_output"],
        )
        if upstream is not None:
            score += (upstream - 0.5) * 0.18

    uncertainty = len(missing_information) + len(timeline_risks)
    score -= min(0.18, 0.025 * uncertainty)
    if generated_by != "llm":
        score -= 0.06
    if not similar_projects:
        score -= 0.04

    return _bounded(score)
