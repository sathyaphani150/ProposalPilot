from __future__ import annotations

from app.services.rfp_engine import _deterministic_extract, _finalize_analysis_payload


GEM_SAMPLE = """
Request for Proposal for Search Engine Enhancement using Natural Language Processing
for Government e-Marketplace GeM.

GeM's existing keyword based search is not accurate enough. Buyers may fail to find
intended products or services, which can lead to non-availability claims and
procurement leakage away from GeM.

String Optimizer to isolate Product/Service Feature Information by performing
Stop word removal, Stemming, Lemmatization, Tokenization, Normalization and
Noise removal.

Use ML/NLP algorithms such as TF-IDF, word2vec, SVM and Naive Bayes for
product and service category classification.

The solution shall integrate with existing Apache Solr search architecture
through APIs and microservices.

Deployment shall be in GCC infrastructure with security controls and operation
and maintenance support.

Bids received after closing shall be rejected.
Bidder registration process shall be completed on the e-tendering portal.
Copy of audited balance sheet must be submitted.
Name of statutory auditor must be provided.
Blacklisting declaration as per annexure.
"""


def _payload() -> dict:
    result, meta = _deterministic_extract(GEM_SAMPLE)
    return _finalize_analysis_payload(result.model_dump(), GEM_SAMPLE, meta)


def test_gem_procurement_noise_is_not_solution_scope() -> None:
    payload = _payload()
    report = payload["raw_llm_output"]["executive_report"]
    solution_text = " ".join(
        f"{item['requirement_name']} {item['description']}"
        for item in report["solution_scope"]
    ).lower()
    functional_text = " ".join(payload["functional_requirements"]).lower()
    nfr_text = " ".join(payload["non_functional_requirements"]).lower()

    assert "bids received after closing" not in functional_text
    assert "copy of audited balance sheet" not in nfr_text
    assert "name of statutory auditor" not in nfr_text
    assert "audited balance sheet" not in solution_text
    assert "statutory auditor" not in solution_text
    assert {item["category"] for item in report["excluded_noise"]} >= {
        "procurement_process",
        "bidder_eligibility",
    }


def test_gem_real_solution_requirements_are_classified() -> None:
    payload = _payload()
    report = payload["raw_llm_output"]["executive_report"]
    names = {item["requirement_name"] for item in report["solution_scope"]}
    categories = {
        item["requirement_name"]: item["category"]
        for item in report["solution_scope"]
    }

    assert "NLP Search String Optimization" in names
    assert categories["NLP Search String Optimization"] == "Functional"
    assert "Apache Solr Integration" in names
    assert categories["Apache Solr Integration"] == "Integration"
    assert "GCC Hosting and Deployment" in names
    assert categories["GCC Hosting and Deployment"] == "Operational"


def test_gem_executive_intelligence_is_populated() -> None:
    payload = _payload()
    report = payload["raw_llm_output"]["executive_report"]

    assert len(payload["missing_information"]) >= 12
    assert {"NLP", "Search Optimization", "Apache Solr", "Product Category Classification"} <= set(
        payload["domain_tags"]
    )
    assert report["ceo_brief"]
    assert report["bid_recommendation"]["decision"] in {
        "Strong Bid",
        "Bid with Clarifications",
        "Hold",
        "No Bid",
    }
    assert report["risk_assessment"]
    assert report["prospect_call_prep"]["must_ask_discovery_questions"]
    assert report["quality_checks"]["checks"]["procurement_instructions_excluded_from_scope"]
