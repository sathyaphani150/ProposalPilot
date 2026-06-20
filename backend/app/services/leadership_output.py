"""
Leadership-facing response shaping for RFP analysis endpoints.

The database may retain raw extraction/debug evidence, but CEO/VP/Director views
should receive only decision-grade, source-grounded, low-noise content.
"""
from __future__ import annotations

import copy
import re
from typing import Any

from app.services.rfp_taxonomy import (
    LOW_VALUE_PUBLIC_PHRASES as _LOW_VALUE_PHRASES,
    PUBLIC_RESPONSE_NOISE_TERMS as _NOISE_TERMS,
)

def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(_as_text(item) for item in value if _as_text(item))
    if isinstance(value, dict):
        return ""
    return str(value)


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _clean_text(value: Any, *, max_chars: int = 700) -> str:
    text = _as_text(value)
    text = re.sub(r"\.{4,}\s*\d+", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = text.strip(" -:\t\r\n")
    return text[:max_chars].strip()


def _is_noise(value: Any) -> bool:
    text = f" {_clean_text(value).lower()} "
    if len(text.strip()) < 12:
        return True
    return any(term in text for term in _NOISE_TERMS | _LOW_VALUE_PHRASES)


def _clean_public_text(value: Any, *, max_chars: int = 700) -> str:
    text = _clean_text(value, max_chars=max_chars)
    return "" if not text or _is_noise(text) else text


def _clean_multiline_text(value: Any, *, max_chars: int = 9000) -> str:
    text = _as_text(value).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]{2,}", " ", line).strip() for line in text.split("\n")]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned[:max_chars].strip()


def _clean_items(items: Any, *, limit: int = 8, max_chars: int = 420) -> list[str]:
    if not items:
        return []
    source = items if isinstance(items, list) else [items]
    output: list[str] = []
    seen: set[str] = set()
    for item in source:
        text = _clean_text(item, max_chars=max_chars)
        normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
        if not text or _is_noise(text) or normalized in seen:
            continue
        seen.add(normalized)
        output.append(text)
        if len(output) >= limit:
            break
    return output


def _with_optional_text(data: dict[str, Any], key: str, value: Any, *, max_chars: int = 260) -> None:
    text = _clean_text(value, max_chars=max_chars)
    if text and not _is_noise(text):
        data[key] = text


def _clean_dict_text_fields(data: Any, *, allowed_keys: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        if allowed_keys is not None and key not in allowed_keys:
            continue
        if isinstance(value, str):
            text = _clean_text(value)
            if text and not _is_noise(text):
                cleaned[key] = text
        elif isinstance(value, list):
            cleaned[key] = _clean_items(value)
        elif isinstance(value, dict):
            nested = _clean_dict_text_fields(value)
            if nested:
                cleaned[key] = nested
        elif value is not None:
            cleaned[key] = value
    return cleaned


def _sanitize_risks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    risks: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            text = _clean_text(item)
            if text and not _is_noise(text):
                risks.append({"risk_title": "Delivery risk", "impact": text, "mitigation": "Validate during executive discovery."})
            continue
        title = _clean_text(item.get("risk_title") or item.get("risk_name") or item.get("risk"), max_chars=140)
        impact = _clean_text(item.get("impact"))
        mitigation = _clean_text(item.get("mitigation"))
        if not title and not impact:
            continue
        if _is_noise(title) or _is_noise(impact):
            continue
        risks.append(
            {
                "risk_title": title or "Opportunity risk",
                "severity": _clean_text(item.get("severity"), max_chars=60) or "Medium",
                "impact": impact,
                "mitigation": mitigation or "Validate ownership, dependency readiness, and acceptance criteria before pricing.",
                "owner": _clean_text(item.get("owner"), max_chars=80) or "Joint",
                "probability": _clean_text(item.get("probability"), max_chars=60) or "Medium",
            }
        )
        if len(risks) >= 6:
            break
    return risks


def _sanitize_architecture_diagram(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    nodes: list[dict[str, str]] = []
    node_candidate = value.get("nodes")
    node_source = node_candidate if isinstance(node_candidate, list) else []
    for item in node_source:
        if not isinstance(item, dict):
            continue
        node_id = _clean_text(item.get("id"), max_chars=80)
        label = _clean_text(item.get("label"), max_chars=120)
        if not node_id or not label:
            continue
        nodes.append(
            {
                "id": node_id,
                "label": label,
                "kind": _clean_text(item.get("kind"), max_chars=40),
                "group": _clean_text(item.get("group"), max_chars=80) or "Architecture",
                "description": _clean_text(item.get("description"), max_chars=260),
                "technology": _clean_text(item.get("technology"), max_chars=80),
            }
        )
        if len(nodes) >= 12:
            break

    node_ids = {node["id"] for node in nodes}
    edges: list[dict[str, str]] = []
    edge_candidate = value.get("edges")
    edge_source = edge_candidate if isinstance(edge_candidate, list) else []
    for item in edge_source:
        if not isinstance(item, dict):
            continue
        source = _clean_text(item.get("from"), max_chars=80)
        target = _clean_text(item.get("to"), max_chars=80)
        label = _clean_text(item.get("label"), max_chars=140)
        if source in node_ids and target in node_ids and label:
            edges.append({"from": source, "to": target, "label": label})
        if len(edges) >= 14:
            break

    executive_summary = _clean_items(value.get("executive_summary"), limit=4, max_chars=220)
    lanes: list[dict[str, Any]] = []
    lane_candidate = value.get("lanes")
    lane_source = lane_candidate if isinstance(lane_candidate, list) else []
    for item in lane_source:
        if not isinstance(item, dict):
            continue
        lane_id = _clean_text(item.get("id"), max_chars=80)
        title = _clean_text(item.get("title"), max_chars=120)
        if not lane_id or not title:
            continue
        raw_node_ids = item.get("node_ids")
        node_id_source = raw_node_ids if isinstance(raw_node_ids, list) else []
        lane_node_ids = [
            node_id
            for node_id in (_clean_text(candidate, max_chars=80) for candidate in node_id_source)
            if node_id in node_ids
        ]
        if not lane_node_ids:
            continue
        raw_groups = item.get("groups")
        group_source = raw_groups if isinstance(raw_groups, list) else []
        lanes.append(
            {
                "id": lane_id,
                "title": title,
                "description": _clean_text(item.get("description"), max_chars=220),
                "groups": [_clean_text(group, max_chars=80) for group in group_source if _clean_text(group, max_chars=80)][:8],
                "node_ids": lane_node_ids,
            }
        )
        if len(lanes) >= 6:
            break

    if not nodes:
        return {}
    return {
        "title": _clean_text(value.get("title"), max_chars=140),
        "notation": _clean_text(value.get("notation"), max_chars=80),
        "view": _clean_text(value.get("view"), max_chars=80),
        "executive_summary": executive_summary,
        "lanes": lanes,
        "primary_flow": edges,
        "nodes": nodes,
        "edges": edges,
    }


def _sanitize_rfp_intelligence(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    sentiment = _clean_dict_text_fields(
        value.get("sentiment_analysis"),
        allowed_keys={
            "overall_sentiment",
            "summary",
            "confidence",
            "recommended_posture",
        },
    )
    sentiment_points: list[dict[str, Any]] = []
    sentiment_source = value.get("sentiment_analysis", {}).get("points") if isinstance(value.get("sentiment_analysis"), dict) else []
    for item in (sentiment_source if isinstance(sentiment_source, list) else []):
        if not isinstance(item, dict):
            continue
        insight = _clean_text(item.get("insight"), max_chars=420)
        if not insight or _is_noise(insight):
            continue
        sentiment_points.append(
            {
                "title": _clean_text(item.get("title"), max_chars=120) or "RFP insight",
                "insight": insight,
                "evidence": _clean_text(item.get("evidence"), max_chars=260),
                "implication": _clean_text(item.get("implication"), max_chars=320),
            }
        )
        if len(sentiment_points) >= 6:
            break
    sentiment["points"] = sentiment_points
    questions: list[dict[str, Any]] = []
    question_candidate = value.get("must_ask_questions")
    question_source = question_candidate if isinstance(question_candidate, list) else []
    for item in question_source:
        if not isinstance(item, dict):
            continue
        question = _clean_text(item.get("question"), max_chars=260)
        if not question or _is_noise(question):
            continue
        question_card: dict[str, Any] = {
            "question": question,
            "why_it_matters": _clean_text(item.get("why_it_matters"), max_chars=260),
            "assumption_to_validate": _clean_text(item.get("assumption_to_validate"), max_chars=260),
        }
        _with_optional_text(question_card, "category", item.get("category"), max_chars=100)
        _with_optional_text(question_card, "evidence", item.get("evidence"), max_chars=220)
        questions.append(question_card)
        if len(questions) >= 10:
            break

    talking_points: list[dict[str, Any]] = []
    talking_point_candidate = value.get("talking_points")
    talking_point_source = talking_point_candidate if isinstance(talking_point_candidate, list) else []
    for item in talking_point_source:
        if not isinstance(item, dict):
            continue
        point = _clean_text(item.get("point"), max_chars=260)
        if point and not _is_noise(point):
            talking_points.append(
                {
                    "point": point,
                    "client_angle": _clean_text(item.get("client_angle"), max_chars=300),
                    "proof_needed": _clean_text(item.get("proof_needed"), max_chars=300),
                    "evidence": _clean_text(item.get("evidence"), max_chars=220),
                }
            )
        if len(talking_points) >= 7:
            break

    evidence: list[dict[str, Any]] = []
    evidence_candidate = value.get("relevant_knowledge_evidence")
    evidence_source = evidence_candidate if isinstance(evidence_candidate, list) else []
    for item in evidence_source:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"), max_chars=140)
        why = _clean_text(item.get("why_relevant"), max_chars=420)
        if title and why and not _is_noise(why):
            evidence.append(
                {
                    "title": title,
                    "domain": _clean_text(item.get("domain"), max_chars=80),
                    "item_type": _clean_text(item.get("item_type"), max_chars=80),
                    "score": item.get("score"),
                    "why_relevant": why,
                    "tech_stack": _clean_items(item.get("tech_stack"), limit=8, max_chars=60),
                    "tags": _clean_items(item.get("tags"), limit=8, max_chars=60),
                }
            )
        if len(evidence) >= 6:
            break

    architecture_candidate = value.get("architecture")
    architecture: dict[str, Any] = architecture_candidate if isinstance(architecture_candidate, dict) else {}
    return {
        "sentiment_analysis": sentiment,
        "must_ask_questions": questions,
        "top_risks": _sanitize_risks(value.get("top_risks")),
        "talking_points": talking_points,
        "narrative": _clean_dict_text_fields(
            value.get("narrative"),
            allowed_keys={"title", "story", "how_it_helps", "evidence_project_title", "confidence"},
        ),
        "relevant_knowledge_evidence": evidence,
        "architecture": {
            "summary": _clean_text(architecture.get("summary"), max_chars=700),
            "business_view": _clean_items(architecture.get("business_view"), limit=6, max_chars=360),
            "technical_view": _clean_items(architecture.get("technical_view"), limit=10, max_chars=360),
            "data_flow": _clean_items(architecture.get("data_flow"), limit=7, max_chars=360),
            "integration_flow": _clean_items(architecture.get("integration_flow"), limit=7, max_chars=360),
            "security_operations": _clean_items(architecture.get("security_operations"), limit=8, max_chars=360),
            "decision_points": _clean_items(architecture.get("decision_points"), limit=7, max_chars=360),
            "call_prep_questions": _clean_items(architecture.get("call_prep_questions"), limit=8, max_chars=280),
            "diagram": _sanitize_architecture_diagram(architecture.get("diagram")),
            "structurizr_dsl": _clean_multiline_text(architecture.get("structurizr_dsl"), max_chars=9000),
            "generated_by": _clean_text(architecture.get("generated_by"), max_chars=80),
        },
    }


def sanitize_analysis_payload_for_leadership(analysis: dict[str, Any]) -> dict[str, Any]:
    """Return the public leadership-safe analysis payload for the API."""
    payload = copy.deepcopy(analysis)
    payload["business_problem"] = _clean_public_text(payload.get("business_problem"), max_chars=1000) or None
    payload["functional_requirements"] = _clean_items(payload.get("functional_requirements"), limit=5)
    payload["non_functional_requirements"] = _clean_items(payload.get("non_functional_requirements"), limit=5)
    payload["data_needs"] = _clean_items(payload.get("data_needs"), limit=5)
    payload["integration_needs"] = _clean_items(payload.get("integration_needs"), limit=5)
    payload["compliance_needs"] = _clean_items(payload.get("compliance_needs"), limit=5)
    payload["timeline_risks"] = _clean_items(payload.get("timeline_risks"), limit=5)
    payload["missing_information"] = _clean_items(payload.get("missing_information"), limit=10)
    payload["scope_boundaries"] = _clean_items(payload.get("scope_boundaries"), limit=6)
    payload["domain_tags"] = _clean_items(payload.get("domain_tags"), limit=8, max_chars=80)

    raw = _dict_or_empty(payload.get("raw_llm_output"))
    rfp_intelligence = _sanitize_rfp_intelligence(raw.get("rfp_intelligence"))
    extraction_meta = _dict_or_empty(raw.get("extraction_meta"))
    payload["raw_llm_output"] = {
        "extraction_meta": {
            "mode": extraction_meta.get("mode") or "source-grounded",
            "confidence": extraction_meta.get("confidence"),
            "warnings": _clean_items(extraction_meta.get("warnings"), limit=3),
        },
        "rfp_intelligence": rfp_intelligence,
    }
    payload["analysis_brief"] = {
        "summary": rfp_intelligence.get("sentiment_analysis", {}).get("summary") or payload["business_problem"],
        "recommended_posture": rfp_intelligence.get("sentiment_analysis", {}).get("recommended_posture"),
        "top_questions": [
            item.get("question")
            for item in rfp_intelligence.get("must_ask_questions", [])[:5]
            if isinstance(item, dict) and item.get("question")
        ],
        "top_risks": [
            item.get("risk_title")
            for item in rfp_intelligence.get("top_risks", [])[:5]
            if isinstance(item, dict) and item.get("risk_title")
        ],
    }
    return payload
