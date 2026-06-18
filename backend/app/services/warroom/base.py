from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    agent_name: str
    summary: str
    recommendations: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


def _clean_list(values: Any, *, max_items: int = 8) -> list[str]:
    if not values:
        return []
    if not isinstance(values, list):
        values = [values]
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = re.sub(r"\s{2,}", " ", str(value).strip()).strip(" -:\t")
        if not text:
            continue
        normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(text)
        if len(cleaned) >= max_items:
            break
    return cleaned


def guidance_text(guidance: list[str] | None) -> str:
    items = _clean_list(guidance, max_items=10)
    if not items:
        return "No additional user guidance provided."
    return "\n".join(f"- {item}" for item in items)


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)
