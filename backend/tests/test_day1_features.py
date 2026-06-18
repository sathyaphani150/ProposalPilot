from __future__ import annotations

from app.services.architecture_recommender import _heuristic_recommendation
from app.services.expertise_matcher import _heuristic_match
from app.services.knowledge_service import _confidence
from app.services.proposal_service import _build_discovery_questions


def test_retrieval_confidence_uses_weighted_formula() -> None:
    assert _confidence(0.8, 0.7) == 0.77


def test_expertise_matcher_falls_back_to_internal_evidence() -> None:
    match = _heuristic_match(
        "Enterprise workflow modernization with integrations and reporting.",
        [
            {
                "project_name": "Workflow Modernization Platform",
                "confidence": 0.91,
                "relevance_summary": "Modernized approvals and reporting",
            },
            {
                "project_name": "Portal Refresh",
                "confidence": 0.52,
            },
        ],
    )

    assert match.match_type == "Exact Match"
    assert match.matched_projects == ["Workflow Modernization Platform", "Portal Refresh"]
    assert match.confidence >= 0.9


def test_architecture_recommender_returns_actionable_sections() -> None:
    recommendation = _heuristic_recommendation(
        "Enterprise workflow modernization with integrations and reporting.",
        _heuristic_match(
            "Enterprise workflow modernization with integrations and reporting.",
            [],
        ),
        [
            {
                "project_name": "Workflow Modernization Platform",
                "reusable_assets": ["Auth", "Workflow Engine"],
                "confidence": 0.9,
            }
        ],
    )

    assert "API-first" in recommendation.architecture
    assert recommendation.reusable_components
    assert recommendation.assumptions
    assert recommendation.validation_questions


def test_discovery_question_builder_exposes_new_day_one_groups() -> None:
    questions = _build_discovery_questions(
        {
            "discovery_questions": {},
            "business_questions": ["What KPI defines success?"],
            "data_questions": ["Expected data volume?"],
            "integration_questions": ["SSO required?"],
            "architecture_questions": ["Cloud preference?"],
            "implementation_questions": ["Is a product owner available?"],
        }
    )

    assert questions["business"] == ["What KPI defines success?"]
    assert questions["data"] == ["Expected data volume?"]
    assert questions["integration"] == ["SSO required?"]
    assert questions["architecture"] == ["Cloud preference?"]
    assert questions["implementation_readiness"] == ["Is a product owner available?"]
