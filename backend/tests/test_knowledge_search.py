from __future__ import annotations

import uuid

from app.models import KnowledgeItem
from app.services.knowledge_service import (
    _knowledge_item_to_search_result,
    _merge_search_results,
    _score_knowledge_item,
)


def test_keyword_search_scores_metadata_rich_healthcare_project() -> None:
    item = KnowledgeItem(
        id=uuid.uuid4(),
        item_type="project",
        title="MediLink Healthcare Interoperability Hub",
        description=(
            "Interoperability platform enabling healthcare providers to exchange "
            "patient data securely using FHIR standards. Supports real-time data "
            "sync and audit logging."
        ),
        domain="healthcare",
        tech_stack=["Node.js", "FHIR", "MongoDB", "AWS Lambda", "React", "GraphQL"],
        tags=["FHIR", "HIPAA", "data integration", "event streaming"],
        chunk_count=1,
        is_active=True,
    )

    relevant_score = _score_knowledge_item(item, "FHIR HIPAA GraphQL healthcare")
    irrelevant_score = _score_knowledge_item(item, "education mobile quizzes")

    assert relevant_score > 0.7
    assert irrelevant_score == 0


def test_merge_prefers_best_score_per_document() -> None:
    item_id = str(uuid.uuid4())
    db_result = {
        "point_id": f"db:{item_id}",
        "doc_id": item_id,
        "score": 0.86,
        "text": "Database fallback match",
    }
    vector_result = {
        "point_id": "vector-point",
        "doc_id": item_id,
        "score": 0.42,
        "text": "Vector match",
    }

    assert _merge_search_results([vector_result], [db_result], 5) == [db_result]


def test_keyword_result_uses_saved_description_as_search_text() -> None:
    item = KnowledgeItem(
        id=uuid.uuid4(),
        item_type="project",
        title="Audit Logging Portal",
        description="Tracks immutable approval and audit events for compliance.",
        domain="healthcare",
        tech_stack=["React"],
        tags=["audit"],
        chunk_count=1,
        is_active=True,
    )

    result = _knowledge_item_to_search_result(item, 0.8)

    assert result["title"] == "Audit Logging Portal"
    assert result["text"] == item.description
    assert result["doc_id"] == str(item.id)
