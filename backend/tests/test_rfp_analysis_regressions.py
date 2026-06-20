from __future__ import annotations

from pathlib import Path

from app.services.rfp_engine import _deterministic_extract, _finalize_analysis_payload
from app.services.rfp_service import _analysis_needs_recovery
from app.services.leadership_output import sanitize_analysis_payload_for_leadership


GENERIC_RFP_SAMPLE = """
Request for Proposal for Enterprise Workflow Modernization Platform.

The buyer wants to replace spreadsheet-driven approvals with a secure web
portal for case intake, routing, review, reporting, and audit tracking.

The solution shall provide role-based dashboards, configurable approval
workflows, document upload, notifications, management reports, and audit trails.

The selected system shall integrate with existing identity, finance, document
repository, and notification systems through APIs or batch interfaces.

Historical records must be migrated from existing spreadsheets and file shares.
The supplier shall validate data quality, reconcile migrated records, and define
data ownership for ongoing operations.

The platform shall be hosted in the buyer's approved cloud environment with
access control, encryption, monitoring, backup, disaster recovery, and support.

Bids received after closing shall be rejected.
EMD must be submitted before pre-bid meeting and bid submission.
Bidder registration process shall be completed on the e-tendering portal.
Copy of audited balance sheet must be submitted.
Name of statutory auditor must be provided.
3rd Floor, Tower II, New Delhi.
Blacklisting declaration as per annexure.
"""


MOBILE_RFP_SAMPLE = """
Request for Proposal for Design, Development, Implementation and Maintenance
of a Mobile Application for a financial education authority.

The mobile application shall provide learning modules, event updates, quizzes,
resource downloads, multilingual content, feedback capture, and push
notifications for students, teachers, and public users.

The selected bidder shall integrate Mobile APIs provided by the authority to
access statistical data related to financial literacy initiatives and publish
initiative-wise dashboards in the application.

The application shall include backend database administration, content
management, mobile API integration, user acceptance testing, security audit
closure, application hosting, and support and maintenance services.

The application will be hosted only after successful acceptance testing and
reasonable compliance with the third-party security audit report.
"""


SEARCH_RFP_SAMPLE = """
Request for Proposal for Search Engine Enhancement using Natural Language
Processing for a government e-marketplace.

The buyer requires search string optimization, query intent understanding,
stop-word removal, stemming, lemmatization, tokenization, synonym handling,
and noise removal for product and service search queries.

The solution shall improve search relevance, ranking, category classification,
catalog mapping, seller category suggestion, and information retrieval quality.

The system shall integrate with the current Apache Solr search architecture,
existing web services, and microservice APIs consumed by the marketplace.

The selected bidder shall define model validation metrics, training data
requirements, relevance measurement, monitoring approach, and deployment plan.
"""


ETRM_RFP_SAMPLE = """
Request for Proposal for Software Development and IT Consulting Services.

CPA requires additional resources to complete a reproduction of the development
and build environment, complete updates to the ETRM application, and perform
other tasks as directed by CPA.

The scope includes migration of the current ETRM application to a dedicated host
in AWS, creation of a separate test environment, validation and testing of the
migrated ETRM application, and creation of a formal upgrade process for
releasing new versions of the ETRM application.

The contractor must protect the security and confidentiality of ETRM system
data and comply with CPRA and other applicable laws.
"""


def _payload() -> dict:
    result, meta = _deterministic_extract(GENERIC_RFP_SAMPLE)
    return _finalize_analysis_payload(result.model_dump(), GENERIC_RFP_SAMPLE, meta)


def _sample_intelligence(text: str) -> dict:
    result, meta = _deterministic_extract(text)
    payload = _finalize_analysis_payload(result.model_dump(), text, meta)
    return payload["raw_llm_output"]["rfp_intelligence"]


def test_tender_admin_noise_is_excluded_from_solution_fields() -> None:
    payload = _payload()
    report = payload["raw_llm_output"]["executive_report"]
    solution_text = " ".join(
        f"{item['requirement_name']} {item['description']}"
        for item in report["solution_scope"]
    ).lower()
    extracted_text = " ".join(
        [
            *payload["functional_requirements"],
            *payload["non_functional_requirements"],
            *payload["data_needs"],
            *payload["integration_needs"],
        ]
    ).lower()
    blocked = [
        "audited",
        "balance sheet",
        "statutory auditor",
        "emd",
        "bid submission",
        "pre-bid",
        "new delhi",
    ]

    assert "bids received after closing" not in extracted_text
    for term in blocked:
        assert term not in extracted_text
        assert term not in solution_text
    assert {item["category"] for item in report["excluded_noise"]} >= {
        "procurement_process",
        "bidder_eligibility",
    }


def test_generic_executive_report_is_populated_without_sample_specific_tags() -> None:
    payload = _payload()
    report = payload["raw_llm_output"]["executive_report"]

    assert payload["missing_information"]
    assert {"Workflow Automation", "API Integration", "Cloud/Hosted Deployment"} & set(payload["domain_tags"])
    assert report["ceo_brief"]
    assert report["bid_recommendation"]["decision"] in {
        "Strong Bid",
        "Bid with Clarifications",
        "Hold",
        "No Bid",
    }
    assert report["risk_assessment"]
    assert report["prospect_call_prep"]["must_ask_discovery_questions"]
    assert "raw_extraction_internal" in payload["raw_llm_output"]


def test_stale_analysis_response_is_marked_for_recovery() -> None:
    assert _analysis_needs_recovery(
        {"executive_intelligence": {}},
        [],
        ["mobile", "web_portal", "integration", "data", "reporting", "workflow"],
        GENERIC_RFP_SAMPLE,
    )


def test_current_rfp_intelligence_response_does_not_force_recovery() -> None:
    assert not _analysis_needs_recovery(
        {
            "executive_report": {"ceo_brief": "Internal legacy report."},
            "rfp_intelligence": {
                "sentiment_analysis": {"summary": "Current RFP intelligence."},
                "must_ask_questions": [{"question": "What outcome matters?"}],
                "architecture": {
                    "diagram": {
                        "nodes": [{"id": "workflow", "label": "Workflow services", "group": "Solution Core"}],
                        "edges": [],
                    }
                },
            },
        },
        ["Question"] * 3,
        ["Workflow Automation", "API Integration", "Cloud/Hosted Deployment"],
        GENERIC_RFP_SAMPLE,
    )


def test_leadership_analysis_response_hides_raw_debug_and_admin_noise() -> None:
    payload = sanitize_analysis_payload_for_leadership(_payload())
    raw = payload["raw_llm_output"]
    response_text = str(payload).lower()

    assert set(raw) == {"extraction_meta", "rfp_intelligence"}
    assert "raw_extraction_internal" not in raw
    assert "document_sections" not in raw
    assert "excluded_noise" not in raw
    assert "executive_report" not in raw
    assert "executive_intelligence" not in raw
    assert "audited balance sheet" not in response_text
    assert "statutory auditor" not in response_text
    assert "emd" not in response_text
    assert "bid submission" not in response_text
    assert "delivery-capacity" not in response_text
    assert payload["analysis_brief"]["top_questions"]
    assert raw["rfp_intelligence"]["must_ask_questions"]
    assert raw["rfp_intelligence"]["architecture"]
    assert raw["rfp_intelligence"]["architecture"]["diagram"]["nodes"]
    assert raw["rfp_intelligence"]["architecture"]["diagram"]["lanes"]
    assert raw["rfp_intelligence"]["architecture"]["diagram"]["primary_flow"]
    assert "workspace" in raw["rfp_intelligence"]["architecture"]["structurizr_dsl"]
    assert "architecture_text" not in raw["rfp_intelligence"]["architecture"]
    assert "mermaid" not in raw["rfp_intelligence"]["architecture"]


def test_rfp_intelligence_is_specific_to_each_rfp_not_static_templates() -> None:
    mobile = _sample_intelligence(MOBILE_RFP_SAMPLE)
    search = _sample_intelligence(SEARCH_RFP_SAMPLE)

    mobile_questions = {item["question"] for item in mobile["must_ask_questions"]}
    search_questions = {item["question"] for item in search["must_ask_questions"]}
    mobile_risks = {item["risk_title"] for item in mobile["top_risks"]}
    search_risks = {item["risk_title"] for item in search["top_risks"]}
    mobile_points = {item["point"] for item in mobile["talking_points"]}
    search_points = {item["point"] for item in search["talking_points"]}
    mobile_node_ids = {node["id"] for node in mobile["architecture"]["diagram"]["nodes"]}
    search_node_ids = {node["id"] for node in search["architecture"]["diagram"]["nodes"]}
    search_node_labels = {node["label"] for node in search["architecture"]["diagram"]["nodes"]}
    mobile_node_labels = {node["label"] for node in mobile["architecture"]["diagram"]["nodes"]}

    assert mobile_questions != search_questions
    assert mobile_risks != search_risks
    assert mobile_points != search_points
    assert mobile_node_ids != search_node_ids
    assert any("Mobile APIs" in question or "mobile" in question.lower() for question in mobile_questions)
    assert any("search" in question.lower() or "query" in question.lower() for question in search_questions)
    assert any("Mobile" in label or "learning" in label.lower() for label in mobile_node_labels)
    assert any("Search" in label or "query" in label.lower() or "NLP" in label for label in search_node_labels)
    assert "mobileApp" in mobile_node_ids
    assert "contentAdmin" in mobile_node_ids
    assert "queryUnderstanding" in search_node_ids
    assert "categoryClassifier" in search_node_ids
    assert "solrSearch" in search_node_ids
    assert any("Solr" in label or "query" in label.lower() for label in search_node_labels)


def test_fallback_intelligence_does_not_emit_reused_card_headings() -> None:
    intelligence = _sample_intelligence(SEARCH_RFP_SAMPLE)
    response_text = str(intelligence)
    forbidden_heading_fragments = [
        "Integration readiness:",
        "Data readiness:",
        "Control sign-off:",
        "Acceptance ambiguity:",
        "Timeline dependency:",
        "Scope signal:",
        "Project focus:",
        "Opportunity Signals",
        "Leadership Concerns",
    ]

    for fragment in forbidden_heading_fragments:
        assert fragment not in response_text

    assert any(item.get("category") for item in intelligence["must_ask_questions"])
    assert "components" not in intelligence["architecture"]
    assert "assumptions" not in intelligence["architecture"]


def test_etrm_call_prep_avoids_false_ai_and_weak_evidence() -> None:
    intelligence = _sample_intelligence(ETRM_RFP_SAMPLE)
    response_text = str(intelligence).lower()

    assert "validation dataset" not in response_text
    assert "retraining ownership" not in response_text
    assert "model acceptance" not in response_text
    assert "payguard" not in response_text
    assert intelligence["relevant_knowledge_evidence"] == []
    assert intelligence["narrative"]["title"].startswith("Evidence gap")

    questions = intelligence["must_ask_questions"]
    categories = {item.get("category") for item in questions}
    assert {"Cloud migration", "Testing and acceptance", "Release governance", "Security and compliance"} & categories
    assert any("AWS" in item["question"] or "cutover" in item["question"].lower() for item in questions)
    assert any("UAT" in item["question"] or "regression" in item["question"].lower() for item in questions)

    architecture = intelligence["architecture"]
    assert architecture["business_view"]
    assert architecture["technical_view"]
    assert architecture["security_operations"]
    assert architecture["diagram"]["notation"] == "Deployment flow / C4 container model"
    assert any(node["group"] == "Migration Core" for node in architecture["diagram"]["nodes"])
    assert architecture["diagram"]["executive_summary"]
    assert [lane["title"] for lane in architecture["diagram"]["lanes"]][:4] == [
        "1. Current estate",
        "2. Migration workstream",
        "3. Target runtime",
        "4. Validation and release",
    ]
    assert any("awsRuntime" in lane["node_ids"] for lane in architecture["diagram"]["lanes"])
    assert architecture["diagram"]["primary_flow"] == architecture["diagram"]["edges"]
    assert architecture["diagram"]["title"].startswith("Cloud Migration")
    assert {node["id"] for node in architecture["diagram"]["nodes"]} >= {
        "currentApplication",
        "migrationRunbook",
        "awsRuntime",
        "testEnvironment",
        "releasePipeline",
    }
    assert "container solution" in architecture["structurizr_dsl"]
    assert "components" not in architecture
    assert "assumptions" not in architecture


def test_rfp_analysis_ui_uses_executive_tab_set_only() -> None:
    page = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "RFPAnalysis.tsx"
    text = page.read_text(encoding="utf-8")
    assert "'Must-Ask Questions'" in text
    assert "'Top Risks'" in text
    assert "'Talking Points'" in text
    assert "'Narrative'" in text
    assert "'Relevant Knowledge Evidence'" in text
    assert "'Architecture'" in text
    assert "Sentiment Analysis" in text
    assert "Open War Room" in text
    assert "Architecture Detail" not in text
    assert "Mermaid Diagram" not in text
    assert "architecture.generated_by" not in text
    assert "gpt-oss" not in text
    tabs_block = text[text.index("const tabs = [") : text.index("]", text.index("const tabs = ["))]
    assert "'Leadership Snapshot'" not in tabs_block
    assert "'CEO Brief'" not in tabs_block
    assert "'Bid Decision'" not in tabs_block
    assert "'Commercial View'" not in tabs_block
    assert "'Past Expertise'" not in tabs_block
    assert "'Clean Scope'" not in tabs_block
    assert "'Excluded Tender/Admin Noise'" not in tabs_block
    assert "'Quality Checks'" not in tabs_block
    assert "'Debug / Source Extraction'" not in tabs_block
