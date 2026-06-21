from __future__ import annotations

import re
from typing import Any

from loguru import logger


_GENERIC_TERMS = {
    "client",
    "project",
    "proposal",
    "solution",
    "system",
    "platform",
    "workflow",
    "service",
    "services",
    "application",
    "requirements",
    "business",
    "delivery",
    "implementation",
}


def _keywords(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, dict):
        return set().union(*(_keywords(item) for item in value.values()))
    if isinstance(value, (list, tuple, set)):
        return set().union(*(_keywords(item) for item in value))
    return {
        token.lower()
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", str(value))
        if token.lower() not in _GENERIC_TERMS
    }


def _text_blob(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_text_blob(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text_blob(item) for item in value)
    return str(value)


def warn_if_generic_agent_output(agent: str, state: dict[str, Any], payload: dict[str, Any]) -> None:
    analysis = state.get("rfp_analysis") or {}
    distinguishing_terms = _keywords(
        [
            state.get("client_name"),
            state.get("session_title"),
            analysis.get("domain_tags"),
            analysis.get("business_problem"),
        ]
    )
    if not distinguishing_terms:
        return

    output_text = _text_blob(
        {key: value for key, value in payload.items() if key not in {"confidence", "generated_by"}}
    ).lower()
    if any(term in output_text for term in distinguishing_terms):
        return

    logger.warning(
        "War room LLM output for {} may be generic: no overlap with RFP/session terms {}.",
        agent,
        sorted(distinguishing_terms)[:12],
    )
