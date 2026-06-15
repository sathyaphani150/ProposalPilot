from __future__ import annotations

from pathlib import Path

from app.services.rfp_engine import _deterministic_extract, _finalize_analysis_payload
from app.services.rfp_service import _analysis_needs_recovery


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


def _payload() -> dict:
    result, meta = _deterministic_extract(GENERIC_RFP_SAMPLE)
    return _finalize_analysis_payload(result.model_dump(), GENERIC_RFP_SAMPLE, meta)


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


def test_current_executive_report_response_does_not_force_recovery() -> None:
    assert not _analysis_needs_recovery(
        {"executive_report": {"ceo_brief": "Current executive report."}},
        ["Question"] * 3,
        ["Workflow Automation", "API Integration", "Cloud/Hosted Deployment"],
        GENERIC_RFP_SAMPLE,
    )


def test_rfp_analysis_ui_keeps_raw_extraction_in_debug_tab() -> None:
    page = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "RFPAnalysis.tsx"
    text = page.read_text(encoding="utf-8")
    assert "'Leadership Snapshot'" in text
    assert "'CEO Brief'" in text
    assert "'Top Risks'" in text
    assert "'Must-Ask Questions'" in text
    assert "'Commercial View'" in text
    assert "'Past Expertise'" in text
    assert "'Clean Scope'" in text
    assert "'Excluded Tender/Admin Noise'" in text
    assert "'Quality Checks'" in text
    assert "'Debug / Source Extraction'" in text
    assert text.index("'Leadership Snapshot'") < text.index("'Debug / Source Extraction'")
    assert "Show Debug Extraction" in text
