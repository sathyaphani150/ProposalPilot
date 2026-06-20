"""
ProposalPilot AI - RFP Understanding Engine.

The engine prefers structured LLM extraction, but never fabricates fallback
answers. If the LLM path fails, it returns a conservative source-text-only
analysis so the workflow remains demo-stable without hallucinating.
"""
from __future__ import annotations

import re
from collections.abc import Collection
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field, field_validator

from app.config import get_settings
from app.services.llm_service import get_llm_service
from app.services.rfp_taxonomy import (
    ADMIN_TERMS as _ADMIN_TERMS,
    CAPABILITY_LABELS,
    CAPABILITY_TAG_KEYWORDS as _CAPABILITY_TAG_KEYWORDS,
    DELIVERY_TERMS as _DELIVERY_TERMS,
    EVIDENCE_STOPWORDS as _EVIDENCE_STOPWORDS,
    EXCLUDED_SECTION_CATEGORIES as _EXCLUDED_SECTION_CATEGORIES,
    GENERIC_SIGNAL_TERMS as _GENERIC_SIGNAL_TERMS,
    INFRA_OPERATIONAL_SIGNAL_TERMS as _INFRA_OPERATIONAL_SIGNAL_TERMS,
    INTEGRATION_SIGNAL_TERMS as _INTEGRATION_SIGNAL_TERMS,
    RFP_SIGNAL_CATEGORY_KEYWORDS as _CATEGORY_KEYWORDS,
    SECTION_CATEGORIES as _SECTION_CATEGORIES,
    SECTION_CATEGORY_RULES,
    SECTION_CLASSIFIER_TERMS,
    TECHNICAL_SIGNAL_TERMS as _TECHNICAL_SIGNAL_TERMS,
    TRUST_GATE_NOISE_TERMS as _TRUST_GATE_NOISE_TERMS,
)

settings = get_settings()


class RFPExtractionOutput(BaseModel):
    """Structured output from RFP analysis."""

    business_problem: str = Field(
        description="Core business problem stated or strongly implied by the document."
    )
    functional_requirements: list[str] = Field(default_factory=list)
    non_functional_requirements: list[str] = Field(default_factory=list)
    data_needs: list[str] = Field(default_factory=list)
    integration_needs: list[str] = Field(default_factory=list)
    compliance_needs: list[str] = Field(default_factory=list)
    timeline_risks: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    scope_boundaries: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    estimated_complexity: str = Field(description="low | medium | high | very_high")

    @field_validator("estimated_complexity")
    @classmethod
    def normalize_complexity(cls, value: str) -> str:
        normalized = value.lower().strip().replace(" ", "_").replace("-", "_")
        if normalized not in {"low", "medium", "high", "very_high"}:
            return "medium"
        return normalized


class ExecutiveInsightOutput(BaseModel):
    title: str
    insight: str
    evidence: str
    source: str
    confidence: float
    recommendation: str


class ExecutiveIntelligenceOutput(BaseModel):
    executive_summary: str
    key_insights: list[ExecutiveInsightOutput] = Field(default_factory=list)
    opportunity_assessment: list[ExecutiveInsightOutput] = Field(default_factory=list)
    business_drivers: list[str] = Field(default_factory=list)
    risks_and_dependencies: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    discovery_strategy: list[str] = Field(default_factory=list)


class RFPSentimentPointOutput(BaseModel):
    title: str = Field(description="Short, RFP-specific heading derived from a source fact.")
    insight: str
    evidence: str
    implication: str


class RFPSentimentOutput(BaseModel):
    overall_sentiment: str
    summary: str
    confidence: str
    recommended_posture: str
    points: list[RFPSentimentPointOutput] = Field(default_factory=list)


class RFPMustAskQuestionOutput(BaseModel):
    question: str
    why_it_matters: str
    assumption_to_validate: str
    evidence: str = ""


class RFPTopRiskOutput(BaseModel):
    risk_title: str = Field(description="Specific risk heading based on an actual RFP dependency or requirement.")
    severity: str
    probability: str
    impact: str
    mitigation: str
    owner: str
    evidence: str = ""


class RFPTalkingPointOutput(BaseModel):
    point: str
    client_angle: str
    proof_needed: str
    evidence: str = ""


class RFPNarrativeOutput(BaseModel):
    title: str
    story: str
    how_it_helps: list[str] = Field(default_factory=list)
    evidence_project_title: str = ""
    confidence: str


class RFPArchitectureOutput(BaseModel):
    summary: str
    business_view: list[str] = Field(default_factory=list)
    technical_view: list[str] = Field(default_factory=list)
    data_flow: list[str] = Field(default_factory=list)
    integration_flow: list[str] = Field(default_factory=list)
    security_operations: list[str] = Field(default_factory=list)
    decision_points: list[str] = Field(default_factory=list)
    call_prep_questions: list[str] = Field(default_factory=list)
    diagram: dict[str, Any] = Field(default_factory=dict)
    structurizr_dsl: str = ""


class RFPIntelligenceOutput(BaseModel):
    sentiment_analysis: RFPSentimentOutput
    must_ask_questions: list[RFPMustAskQuestionOutput] = Field(default_factory=list)
    top_risks: list[RFPTopRiskOutput] = Field(default_factory=list)
    talking_points: list[RFPTalkingPointOutput] = Field(default_factory=list)
    narrative: RFPNarrativeOutput
    architecture: RFPArchitectureOutput


_SYSTEM_PROMPT = """
You are a senior pre-sales solutions architect and RFP analyst.

Extract only facts that are present in the source document. Do not invent
features, integrations, dates, compliance needs, competitors, budgets, team
sizes, or technology choices.

Rules:
- Return valid JSON matching the requested schema.
- If the source is silent for a category, return an empty list.
- Every bullet must be specific and traceable to source wording.
- Put unknowns in missing_information instead of guessing.
- Use estimated_complexity only as low, medium, high, or very_high.
"""


_EXECUTIVE_SYSTEM_PROMPT = """
You are a senior strategy consultant, solution architect, and pursuit lead.

Your job is to create executive intelligence from an RFP. Do not summarize
sections. Do not copy tender boilerplate. Do not invent client facts.

Every insight must help a Director, CEO, CTO, VP, or Consulting Partner decide:
- Is this opportunity worth pursuing?
- What business problem is likely behind the RFP?
- What must we validate before pricing or committing scope?
- What risks, dependencies, and strategic implications matter?

Rules:
- Return valid JSON matching the schema.
- Use concise consulting language.
- Mark source as exactly one of: explicit_in_rfp, inferred_from_rfp, derived_from_industry_knowledge.
- Evidence must be a short source-grounded phrase, not a long copied paragraph.
- Confidence must be between 0.0 and 1.0.
- Avoid generic filler and avoid bid-submission/procurement boilerplate.
"""



def _strip_reference_noise(text: str) -> str:
    text = re.sub(r"\.{4,}\s*\d+\s*$", "", text)
    text = re.sub(r"\s+\.{4,}\s*", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" -:\t")


def _is_probably_heading(line: str) -> bool:
    words = re.findall(r"[A-Za-z]+", line)
    if not words:
        return True
    upper_words = sum(1 for word in words if word.isupper() and len(word) > 2)
    return len(words) <= 8 and upper_words / len(words) > 0.65


def _is_noise_line(line: str) -> bool:
    lower = line.lower()
    if _is_tender_boilerplate(line):
        return True
    if re.search(r"\.{4,}\s*\d+\s*$", line):
        return True
    if re.fullmatch(r"\d+(\.\d+)*", line):
        return True
    if len(line) < 18:
        return True
    if _is_probably_heading(line) and not any(term in lower for term in _DELIVERY_TERMS):
        return True
    toc_terms = {
        "table of contents",
        "contents",
        "list of tables",
        "annexure",
        "document reference number",
        "checklist of documents",
        "classification: internal",
        "page ",
    }
    if any(term == lower or lower.startswith(term) for term in toc_terms):
        return True
    legal_noise = {
        "the information contained in this rfp",
        "rfp document is not a recommendation",
        "no contractual obligation",
        "shall not be copied",
        "copyright violation",
        "exclusive use of",
        "makes no representation or warranty",
        "bidder should conduct their own",
        "download the tender document",
        "online on e tendering portal",
        "submitted in physical form",
        "upload supporting documents",
        "mapped documents",
    }
    if any(term in lower for term in legal_noise):
        return True
    return False


def _clean_lines(raw_text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in re.split(r"[\r\n]+", raw_text):
        line = _strip_reference_noise(re.sub(r"\s+", " ", raw_line))
        if line and not _is_noise_line(line):
            lines.append(line)
    return lines


def _looks_actionable(line: str) -> bool:
    lower = line.lower()
    action_terms = {
        "shall",
        "must",
        "should",
        "required",
        "require",
        "provide",
        "support",
        "enable",
        "integrate",
        "develop",
        "implement",
        "maintain",
        "secure",
        "facilitate",
        "submit",
        "deliver",
        "configure",
    }
    return any(term in lower for term in action_terms)


def _is_admin_only(line: str) -> bool:
    lower = line.lower()
    return any(term in lower for term in _ADMIN_TERMS) and not any(
        term in lower for term in _DELIVERY_TERMS
    )


def _is_tender_boilerplate(line: str) -> bool:
    lower = line.lower()
    boilerplate_terms = {
        "procedure & submission",
        "procedure and submission",
        "format for bid",
        "bid-security declaration",
        "performance bank guarantee",
        "evaluated bid score",
        "technical score",
        "bid price",
        "bidder should enclose",
        "response to the bid",
        "read in consonance",
        "addendum",
        "addenda",
        "last date of submission",
        "committee will evaluate",
        "certifying authority",
        "digital signature",
        "e-tender",
        "online on e",
        "mapped documents",
        "pre-contract integrity pact",
        "authorization to bid",
        "bidder should conduct",
        "no contractual obligation",
        "not a recommendation",
        "copyright violation",
        "property of",
        "bids received after closing",
        "shall be rejected",
        "bidder registration",
        "registered bidder",
        "copy of audited balance sheet",
        "audited balance sheet",
        "name of statutory auditor",
        "statutory auditor",
        "blacklisting declaration",
        "turnover criteria",
        "net worth certificate",
        "pre-bid meeting",
        "pre bid meeting",
        "earnest money deposit",
        "emd",
        "annexure",
        "certificate of incorporation",
        "ca certificate",
        "iso certificate",
        "cmmi",
        "bid validity",
        "corrigendum",
        "queries from bidders",
        "bidder shall bear",
        "cost of bid",
        "independent advice",
        "reserves right to reject",
        "no liability",
        "no representation",
    }
    return any(term in lower for term in boilerplate_terms)


def _is_low_value_unit(unit: str) -> bool:
    lower = unit.lower()
    if _is_tender_boilerplate(unit):
        return True
    low_value_terms = {
        "terms and conditions set out",
        "purpose of bidding",
        "specification, terms, condition",
        "provided to the bidder",
        "bidder may require",
        "accuracy, reliability and completeness",
        "formal contract is signed",
        "duly authorized officers",
        "valid certifying authority",
        "bid document through offline",
        "copy of the audited",
        "copy of audited",
        "this rfp document includes statements",
        "this rfp document may not be appropriate",
        "not possible for",
        "investment objectives",
        "financial situation",
        "particular needs of each party",
        "costs and expenses will remain with the bidder",
        "shall not be liable",
        "date of commencement of bidding process",
    }
    return any(term in lower for term in low_value_terms)


def _contains_any(text: str, terms: Collection[str]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def _has_solution_signal(text: str) -> bool:
    return _contains_any(text, _TECHNICAL_SIGNAL_TERMS | _INTEGRATION_SIGNAL_TERMS | _INFRA_OPERATIONAL_SIGNAL_TERMS)


def _has_trust_gate_noise(text: str) -> bool:
    lower = f" {text.lower()} "
    return any(term in lower for term in _TRUST_GATE_NOISE_TERMS)


def _is_solution_scope_noise(text: str) -> bool:
    lower = text.lower()
    if _contains_any(lower, _TECHNICAL_SIGNAL_TERMS | _INTEGRATION_SIGNAL_TERMS):
        return False
    return _has_trust_gate_noise(text) or _is_tender_boilerplate(text) or _is_admin_only(text)


def _dedupe(items: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = re.sub(r"[^a-z0-9]+", " ", item.lower()).strip()
        if len(normalized) < 16 or normalized in seen:
            continue
        if any(normalized in existing or existing in normalized for existing in seen):
            continue
        seen.add(normalized)
        output.append(item)
    return output


def _candidate_units(raw_text: str) -> list[str]:
    text = re.sub(r"\r\n?", "\n", raw_text)
    text = re.sub(r"\.{4,}\s*\d+", " ", text)
    text = re.sub(r"\n(?=[a-z,(])", " ", text)
    raw_units = re.split(r"(?<=[.;:?])\s+|\n+", text)
    units: list[str] = []
    for unit in raw_units:
        cleaned = _strip_reference_noise(re.sub(r"\s+", " ", unit))
        if cleaned and not _is_noise_line(cleaned) and not _is_low_value_unit(cleaned):
            units.append(cleaned[:650])
    return _dedupe(units)


def _raw_document_units(raw_text: str) -> list[str]:
    text = re.sub(r"\r\n?", "\n", raw_text)
    text = re.sub(r"\.{4,}\s*\d+", " ", text)
    text = re.sub(r"\n(?=[a-z,(])", " ", text)
    raw_units = re.split(r"(?<=[.;:?])\s+|\n+", text)
    units: list[str] = []
    for unit in raw_units:
        cleaned = _strip_reference_noise(re.sub(r"\s+", " ", unit))
        if len(cleaned) >= 12:
            units.append(cleaned[:650])
    return _dedupe(units)


def _pick_units(
    units: list[str],
    keywords: set[str],
    *,
    limit: int,
    require_actionable: bool = False,
    exclude_admin_only: bool = False,
) -> list[str]:
    matches: list[str] = []
    for unit in units:
        lower = unit.lower()
        if any(keyword in lower for keyword in keywords):
            if _is_low_value_unit(unit):
                continue
            if require_actionable and not _looks_actionable(unit):
                continue
            if exclude_admin_only and _is_admin_only(unit):
                continue
            matches.append(unit)
        if len(matches) >= limit:
            break
    return _dedupe(matches)[:limit]


def _classify_document_section(unit: str) -> tuple[str, float, str]:
    lower = unit.lower()
    eligibility_terms = SECTION_CLASSIFIER_TERMS["eligibility"]
    procurement_terms = SECTION_CLASSIFIER_TERMS["procurement"]
    legal_terms = SECTION_CLASSIFIER_TERMS["legal"]
    contact_terms = SECTION_CLASSIFIER_TERMS["contact"]
    compliance_terms = SECTION_CLASSIFIER_TERMS["compliance"]

    if any(term in lower for term in contact_terms) and not _has_solution_signal(lower):
        return "buyer_contact_or_location", 0.94, "Buyer address/contact/location text, not solution scope."
    if any(term in lower for term in legal_terms) and not _has_solution_signal(lower):
        return "legal_disclaimer", 0.94, "Legal/disclaimer language, not delivery scope."
    if any(term in lower for term in eligibility_terms) and not _has_solution_signal(lower):
        return "bidder_eligibility", 0.95, "Bidder qualification or financial evidence requirement."
    if any(term in lower for term in procurement_terms) and not _has_solution_signal(lower):
        return "procurement_process", 0.95, "Tender process instruction."
    if any(term in lower for term in _INTEGRATION_SIGNAL_TERMS):
        return "integration_requirement", 0.94, "Integration or platform touchpoint."
    if any(term in lower for term in _TECHNICAL_SIGNAL_TERMS):
        return "technical_requirement", 0.94, "Technical solution feature."
    if any(term in lower for term in _INFRA_OPERATIONAL_SIGNAL_TERMS):
        return "infrastructure_operational_requirement", 0.88, "Deployment, hosting, support, or operations requirement."
    if any(term in lower for term in compliance_terms):
        return "compliance_security", 0.86, "Security, compliance, confidentiality, or IPR requirement."

    for rule in SECTION_CATEGORY_RULES:
        if any(keyword in lower for keyword in rule.keywords):
            confidence = 0.86 if rule.category in _EXCLUDED_SECTION_CATEGORIES or rule.category in {"technical_requirement", "integration_requirement"} else 0.74
            return rule.category, confidence, rule.reason
    if _is_tender_boilerplate(unit) or _is_low_value_unit(unit):
        return "irrelevant_noise", 0.72, "Low-value tender boilerplate or document noise."
    return "irrelevant_noise", 0.45, "No clear business, technical, delivery, or compliance signal."


def _classify_document_sections(raw_text: str, *, limit: int = 80) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for unit in _raw_document_units(raw_text):
        category, confidence, reason = _classify_document_section(unit)
        sections.append(
            {
                "category": category,
                "text": unit,
                "confidence": round(confidence, 2),
                "reason": reason,
            }
        )
        if len(sections) >= limit:
            break
    return sections


def _excluded_noise_from_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    excluded: list[dict[str, Any]] = []
    for section in sections:
        if section["category"] in _EXCLUDED_SECTION_CATEGORIES:
            excluded.append(
                {
                    "category": section["category"],
                    "text": section["text"],
                    "why_excluded": section["reason"],
                    "confidence": section["confidence"],
                }
            )
    return excluded[:24]


def _infer_domain_tags(raw_text: str) -> list[str]:
    lower = raw_text.lower()
    tags = [
        tag
        for tag, keywords in _CAPABILITY_TAG_KEYWORDS.items()
        if any(_contains_term(lower, keyword) for keyword in keywords)
    ]
    if _has_search_nlp_signals(lower):
        required_search_tags = [
            "NLP",
            "Search Optimization",
            "Information Retrieval",
            "Query Understanding",
            "Machine Learning",
            "Search Relevance",
        ]
        if any(term in lower for term in ("category", "catalog", "taxonomy", "seller", "classification")):
            required_search_tags.extend(["Product Category Classification", "Catalog Management"])
        if any(term in lower for term in ("api", "microservice", "micro-service", "integration", "web service")):
            required_search_tags.append("API Integration")
        if any(term in lower for term in ("cloud", "deployment", "hosting")):
            required_search_tags.append("Cloud/Hosted Deployment")
        tags = [*required_search_tags, *tags]
    if not tags:
        generic_rules = {
            "Workflow Automation": {"workflow", "approval", "case management"},
            "Reporting & Analytics": {"report", "dashboard", "analytics", "metrics"},
            "Web Portal": {"portal", "website", "web application"},
            "Application Modernization": {"application", "software", "system"},
        }
        tags = [
            tag
            for tag, keywords in generic_rules.items()
            if any(_contains_term(lower, keyword) for keyword in keywords)
        ]
    unique_tags: list[str] = []
    seen_tags: set[str] = set()
    for tag in tags:
        normalized = tag.lower()
        if normalized not in seen_tags:
            seen_tags.add(normalized)
            unique_tags.append(tag)
    return unique_tags[:12]


def _contains_term(text: str, term: str) -> bool:
    if " " in term:
        return term in text
    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def _has_search_nlp_signals(lower_text: str) -> bool:
    search_terms = ("search", "query", "solr", "string optimizer", "relevance")
    nlp_terms = (
        "natural language processing",
        "nlp",
        "lemmatization",
        "stemming",
        "tokenization",
        "tf-idf",
        "word2vec",
        "svm",
        "naive bayes",
        "category classification",
    )
    return any(term in lower_text for term in search_terms) and any(term in lower_text for term in nlp_terms)


def _estimate_complexity(analysis: dict[str, Any], raw_text: str) -> str:
    signal_count = sum(
        len(analysis[key])
        for key in (
            "functional_requirements",
            "non_functional_requirements",
            "data_needs",
            "integration_needs",
            "compliance_needs",
            "timeline_risks",
        )
    )
    lower = raw_text.lower()
    if signal_count >= 18 or any(word in lower for word in ("multi-agent", "real-time", "compliance", "migration", "apache solr", "natural language processing", "gcc")):
        return "high"
    if signal_count >= 8:
        return "medium"
    return "low"


def _normalized_source_text(raw_text: str) -> str:
    return re.sub(r"\s+", " ", raw_text.replace("\r", "\n")).strip()


def _extract_opportunity_title(raw_text: str) -> str:
    text = _normalized_source_text(raw_text[:8_000])
    patterns = (
        r"Request for Proposal(?:\s*\(RFP\))?\s+for\s+(.{20,180}?)(?:\.| Department| Page | Classification| \d{1,2}/\d{1,2}|$)",
        r"RFP for\s+(.{12,160}?)(?:\.| Page | Classification| Department|$)",
        r"Empanelment of\s+(.{12,140}?)(?:\.| Page | Classification| Department|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            title = _strip_reference_noise(match.group(1))
            title = re.sub(r"\bPage\s+\d+.*$", "", title, flags=re.IGNORECASE).strip(" -.")
            if title and not _is_low_value_unit(title):
                return title[:220]
    for line in _clean_lines(raw_text)[:40]:
        if any(term in line.lower() for term in ("rfp for", "request for proposal", "empanelment")):
            return line[:220]
    return ""


def _extract_client_name(raw_text: str) -> str:
    text = _normalized_source_text(raw_text[:6_000])
    known_patterns = (
        r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,4}\s+Bank(?:\s+of\s+[A-Z][A-Za-z]+)?)\b",
        r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,5}\s+(?:Limited|Ltd|Corporation|Authority|University|Institute))\b",
        r"\b((?:Department|Ministry)\s+of\s+[A-Z][A-Za-z& ]{3,80})\b",
    )
    for pattern in known_patterns:
        match = re.search(pattern, text)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip(" ,.-")
            if value.lower() not in {"request for proposal"}:
                return value[:160]
    return ""


def _business_problem_from_source(units: list[str], raw_text: str) -> str:
    lower = raw_text.lower()
    opportunity_title = _extract_opportunity_title(raw_text)
    client_name = _extract_client_name(raw_text)
    if opportunity_title:
        capabilities = _capability_labels(_infer_domain_tags(raw_text))
        prefix = f"{client_name} is " if client_name else "The buyer is "
        if capabilities:
            return (
                prefix
                + "seeking "
                + opportunity_title
                + ", with strategic implications around "
                + ", ".join(capabilities[:4])
                + "."
            )
        return prefix + "seeking " + opportunity_title + "."

    direct = _pick_units(
        units,
        {"objective", "purpose", "scope of work", "project requirement", "key processes", "proposed", "portal", "system", "module", "migration", "integration"},
        limit=5,
        exclude_admin_only=True,
    )
    direct = [item for item in direct if not _is_tender_boilerplate(item)]
    if direct:
        themes = _infer_domain_tags(raw_text)
        if themes:
            labels = _capability_labels(themes)
            return (
                "The opportunity appears to be a "
                + ", ".join(labels[:3])
                + " initiative. The clearest source signal is: "
                + direct[0]
            )
        return "The opportunity appears to center on: " + direct[0]

    capability_keywords = {
        "application": "application delivery",
        "mobile": "mobile experience",
        "portal": "portal/workflow delivery",
        "api": "API or system integration",
        "database": "data management",
        "dashboard": "reporting/dashboarding",
        "security": "security controls",
        "support": "support and maintenance",
        "migration": "migration",
        "analytics": "analytics",
    }
    capabilities = [
        label
        for keyword, label in capability_keywords.items()
        if keyword in lower
    ]
    domain_tags = _infer_domain_tags(raw_text)
    if capabilities:
        prefix = "The document appears to request "
        if domain_tags:
            prefix = f"The document appears to request {', '.join(domain_tags[:2])} solution work involving "
        return prefix + ", ".join(capabilities[:4]) + "."

    organization_match = re.search(
        r"(?:for|by)\s+([A-Z][A-Za-z0-9&.,'() -]{3,80})",
        raw_text[:3_000],
    )
    if organization_match:
        return (
            "The source document describes a requirement or procurement for "
            f"{organization_match.group(1).strip()} but does not state a concise business problem."
        )
    return "No explicit business problem was found in the source document."


def _critical_gaps(analysis: dict[str, Any]) -> list[str]:
    gap_rules = (
        (
            "Not specified clearly enough: measurable business outcomes and success metrics.",
            ("business_problem",),
        ),
        (
            "Not specified clearly enough: source systems, data owners, data quality constraints, retention, and reporting cadence.",
            ("data_needs",),
        ),
        (
            "Not specified clearly enough: integration owners, API documentation, sandbox access, credentials, and sample payloads.",
            ("integration_needs",),
        ),
        (
            "Not specified clearly enough: hosting/deployment model, security controls, access control, audit logging, and compliance approvals.",
            ("non_functional_requirements", "compliance_needs"),
        ),
        (
            "Not specified clearly enough: acceptance criteria, UAT process, sign-off authority, and go-live readiness gates.",
            ("scope_boundaries",),
        ),
        (
            "Not specified clearly enough: implementation timeline, buyer dependencies, support expectations, and change-control process.",
            ("timeline_risks",),
        ),
    )
    gaps: list[str] = []
    for gap, keys in gap_rules:
        if not any(analysis.get(key) for key in keys):
            gaps.append(gap)
    return gaps


def _specific_items(items: Any, *, limit: int = 4, keywords: Collection[str] | None = None) -> list[str]:
    if not isinstance(items, list):
        return []
    cleaned: list[str] = []
    for item in items:
        text = _strip_reference_noise(re.sub(r"\s+", " ", str(item))).strip()
        if not text or _is_low_value_unit(text) or _is_tender_boilerplate(text) or _is_admin_only(text):
            continue
        lower = text.lower()
        if any(term in lower for term in _GENERIC_SIGNAL_TERMS):
            continue
        if keywords and not any(_contains_term(lower, keyword) for keyword in keywords):
            continue
        if len(re.findall(r"[A-Za-z0-9]+", text)) < 3:
            continue
        cleaned.append(text[:320])
        if len(cleaned) >= limit:
            break
    return _dedupe(cleaned)[:limit]


def _short_signal(text: str, *, words: int = 11, max_chars: int = 110) -> str:
    cleaned = _strip_reference_noise(re.sub(r"\s+", " ", str(text))).strip(" .:-")
    cleaned = re.sub(r"^(the buyer is seeking\s+)?request for proposal\s*(\(rfp\))?\s*(for)?\s*", "", cleaned, flags=re.IGNORECASE).strip(" .:-")
    cleaned = re.sub(r"^rfp\s*(for)?\s*", "", cleaned, flags=re.IGNORECASE).strip(" .:-")
    tokens = re.findall(r"[A-Za-z0-9&/+.-]+", cleaned)
    label_tokens = tokens[:words]
    while label_tokens and label_tokens[-1].lower() in {"of", "for", "to", "and", "or", "the", "a", "an"}:
        label_tokens.pop()
    label = " ".join(label_tokens).strip()
    return (label or cleaned)[:max_chars].strip(" .:-")


def _has_domain_terms(text: str, terms: set[str]) -> bool:
    lower = text.lower()
    return any(_contains_term(lower, term) for term in terms)


def _analysis_signals(analysis: dict[str, Any] | None) -> dict[str, list[str]]:
    source = analysis or {}
    data_signals = _specific_items(source.get("data_needs"), limit=4, keywords=_CATEGORY_KEYWORDS["data"])
    data_signals = [
        item
        for item in data_signals
        if not _contains_any(
            item,
            {
                "security",
                "confidentiality",
                "confidential",
                "privacy",
                "compliance",
                "cpra",
                "audit",
                "access control",
            },
        )
    ]
    return {
        "functional": _specific_items(source.get("functional_requirements"), limit=5, keywords=_CATEGORY_KEYWORDS["functional"]),
        "non_functional": _specific_items(source.get("non_functional_requirements"), limit=4, keywords=_CATEGORY_KEYWORDS["control"]),
        "data": data_signals,
        "integration": _specific_items(source.get("integration_needs"), limit=4, keywords=_CATEGORY_KEYWORDS["integration"]),
        "compliance": _specific_items(source.get("compliance_needs"), limit=4, keywords=_CATEGORY_KEYWORDS["control"]),
        "timeline": _specific_items(source.get("timeline_risks"), limit=3, keywords=_CATEGORY_KEYWORDS["timeline"]),
        "scope": _specific_items(source.get("scope_boundaries"), limit=3, keywords=_CATEGORY_KEYWORDS["scope"]),
    }


def _rfp_focus(analysis: dict[str, Any] | None, raw_text: str) -> str:
    source = analysis or {}
    focus_source = (
        _extract_opportunity_title(raw_text)
        or (_specific_items(source.get("functional_requirements"), limit=1) or [""])[0]
        or str(source.get("business_problem") or "")
        or "this initiative"
    )
    focus_source = re.split(r",?\s+with strategic implications\b", focus_source, maxsplit=1, flags=re.IGNORECASE)[0]
    return _short_signal(focus_source, words=13, max_chars=120) or "this initiative"


def _missing_information_questions(
    raw_text: str,
    tags: list[str],
    analysis: dict[str, Any] | None = None,
) -> list[str]:
    signals = _analysis_signals(analysis)
    business_problem = _rfp_focus(analysis, raw_text)
    questions: list[str] = [
        f"What measurable outcome would make {business_problem} successful from the buyer's point of view?",
    ]

    for item in signals["functional"][:3]:
        label = _short_signal(item)
        lower_label = label.lower()
        if any(term in lower_label for term in ("migration", "migrated", "dedicated host", "aws", "environment")):
            questions.append(f"For '{label}', what current infrastructure, dependencies, AWS account/VPC/IAM constraints, cutover window, rollback plan, and acceptance evidence must be confirmed?")
        elif any(term in lower_label for term in ("test", "testing", "validation", "uat")):
            questions.append(f"For '{label}', who owns test data, regression scenarios, defect triage, UAT sign-off, and remediation acceptance?")
        elif any(term in lower_label for term in ("upgrade", "release", "version")):
            questions.append(f"For '{label}', what release governance, branching/build process, approval path, rollback rule, and production promotion evidence are expected?")
        else:
            questions.append(f"What exact workflow, roles, dependencies, and acceptance evidence should define completion for '{label}'?")

    for item in signals["integration"][:3]:
        label = _short_signal(item)
        questions.append(f"What interface contract, owner, environment, credentials, sample payloads, and test window are available for '{label}'?")

    for item in signals["data"][:3]:
        label = _short_signal(item)
        questions.append(f"Who owns '{label}', and what quality, migration, retention, and reconciliation rules must the proposal assume?")

    for item in [*signals["non_functional"][:2], *signals["compliance"][:2]]:
        label = _short_signal(item)
        questions.append(f"Which go-live evidence, reviewer, remediation window, and sign-off gate apply to '{label}'?")

    for item in signals["timeline"][:2]:
        label = _short_signal(item)
        questions.append(f"For the timeline or milestone signal '{label}', which client-side dependencies can move the date, and what change-control trigger should apply?")

    for item in signals["scope"][:2]:
        label = _short_signal(item)
        questions.append(f"For '{label}', what is explicitly out of scope, buyer-owned, or handled during support/O&M rather than initial build?")

    lower = raw_text.lower()
    if "test environment" in lower or "validation and testing" in lower:
        questions.append("For the separate test environment and migrated application validation, who owns test data, regression scenarios, defect triage, UAT sign-off, and remediation acceptance?")
    if "upgrade process" in lower or "releasing new versions" in lower:
        questions.append("For the formal upgrade process, what release governance, build packaging, approval path, rollback rule, and production promotion evidence are expected?")
    if _has_domain_terms(lower, {"model", "machine learning", "ai", "nlp", "classification", "prediction"}):
        ai_label = _short_signal((signals["functional"] or signals["data"] or ["AI/model requirement"])[0])
        questions.append(f"What validation dataset, relevance metric, error-review process, monitoring, and retraining ownership will be accepted for '{ai_label}'?")
    if _has_domain_terms(lower, {"mobile", "portal", "dashboard", "workflow", "user"}):
        ux_label = _short_signal((signals["functional"] or ["user-facing workflow"])[0])
        questions.append(f"Which user roles, journeys, approval states, notifications, and accessibility expectations are in scope for '{ux_label}'?")

    if len(questions) < 8:
        for gap in _critical_gaps(analysis or {}):
            questions.append(gap.replace("Not specified clearly enough: ", "Can the client confirm ").rstrip(".") + "?")

    return _dedupe(questions)[:16]


def _evidence_for(raw_text: str, keywords: set[str], fallback: str = "") -> str:
    for unit in _raw_document_units(raw_text):
        lower = unit.lower()
        if any(keyword in lower for keyword in keywords):
            return unit[:260]
    return fallback[:260]


def _requirement(
    name: str,
    description: str,
    category: str,
    priority: str,
    evidence: str,
    interpretation: str,
    confidence: str = "high",
) -> dict[str, Any]:
    return {
        "requirement_name": name,
        "description": description,
        "category": category,
        "priority": priority,
        "evidence": evidence,
        "interpretation": interpretation,
        "confidence": confidence,
        "assumption": confidence == "low",
    }


def _normalized_requirements(raw_text: str, analysis: dict[str, Any]) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    legacy_sources = [
        ("Functional", analysis.get("functional_requirements", [])),
        ("Non-functional", analysis.get("non_functional_requirements", [])),
        ("Integration", analysis.get("integration_needs", [])),
        ("Data", analysis.get("data_needs", [])),
        ("Compliance", analysis.get("compliance_needs", [])),
        ("Operational", analysis.get("scope_boundaries", [])),
    ]
    existing_names = {item["requirement_name"].lower() for item in requirements}
    for category, items in legacy_sources:
        for item in items:
            text = str(item)
            if _is_tender_boilerplate(text) or _is_admin_only(text):
                continue
            words = re.findall(r"[A-Za-z0-9+/.-]+", text)
            name = " ".join(words[:7]).strip()
            if not name or name.lower() in existing_names:
                continue
            requirements.append(
                _requirement(
                    name=name[:90],
                    description=text[:320],
                    category=category,
                    priority="Medium",
                    evidence=text[:260],
                    interpretation="Source-grounded requirement retained from extraction; review during solution scoping.",
                    confidence="medium",
                )
            )
            existing_names.add(name.lower())
            if len(requirements) >= 18:
                break
    return requirements[:18]


def _score_bid(analysis: dict[str, Any], requirements: list[dict[str, Any]], raw_text: str) -> dict[str, int]:
    tags = set(analysis.get("domain_tags", []))
    signal_count = sum(
        len(analysis.get(key, []) or [])
        for key in (
            "functional_requirements",
            "non_functional_requirements",
            "data_needs",
            "integration_needs",
            "compliance_needs",
        )
    )
    missing_count = len(analysis.get("missing_information", []) or [])
    strategic_fit = 66 + min(len(tags), 6) * 3 + min(len(requirements), 8)
    technical_fit = 62 + min(signal_count, 12) * 2
    domain_fit = 60 + min(len(tags), 8) * 3
    delivery_risk = 78 - min(missing_count, 12) * 2
    commercial = 64 + min(len(requirements), 10) - min(missing_count, 10)
    competitive = 62 + min(len(tags), 5) * 2
    if missing_count > 10:
        delivery_risk -= 4
        commercial -= 3
    overall = round((strategic_fit + technical_fit + domain_fit + delivery_risk + commercial + competitive) / 6)
    return {
        "strategic_fit": strategic_fit,
        "technical_fit": technical_fit,
        "domain_fit": domain_fit,
        "delivery_risk": max(delivery_risk, 35),
        "commercial_attractiveness": max(commercial, 35),
        "competitive_position": competitive,
        "overall_bid_score": overall,
    }


def _dedupe_risk_cards(risks: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for risk in risks:
        key = re.sub(r"[^a-z0-9]+", " ", risk.get("risk_title", "").lower()).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(risk)
    return output


def _risk_assessment(
    raw_text: str,
    tags: list[str],
    analysis: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    lower = raw_text.lower()
    signals = _analysis_signals(analysis)
    risks: list[dict[str, str]] = []

    for item in signals["integration"][:3]:
        label = _short_signal(item)
        risks.append(
            {
                "risk_title": label,
                "severity": "High",
                "probability": "Medium",
                "impact": f"Delivery and estimates can slip if the client has not confirmed interface ownership, environment access, credentials, payload examples, and test windows for '{label}'.",
                "mitigation": f"Before commitment, obtain the interface contract, owner matrix, sample payloads, error scenarios, and integration test calendar for '{label}'.",
                "owner": "Client",
            }
        )

    for item in signals["data"][:3]:
        label = _short_signal(item)
        risks.append(
            {
                "risk_title": label,
                "severity": "High",
                "probability": "Medium",
                "impact": f"Acceptance can be disputed if ownership, quality thresholds, migration rules, reporting definitions, or reconciliation approach for '{label}' are unclear.",
                "mitigation": f"Run data discovery for '{label}', assign source owners, and agree profiling, cleansing, reconciliation, and reporting acceptance rules.",
                "owner": "Joint",
            }
        )

    for item in [*signals["non_functional"][:2], *signals["compliance"][:2]]:
        label = _short_signal(item)
        risks.append(
            {
                "risk_title": label,
                "severity": "High",
                "probability": "Medium",
                "impact": f"Go-live can be blocked if evidence format, reviewer authority, remediation timing, or acceptance gate for '{label}' is not agreed early.",
                "mitigation": f"Confirm control evidence, reviewer, test method, remediation SLA, and final sign-off gate for '{label}' before design lock.",
                "owner": "Joint",
            }
        )

    for item in signals["functional"][:3]:
        label = _short_signal(item)
        risks.append(
            {
                "risk_title": label,
                "severity": "Medium",
                "probability": "Medium",
                "impact": f"The '{label}' scope can become disputed if first-release behavior, exclusions, UAT data, and sign-off tests remain broad.",
                "mitigation": f"Convert '{label}' into measurable acceptance criteria, explicit exclusions, owner sign-off, UAT evidence, and change-control triggers.",
                "owner": "Joint",
            }
        )

    for item in signals["timeline"][:2]:
        label = _short_signal(item)
        risks.append(
            {
                "risk_title": label,
                "severity": "Medium",
                "probability": "Medium",
                "impact": f"The '{label}' milestone can create commercial exposure if buyer-owned access, approvals, data, or environments arrive late.",
                "mitigation": f"Tie '{label}' dates to dependency readiness, client-owned prerequisites, schedule-relief language, and change-request mechanics.",
                "owner": "Joint",
            }
        )

    if any(term in lower for term in ("operate", "maintain", "o&m", "support", "sla", "incident")):
        scope_label = _short_signal((signals["scope"] or ["support and maintenance scope"])[0])
        risks.append(
            {
                "risk_title": scope_label,
                "severity": "Medium",
                "probability": "High",
                "impact": f"The '{scope_label}' obligation can turn implementation into open-ended support, tuning, reporting, or incident ownership.",
                "mitigation": f"Separate build, warranty, O&M, SLA coverage, escalation, monitoring, reporting cadence, and change-request obligations for '{scope_label}'.",
                "owner": "Joint",
            }
        )
    if any(term in lower for term in ("ai", "machine learning", "model", "classification", "prediction", "nlp")):
        ai_label = _short_signal((signals["functional"] or signals["data"] or ["AI/model quality requirement"])[0])
        risks.append(
            {
                "risk_title": ai_label,
                "severity": "High",
                "probability": "Medium",
                "impact": f"The '{ai_label}' capability can underperform if validation data, target metrics, explainability, drift monitoring, and retraining ownership are undefined.",
                "mitigation": f"Define validation data, thresholds, human review, error analysis, explainability, monitoring, and retraining ownership for '{ai_label}'.",
                "owner": "Joint",
            }
        )

    if not risks:
        focus = _rfp_focus(analysis, raw_text)
        risks.append(
            {
                "risk_title": focus,
                "severity": "Medium",
                "probability": "Medium",
                "impact": f"Delivery confidence for '{focus}' will remain limited until success metrics, acceptance criteria, owners, and dependencies are confirmed.",
                "mitigation": f"Use the first client call to convert '{focus}' into assumptions, exclusions, owner actions, acceptance tests, and dependency gates.",
                "owner": "Joint",
            }
        )
    return _dedupe_risk_cards(risks)[:8]


def _delivery_complexity(raw_text: str, tags: list[str]) -> dict[str, Any]:
    lower = raw_text.lower()
    drivers = ["Scope clarity", "Acceptance criteria", "Client dependency readiness"]
    phases = ["Discovery and assumptions validation", "Solution design", "MVP build", "Integration and UAT", "Production rollout", "Support transition"]
    team = ["Solution Architect", "Business Analyst/Product Owner", "Backend Engineer", "QA Engineer"]
    dependencies = ["Client access", "Source documentation", "Acceptance criteria", "Deployment environment"]
    if any(term in lower for term in ("api", "integration", "microservice", "existing system")):
        drivers.append("Integration/API readiness")
        team.append("Integration Engineer")
        dependencies.append("API documentation and sandbox access")
    if any(term in lower for term in ("data", "migration", "report", "analytics", "database")):
        drivers.append("Data quality and ownership")
        team.append("Data Engineer")
        dependencies.append("Representative data and source-system owners")
    if any(term in lower for term in ("security", "privacy", "audit", "encryption", "access control")):
        drivers.append("Security and compliance approval")
        team.append("Security Engineer")
        dependencies.append("Security-control matrix and sign-off path")
    if _has_domain_terms(lower, {"ai", "machine learning", "model", "classification", "prediction", "nlp"}):
        drivers.append("Model validation and monitoring")
        team.append("AI/ML Engineer")
        dependencies.append("Validation dataset and model acceptance metrics")
    if any(term in lower for term in ("cloud", "hosting", "infrastructure", "deploy", "availability")):
        drivers.append("Hosting, release, and observability constraints")
        team.append("DevOps/Cloud Engineer")
        dependencies.append("Approved infrastructure and release process")
    complexity_level = "High" if len(drivers) >= 7 else "Medium-High" if len(drivers) >= 5 else "Medium"
    return {
        "complexity_level": complexity_level,
        "why": "Complexity is driven by the number of unresolved delivery, integration, data, security, deployment, and operating-model dependencies in the RFP.",
        "main_complexity_drivers": _dedupe(drivers)[:8],
        "estimated_delivery_phases": phases,
        "estimated_timeline_range": "Validate after discovery; avoid fixed dates until dependencies, acceptance gates, and operating scope are confirmed.",
        "estimated_team_composition": _dedupe(team),
        "dependencies": _dedupe(dependencies)[:8],
    }


def _architecture_recommendation(
    raw_text: str,
    tags: list[str],
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    signals = _analysis_signals(analysis)
    focus = _rfp_focus(analysis, raw_text)
    named_scope = _dedupe(
        [
            _short_signal(item, words=8)
            for item in [
                *(signals["functional"][:2]),
                *(signals["integration"][:1]),
                *(signals["data"][:1]),
                *(signals["non_functional"][:1]),
            ]
        ]
    )
    if named_scope:
        scope_phrase = "; ".join(named_scope[:4])
        direction = (
            f"Deploy {focus} around the RFP's named scope: {scope_phrase}. "
            "Keep client-owned systems, data ownership, security gates, environments, and acceptance evidence explicit before pricing."
        )
    else:
        direction = (
            f"Deploy {focus} as a modular, evidence-gated solution. "
            "Confirm users, source systems, data ownership, controls, environments, and acceptance evidence before final commitment."
        )

    return {
        "direction": direction,
    }


def _architecture_detail(raw_text: str, analysis: dict[str, Any]) -> dict[str, Any]:
    signals = _analysis_signals(analysis)
    focus = _rfp_focus(analysis, raw_text)
    recommendation = _architecture_recommendation(raw_text, analysis.get("domain_tags", []), analysis)

    functional = [_short_signal(item, words=12) for item in signals["functional"][:4]]
    integrations = [_short_signal(item, words=12) for item in signals["integration"][:4]]
    data_needs = [_short_signal(item, words=12) for item in signals["data"][:4]]
    controls = [_short_signal(item, words=12) for item in [*signals["non_functional"], *signals["compliance"]][:4]]
    scope = [_short_signal(item, words=12) for item in signals["scope"][:3]]

    business_view = _dedupe(
        [
            f"Business outcome: use {focus} to solve the operating problem described in the RFP, with success measured by client-confirmed outcomes rather than tender compliance alone.",
            *[f"Call angle: confirm which business owner signs off the value of '{item}'." for item in functional[:2]],
            "Decision posture: treat architecture as a qualified direction until the client confirms users, data ownership, integrations, controls, and acceptance criteria.",
        ]
    )[:6]

    technical_view = _dedupe(
        [
            f"Experience and workflow capability for {focus}, scoped around the named user journeys and release-one behavior.",
            *[f"Domain service or module: {item}." for item in functional[:3]],
            *[f"Integration adapter boundary: {item}." for item in integrations[:3]],
            *[f"Data/reporting responsibility: {item}." for item in data_needs[:3]],
            *[f"Control plane requirement: {item}." for item in controls[:2]],
        ]
    )[:10]

    data_flow = _dedupe(
        [
            f"Intake: capture or receive inputs needed for {focus} from the buyer's confirmed channels.",
            *[f"Source data path: profile, validate, and reconcile '{item}' before acceptance." for item in data_needs[:3]],
            "Output path: expose dashboards, reports, APIs, notifications, or operational views only where the RFP names them or the client confirms them.",
        ]
    )[:7]

    integration_flow = _dedupe(
        [
            *[f"Connect '{item}' through a documented contract, sandbox, owner, test data, error handling, and release gate." for item in integrations[:4]],
            "Keep external systems behind adapters so proposal scope is not coupled to undocumented APIs or late client access.",
        ]
    )[:7]

    security_operations = _dedupe(
        [
            *[f"Design-time control: {item} needs a reviewer, evidence format, test method, remediation window, and sign-off path." for item in controls[:4]],
            *[f"Operating scope: separate build, warranty, monitoring, support, tuning, and change-request obligations for '{item}'." for item in scope[:2]],
            "Observability should cover workflow health, integration failures, data-quality exceptions, security events, and support handoff readiness.",
        ]
    )[:8]

    decision_points = _dedupe(
        [
            "Architecture style: modular service-led design with explicit adapters, governed data responsibilities, and observable release gates.",
            "MVP boundary: choose the smallest release that proves the buyer's priority workflow and measurable outcome.",
            "Integration strategy: do not commit effort until API contracts, payloads, environments, owners, and testing windows are available.",
            "Data strategy: assign source owners, quality thresholds, migration/reconciliation rules, and reporting definitions before build estimates.",
            "Control strategy: make security, audit, hosting, UAT, and production approvals part of the delivery plan from day one.",
        ]
    )[:7]

    call_prep_questions = _dedupe(
        [
            f"Which stakeholder owns success metrics and final sign-off for {focus}?",
            *[f"What release-one behavior, exclusions, UAT data, and acceptance evidence define '{item}'?" for item in functional[:2]],
            *[f"Who owns the interface contract, sandbox, payload examples, and test window for '{item}'?" for item in integrations[:2]],
            *[f"Who owns source quality, reconciliation, retention, and reporting definitions for '{item}'?" for item in data_needs[:2]],
            *[f"What evidence and approval path prove '{item}' before go-live?" for item in controls[:2]],
        ]
    )[:8]

    return {
        **recommendation,
        "business_view": business_view,
        "technical_view": technical_view,
        "data_flow": data_flow,
        "integration_flow": integration_flow,
        "security_operations": security_operations,
        "decision_points": decision_points,
        "call_prep_questions": call_prep_questions,
    }


def _dsl_quote(value: Any, *, max_chars: int = 180) -> str:
    text = _strip_reference_noise(str(value or "")).replace("\\", "\\\\").replace('"', '\\"')
    text = re.sub(r"\s+", " ", text).strip()[:max_chars]
    return f'"{text}"'


def _diagram_node(
    node_id: str,
    label: str,
    kind: str,
    group: str,
    description: str,
    *,
    technology: str = "",
) -> dict[str, str]:
    return {
        "id": node_id,
        "label": label,
        "kind": kind,
        "group": group,
        "description": description,
        "technology": technology,
    }


def _diagram_edge(source: str, target: str, label: str) -> dict[str, str]:
    return {"from": source, "to": target, "label": label}


def _diagram_lane(
    lane_id: str,
    title: str,
    description: str,
    groups: list[str],
    nodes: list[dict[str, str]],
) -> dict[str, Any]:
    node_ids = [node["id"] for node in nodes if node.get("group") in groups]
    return {
        "id": lane_id,
        "title": title,
        "description": description,
        "groups": groups,
        "node_ids": node_ids,
    }


def _architecture_layout(
    pattern: str,
    focus: str,
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]],
) -> dict[str, Any]:
    if pattern == "cloud_migration":
        lane_defs = [
            ("starting_point", "1. Current estate", "What exists today and who must approve the move.", ["Stakeholders", "Current State"]),
            ("migration", "2. Migration workstream", "The controlled runbook that moves the application without losing rollback control.", ["RFP-Specific Scope", "Migration Core"]),
            ("target", "3. Target runtime", "Where the migrated application, data, and operating environment land.", ["Target Runtime", "Data & Compliance", "Data Governance"]),
            ("validation", "4. Validation and release", "How testing, security evidence, release governance, and support prove go-live readiness.", ["Testing & Release", "Controls & Operations", "Confirmed Interfaces"]),
        ]
        headline = [
            "Reproduce the current ETRM baseline before changing production behavior.",
            "Move through a governed migration runbook with rollback and evidence gates.",
            "Treat AWS runtime, test evidence, data protection, and release governance as one go-live decision.",
        ]
    elif pattern == "search_nlp":
        lane_defs = [
            ("demand", "1. Search demand", "Who searches, what outcome matters, and where queries enter.", ["Stakeholders", "Search Channels", "RFP-Specific Scope"]),
            ("intelligence", "2. NLP and relevance core", "How query understanding, classification, ranking, and relevance improvement happen.", ["NLP & Search Core"]),
            ("platform", "3. Existing marketplace platform", "Where Solr, APIs, and confirmed interfaces remain protected behind integration boundaries.", ["Marketplace Integrations", "Confirmed Interfaces"]),
            ("evidence", "4. Evidence and operations", "How model quality, data readiness, monitoring, and acceptance controls are proven.", ["Data & Model Evidence", "Data Governance", "Controls & Operations"]),
        ]
        headline = [
            "Keep the existing Solr search estate stable while improving query understanding.",
            "Separate NLP, category classification, ranking, and marketplace API responsibilities.",
            "Make relevance metrics and monitoring part of acceptance, not a post-launch afterthought.",
        ]
    elif pattern == "mobile_app":
        lane_defs = [
            ("audience", "1. Users and channels", "Who uses the application and how value reaches them.", ["Stakeholders", "Mobile Channels", "RFP-Specific Scope"]),
            ("engagement", "2. Content and engagement core", "How content, events, quizzes, feedback, and notifications are managed.", ["Content & Engagement Core"]),
            ("data", "3. Authority data and reporting", "How client APIs, application data, dashboards, and reporting connect.", ["Authority Integrations", "Confirmed Interfaces", "Data & Reporting", "Data Governance"]),
            ("release", "4. Hosting and release controls", "How hosting, testing, security audit closure, and support protect launch readiness.", ["Controls & Operations"]),
        ]
        headline = [
            "Anchor the app around learning journeys, content operations, and measurable adoption.",
            "Treat authority APIs and dashboards as confirmed contracts with test data and owners.",
            "Gate hosting through UAT, security audit closure, and support readiness.",
        ]
    else:
        lane_defs = [
            ("experience", "1. Users and experience", "Who uses the system and which release-one journey proves value.", ["Stakeholders", "Channels", "RFP-Specific Scope"]),
            ("core", "2. Business capability", "The owned workflow, document, reporting, or domain services in the proposed solution.", ["Solution Core", "Insights & Reporting"]),
            ("interfaces", "3. Data and integrations", "How client systems, data ownership, and interface contracts are isolated from delivery risk.", ["Enterprise Integrations", "Data & Integrations", "Data Management", "Data Governance", "Confirmed Interfaces"]),
            ("controls", "4. Controls and operations", "How security, monitoring, support, acceptance, and production readiness are proven.", ["Controls & Operations"]),
        ]
        headline = [
            f"Deploy {focus} as a visible user journey backed by owned business services.",
            "Keep integrations and data responsibilities explicit so proposal scope stays controllable.",
            "Tie security, monitoring, and acceptance evidence directly to go-live readiness.",
        ]

    lanes = [_diagram_lane(lane_id, title, description, groups, nodes) for lane_id, title, description, groups in lane_defs]
    assigned = {node_id for lane in lanes for node_id in lane["node_ids"]}
    unassigned = [node["id"] for node in nodes if node["id"] not in assigned]
    if unassigned:
        lanes.append(
            {
                "id": "supporting",
                "title": "Supporting components",
                "description": "Additional RFP-specific components that should remain visible in scope discussions.",
                "groups": [],
                "node_ids": unassigned,
            }
        )
    lanes = [lane for lane in lanes if lane["node_ids"]]

    return {
        "executive_summary": headline,
        "lanes": lanes,
        "primary_flow": edges,
    }


def _arch_signal_pool(signals: dict[str, list[str]], analysis: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("functional", "integration", "data", "non_functional", "compliance", "scope", "timeline"):
        values.extend(signals.get(key, []))
    for key in ("domain_tags", "business_problem"):
        value = analysis.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value:
            values.append(str(value))
    return _dedupe([_short_signal(item, words=12, max_chars=130) for item in values])


def _arch_label(
    pool: list[str],
    keywords: set[str],
    fallback: str,
    *,
    words: int = 8,
    max_chars: int = 90,
) -> str:
    for item in pool:
        lower = item.lower()
        if any(_contains_term(lower, keyword) for keyword in keywords):
            return _short_signal(item, words=words, max_chars=max_chars)
    return fallback


def _architecture_pattern(raw_text: str, analysis: dict[str, Any], signals: dict[str, list[str]]) -> str:
    lower = raw_text.lower()
    tags = " ".join(str(item).lower() for item in analysis.get("domain_tags", []))
    joined = " ".join(_arch_signal_pool(signals, analysis)).lower()
    evidence = f"{lower} {tags} {joined}"
    scores = {
        "search_nlp": 0,
        "cloud_migration": 0,
        "mobile_app": 0,
        "workflow": 0,
        "analytics": 0,
        "document": 0,
        "integration_hub": 0,
    }
    if _has_search_nlp_signals(evidence) or any(term in evidence for term in ("solr", "query intent", "search relevance", "stemming", "lemmatization", "tokenization")):
        scores["search_nlp"] += 6
    if any(term in evidence for term in ("aws", "dedicated host", "migration", "test environment", "upgrade process", "release process", "cutover")):
        scores["cloud_migration"] += 5
    if any(term in evidence for term in ("mobile application", "mobile app", "push notification", "app store", "android", "ios", "multilingual content")):
        scores["mobile_app"] += 5
    if any(term in evidence for term in ("workflow", "approval", "case intake", "routing", "review", "case management")):
        scores["workflow"] += 4
    if any(term in evidence for term in ("dashboard", "analytics", "reporting", "metrics", "management report", "statistical data")):
        scores["analytics"] += 3
    if any(term in evidence for term in ("document upload", "document repository", "file share", "pdf", "records", "evidence retention")):
        scores["document"] += 3
    if len(signals.get("integration", [])) >= 2 or any(term in evidence for term in ("api", "web service", "microservice", "batch interface", "third party")):
        scores["integration_hub"] += 2
    return max(scores, key=lambda key: scores[key])


def _add_node(nodes: list[dict[str, str]], node: dict[str, str]) -> None:
    if not any(existing["id"] == node["id"] for existing in nodes):
        nodes.append(node)


def _add_edge(edges: list[dict[str, str]], edge: dict[str, str]) -> None:
    if not any(existing["from"] == edge["from"] and existing["to"] == edge["to"] and existing["label"] == edge["label"] for existing in edges):
        edges.append(edge)


def _structurizr_kind(kind: str) -> str:
    if kind == "person":
        return "person"
    if kind == "external_system":
        return "softwareSystem"
    return "container"


def _render_structurizr_dsl(focus: str, nodes: list[dict[str, str]], edges: list[dict[str, str]]) -> str:
    system_description = (
        f"Proposed solution boundary for {focus}; validate users, integrations, data ownership, controls, hosting, and acceptance criteria before proposal commitment."
    )
    dsl_lines = [
        f"workspace {_dsl_quote(f'ProposalPilot architecture - {focus}', max_chars=100)} {_dsl_quote(system_description, max_chars=220)} {{",
        "    model {",
    ]
    for node in nodes:
        if node["kind"] == "container":
            continue
        dsl_lines.append(
            f"        {node['id']} = {_structurizr_kind(node['kind'])} {_dsl_quote(node['label'])} {_dsl_quote(node['description'])}"
        )
    dsl_lines.append(
        f"        solution = softwareSystem {_dsl_quote(focus, max_chars=90)} {_dsl_quote(system_description, max_chars=220)} {{"
    )
    for node in nodes:
        if node["kind"] != "container":
            continue
        dsl_lines.append(
            f"            {node['id']} = container {_dsl_quote(node['label'])} {_dsl_quote(node['description'])} {_dsl_quote(node.get('technology') or node['group'])}"
        )
    dsl_lines.extend(["        }", ""])
    for edge in edges:
        dsl_lines.append(f"        {edge['from']} -> {edge['to']} {_dsl_quote(edge['label'], max_chars=120)}")
    dsl_lines.extend(
        [
            "    }",
            "    views {",
            '        systemContext solution "SystemContext" {',
            "            include *",
            "            autoLayout lr",
            f"            title {_dsl_quote(f'System context - {focus}', max_chars=120)}",
            "        }",
            '        container solution "Container" {',
            "            include *",
            "            autoLayout lr",
            f"            title {_dsl_quote(f'Container view - {focus}', max_chars=120)}",
            "        }",
            "        styles {",
            '            element "Person" { shape Person background "#0f766e" color "#ffffff" }',
            '            element "Software System" { background "#2563eb" color "#ffffff" }',
            '            element "Container" { background "#1f2937" color "#ffffff" }',
            '            element "External System" { background "#475569" color "#ffffff" }',
            "        }",
            "    }",
            "}",
        ]
    )
    return "\n".join(dsl_lines)


def _append_contextual_architecture_nodes(
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]],
    signals: dict[str, list[str]],
    *,
    pattern: str,
) -> None:
    route_targets = {
        "search_nlp": {
            "entry": "searchExperience",
            "core": "queryUnderstanding",
            "integration": "marketplaceApis",
            "data": "modelEvidence",
            "control": "searchMonitoring",
        },
        "mobile_app": {
            "entry": "mobileApp",
            "core": "contentAdmin",
            "integration": "authorityApis",
            "data": "appData",
            "control": "securityAudit",
        },
        "cloud_migration": {
            "entry": "migrationRunbook",
            "core": "migrationRunbook",
            "integration": "currentApplication",
            "data": "applicationData",
            "control": "securityReview",
        },
    }
    targets = route_targets.get(
        pattern,
        {
            "entry": "experience",
            "core": "workflowCore",
            "integration": "integrationAdapters",
            "data": "operationalData",
            "control": "controlPlane",
        },
    )
    existing_text = " ".join(f"{node.get('label', '')} {node.get('description', '')}" for node in nodes).lower()

    def has_target(node_id: str) -> bool:
        return any(node["id"] == node_id for node in nodes)

    functional = [_short_signal(item, words=10, max_chars=110) for item in signals.get("functional", [])]
    integrations = [_short_signal(item, words=10, max_chars=110) for item in signals.get("integration", [])]
    data_items = [_short_signal(item, words=10, max_chars=110) for item in signals.get("data", [])]
    controls = [_short_signal(item, words=10, max_chars=110) for item in [*signals.get("non_functional", []), *signals.get("compliance", [])]]
    scope = [_short_signal(item, words=10, max_chars=110) for item in signals.get("scope", [])]

    if functional:
        label = functional[0]
        if label.lower() not in existing_text:
            _add_node(
                nodes,
                _diagram_node(
                    "rfpScopeCapability",
                    label,
                    "container",
                    "RFP-Specific Scope",
                    "Represents the named release capability that should anchor the demo, MVP boundary, and acceptance conversation.",
                    technology="Scoped capability",
                ),
            )
            if has_target(targets["entry"]):
                _add_edge(edges, _diagram_edge("rfpScopeCapability", targets["entry"], "drives the user-facing deployment scope"))

    if integrations:
        label = integrations[0]
        if label.lower() not in existing_text:
            _add_node(
                nodes,
                _diagram_node(
                    "rfpInterfaceContract",
                    label,
                    "external_system",
                    "Confirmed Interfaces",
                    "Requires owner, API or batch contract, sandbox, sample payloads, error handling, and release window confirmation.",
                ),
            )
            if has_target(targets["core"]):
                _add_edge(edges, _diagram_edge(targets["core"], "rfpInterfaceContract", "depends on confirmed interface readiness"))

    if data_items:
        label = data_items[0]
        if label.lower() not in existing_text:
            _add_node(
                nodes,
                _diagram_node(
                    "rfpDataReadiness",
                    label,
                    "container",
                    "Data Governance",
                    "Captures source ownership, quality threshold, migration or reporting definition, reconciliation rule, and retention evidence.",
                    technology="Data readiness gate",
                ),
            )
            if has_target(targets["data"]):
                _add_edge(edges, _diagram_edge("rfpDataReadiness", targets["data"], "sets data acceptance rules"))

    acceptance_signal = (controls or scope)[:1]
    if acceptance_signal:
        label = acceptance_signal[0]
        if label.lower() not in existing_text:
            _add_node(
                nodes,
                _diagram_node(
                    "rfpAcceptanceGate",
                    label,
                    "container",
                    "Controls & Operations",
                    "Turns the RFP's named control or operating obligation into reviewer, evidence, remediation, and go-live sign-off steps.",
                    technology="Acceptance gate",
                ),
            )
            if has_target(targets["control"]):
                _add_edge(edges, _diagram_edge("rfpAcceptanceGate", targets["control"], "defines evidence required for approval"))


def _build_structurizr_architecture(raw_text: str, analysis: dict[str, Any]) -> dict[str, Any]:
    signals = _analysis_signals(analysis)
    focus = _rfp_focus(analysis, raw_text)
    pool = _arch_signal_pool(signals, analysis)
    pattern = _architecture_pattern(raw_text, analysis, signals)
    nodes: list[dict[str, str]] = []
    edges: list[dict[str, str]] = []

    stakeholder_label = "Executive sponsor / business owner"
    user_label = "Client users and operators"
    if pattern == "search_nlp":
        user_label = "Marketplace search users and catalog teams"
    elif pattern == "mobile_app":
        user_label = "Mobile learners, teachers, and content teams"
    elif pattern == "cloud_migration":
        user_label = "Application users, testers, and release owners"
    elif pattern == "analytics":
        user_label = "Business managers and analysts"
    elif pattern == "document":
        user_label = "Document submitters, reviewers, and approvers"
    elif pattern == "workflow":
        user_label = "Case workers, approvers, and reporting users"

    _add_node(nodes, _diagram_node("executiveSponsor", stakeholder_label, "person", "Stakeholders", "Owns outcomes, funding posture, acceptance authority, and unresolved trade-offs."))
    _add_node(nodes, _diagram_node("clientUsers", user_label, "person", "Stakeholders", "Use the delivered capability and validate release-one operating fit."))

    if pattern == "search_nlp":
        search_ui = _arch_label(pool, {"search", "query", "marketplace", "web service"}, "Marketplace search experience")
        optimizer = _arch_label(pool, {"search string", "query intent", "stop-word", "stemming", "lemmatization", "tokenization", "synonym", "noise"}, "Query understanding and normalization service")
        ranking = _arch_label(pool, {"relevance", "ranking", "information retrieval", "search relevance"}, "Search relevance and ranking service")
        classifier = _arch_label(pool, {"category", "classification", "catalog", "seller category", "taxonomy"}, "Catalog category classification service")
        solr = _arch_label(pool, {"solr", "search architecture"}, "Existing Apache Solr search platform")
        model_data = _arch_label(pool, {"training data", "validation", "metrics", "relevance measurement"}, "Training, validation, and relevance metrics store")
        api = _arch_label(pool, {"microservice", "api", "web service"}, "Marketplace microservice API boundary")
        _add_node(nodes, _diagram_node("searchExperience", search_ui, "container", "Search Channels", "Captures user search terms and displays relevance-ranked product or service results.", technology="Search UI / API"))
        _add_node(nodes, _diagram_node("queryUnderstanding", optimizer, "container", "NLP & Search Core", "Normalizes queries through intent handling, tokenization, stemming, lemmatization, synonyms, and noise removal.", technology="NLP pipeline"))
        _add_node(nodes, _diagram_node("relevanceService", ranking, "container", "NLP & Search Core", "Applies ranking, relevance rules, measurement hooks, and search-quality feedback loops.", technology="Search relevance service"))
        _add_node(nodes, _diagram_node("categoryClassifier", classifier, "container", "NLP & Search Core", "Classifies catalog/category intent and supports seller or product category suggestions where required.", technology="ML classification"))
        _add_node(nodes, _diagram_node("marketplaceApis", api, "external_system", "Marketplace Integrations", "Existing marketplace services that consume or expose search capabilities."))
        _add_node(nodes, _diagram_node("solrSearch", solr, "external_system", "Marketplace Integrations", "Existing Solr search architecture that must be integrated without disrupting current search operations."))
        _add_node(nodes, _diagram_node("modelEvidence", model_data, "container", "Data & Model Evidence", "Stores training data references, validation datasets, relevance metrics, error reviews, and acceptance evidence.", technology="Evaluation data store"))
        _add_node(nodes, _diagram_node("searchMonitoring", "Search quality monitoring and drift review", "container", "Controls & Operations", "Tracks relevance, query failures, model quality, regression risk, and retraining or tuning triggers.", technology="Model/search observability"))
        _add_edge(edges, _diagram_edge("executiveSponsor", "searchExperience", "sets search-quality outcomes"))
        _add_edge(edges, _diagram_edge("clientUsers", "searchExperience", "submit marketplace queries"))
        _add_edge(edges, _diagram_edge("searchExperience", "queryUnderstanding", "sends raw search terms"))
        _add_edge(edges, _diagram_edge("queryUnderstanding", "categoryClassifier", "derives catalog/category intent"))
        _add_edge(edges, _diagram_edge("queryUnderstanding", "relevanceService", "passes normalized query features"))
        _add_edge(edges, _diagram_edge("relevanceService", "solrSearch", "executes Solr-backed retrieval"))
        _add_edge(edges, _diagram_edge("categoryClassifier", "marketplaceApis", "returns category suggestions through APIs"))
        _add_edge(edges, _diagram_edge("modelEvidence", "categoryClassifier", "provides validation and training evidence"))
        _add_edge(edges, _diagram_edge("relevanceService", "searchMonitoring", "emits relevance and failure metrics"))
    elif pattern == "cloud_migration":
        current_app = _arch_label(pool, {"application", "software", "system", "platform"}, "Existing application baseline")
        aws_host = _arch_label(pool, {"aws", "dedicated host", "host", "cloud"}, "Target cloud runtime for migrated application")
        test_env = _arch_label(pool, {"test environment", "validation", "testing", "uat"}, "Separate test and validation environment")
        release = _arch_label(pool, {"upgrade", "release", "version", "process"}, "Formal upgrade and release process")
        data = _arch_label(pool, {"data", "confidential", "records", "privacy"}, "Application data and confidentiality controls")
        _add_node(nodes, _diagram_node("currentApplication", current_app, "external_system", "Current State", "Current application and environment that must be reproduced, migrated, tested, or updated."))
        _add_node(nodes, _diagram_node("migrationRunbook", "Migration and cutover runbook", "container", "Migration Core", "Coordinates environment reproduction, migration steps, rollback criteria, and acceptance evidence.", technology="Migration workstream"))
        _add_node(nodes, _diagram_node("awsRuntime", aws_host, "container", "Target Runtime", "Hosts the migrated application in the buyer-approved AWS setup with confirmed network and access constraints.", technology="AWS host"))
        _add_node(nodes, _diagram_node("testEnvironment", test_env, "container", "Testing & Release", "Runs validation, regression testing, UAT evidence capture, and defect triage before production sign-off.", technology="Test environment"))
        _add_node(nodes, _diagram_node("releasePipeline", release, "container", "Testing & Release", "Defines build, upgrade, promotion, rollback, and version-control governance for future releases.", technology="Release governance"))
        _add_node(nodes, _diagram_node("applicationData", data, "container", "Data & Compliance", "Protects application data, migration evidence, access records, and confidentiality obligations.", technology="Controlled data store"))
        _add_node(nodes, _diagram_node("securityReview", "Confidentiality and access-control review", "container", "Controls & Operations", "Confirms security evidence, reviewer authority, remediation windows, and production approval gates.", technology="Security compliance"))
        _add_node(nodes, _diagram_node("opsMonitoring", "AWS operations and support handoff", "container", "Controls & Operations", "Tracks migration health, environment readiness, incident handoff, and support responsibilities.", technology="Cloud operations"))
        _add_edge(edges, _diagram_edge("executiveSponsor", "migrationRunbook", "approves migration risk posture"))
        _add_edge(edges, _diagram_edge("clientUsers", "testEnvironment", "perform UAT and regression validation"))
        _add_edge(edges, _diagram_edge("currentApplication", "migrationRunbook", "provides source application baseline"))
        _add_edge(edges, _diagram_edge("migrationRunbook", "awsRuntime", "rehosts application to target runtime"))
        _add_edge(edges, _diagram_edge("migrationRunbook", "applicationData", "moves and protects system data"))
        _add_edge(edges, _diagram_edge("awsRuntime", "testEnvironment", "is validated before go-live"))
        _add_edge(edges, _diagram_edge("testEnvironment", "releasePipeline", "feeds upgrade acceptance evidence"))
        _add_edge(edges, _diagram_edge("securityReview", "awsRuntime", "gates production readiness"))
        _add_edge(edges, _diagram_edge("awsRuntime", "opsMonitoring", "emits environment and support signals"))
    elif pattern == "mobile_app":
        mobile = _arch_label(pool, {"mobile", "application", "app"}, "Mobile application")
        cms = _arch_label(pool, {"content", "back-office", "administration", "backend", "learning", "quiz", "event"}, "Back-office content management module")
        api = _arch_label(pool, {"mobile api", "api", "statistical data", "integration"}, "Authority mobile/statistical data APIs")
        reporting = _arch_label(pool, {"dashboard", "report", "analytics", "statistical"}, "Initiative dashboards and reporting")
        hosting = _arch_label(pool, {"hosting", "test", "production", "environment"}, "Application hosting and release environments")
        security = _arch_label(pool, {"security audit", "audit", "compliance", "testing"}, "Security audit and acceptance closure")
        _add_node(nodes, _diagram_node("mobileApp", mobile, "container", "Mobile Channels", "Delivers learning modules, events, quizzes, downloads, feedback, multilingual content, and notifications where required.", technology="Mobile app"))
        _add_node(nodes, _diagram_node("contentAdmin", cms, "container", "Content & Engagement Core", "Manages learning content, events, quiz material, downloads, publishing workflow, and back-office administration.", technology="CMS / admin module"))
        _add_node(nodes, _diagram_node("notificationService", "Push notification and feedback service", "container", "Content & Engagement Core", "Supports campaign updates, user feedback capture, notification routing, and engagement tracking.", technology="Notification service"))
        _add_node(nodes, _diagram_node("authorityApis", api, "external_system", "Authority Integrations", "Client-provided APIs or datasets that must be confirmed for credentials, payloads, cadence, and test access."))
        _add_node(nodes, _diagram_node("reporting", reporting, "container", "Data & Reporting", "Publishes initiative-wise dashboards, usage views, and management reporting from app and API data.", technology="Analytics/reporting"))
        _add_node(nodes, _diagram_node("appData", "Mobile content, user feedback, and analytics data", "container", "Data & Reporting", "Stores content metadata, feedback, download records, dashboard data, and acceptance evidence.", technology="Application database"))
        _add_node(nodes, _diagram_node("hosting", hosting, "container", "Controls & Operations", "Separates test, production, hosting, release, backup, and support responsibilities.", technology="Hosted environments"))
        _add_node(nodes, _diagram_node("securityAudit", security, "container", "Controls & Operations", "Tracks security-audit findings, remediation evidence, UAT closure, and go-live approval.", technology="Security/UAT gate"))
        _add_edge(edges, _diagram_edge("executiveSponsor", "reporting", "reviews adoption and initiative outcomes"))
        _add_edge(edges, _diagram_edge("clientUsers", "mobileApp", "consume content and submit feedback"))
        _add_edge(edges, _diagram_edge("contentAdmin", "mobileApp", "publishes approved learning content"))
        _add_edge(edges, _diagram_edge("mobileApp", "notificationService", "registers feedback and engagement events"))
        _add_edge(edges, _diagram_edge("mobileApp", "authorityApis", "requests client-provided statistical data"))
        _add_edge(edges, _diagram_edge("authorityApis", "reporting", "feeds initiative dashboards"))
        _add_edge(edges, _diagram_edge("mobileApp", "appData", "stores usage, content, and feedback records"))
        _add_edge(edges, _diagram_edge("securityAudit", "hosting", "gates deployment after audit closure"))
        _add_edge(edges, _diagram_edge("hosting", "mobileApp", "serves production mobile capability"))
    else:
        is_document = pattern == "document"
        is_analytics = pattern == "analytics"
        experience = _arch_label(pool, {"portal", "dashboard", "workflow", "screen", "application", "intake"}, f"{focus} user experience")
        workflow = _arch_label(pool, {"workflow", "approval", "routing", "case", "review", "process"}, f"{focus} workflow orchestration")
        document = _arch_label(pool, {"document", "upload", "repository", "file", "records"}, "Document and evidence management")
        analytics = _arch_label(pool, {"report", "dashboard", "analytics", "metrics"}, "Operational reporting and analytics")
        data = _arch_label(pool, {"data", "records", "migration", "database", "reconciliation"}, f"{focus} operational data store")
        integration = _arch_label(pool, {"identity", "finance", "api", "repository", "notification", "integration", "batch"}, "Confirmed enterprise integration adapters")
        control = _arch_label(pool, {"security", "audit", "encryption", "access control", "compliance"}, "Access, audit, and compliance controls")
        _add_node(nodes, _diagram_node("experience", experience, "container", "Channels", "Presents the RFP-supported intake, workflow, dashboard, review, or operational screens.", technology="Web/application UI"))
        _add_node(nodes, _diagram_node("workflowCore", workflow, "container", "Solution Core", "Coordinates business rules, task routing, state changes, notifications, exceptions, and acceptance evidence.", technology="Workflow services"))
        if is_document or "document" in document.lower():
            _add_node(nodes, _diagram_node("documentService", document, "container", "Solution Core", "Manages uploads, repository links, evidence retention, document metadata, and review handoff.", technology="Document service"))
        if is_analytics or "report" in analytics.lower() or "dashboard" in analytics.lower():
            _add_node(nodes, _diagram_node("reporting", analytics, "container", "Insights & Reporting", "Turns operational records into dashboards, management reports, reconciliation views, and acceptance evidence.", technology="Reporting/analytics"))
        _add_node(nodes, _diagram_node("integrationAdapters", integration, "container", "Enterprise Integrations", "Encapsulates confirmed APIs, identity, finance, repository, notification, or batch interfaces behind owned contracts.", technology="Integration adapters"))
        _add_node(nodes, _diagram_node("enterpriseSystems", "Client enterprise systems to confirm", "external_system", "Enterprise Integrations", "Buyer-owned systems whose owners, APIs, test data, and release windows must be confirmed."))
        _add_node(nodes, _diagram_node("operationalData", data, "container", "Data Management", "Stores operational records, migrated data, data-quality evidence, reporting definitions, and audit history.", technology="Governed data store"))
        _add_node(nodes, _diagram_node("controlPlane", control, "container", "Controls & Operations", "Enforces access, audit, encryption, compliance evidence, and production sign-off gates.", technology="Security controls"))
        _add_node(nodes, _diagram_node("observability", "Workflow, integration, and support observability", "container", "Controls & Operations", "Monitors workflow health, integration failures, data-quality exceptions, incidents, and support handoff readiness.", technology="Operational monitoring"))
        _add_edge(edges, _diagram_edge("executiveSponsor", "experience", "sets outcomes and acceptance criteria"))
        _add_edge(edges, _diagram_edge("clientUsers", "experience", "complete operating workflows"))
        _add_edge(edges, _diagram_edge("experience", "workflowCore", "submits tasks, decisions, and evidence"))
        if any(node["id"] == "documentService" for node in nodes):
            _add_edge(edges, _diagram_edge("workflowCore", "documentService", "attaches documents and review evidence"))
            _add_edge(edges, _diagram_edge("documentService", "operationalData", "stores metadata and retention records"))
        _add_edge(edges, _diagram_edge("workflowCore", "integrationAdapters", "uses confirmed interface contracts"))
        _add_edge(edges, _diagram_edge("integrationAdapters", "enterpriseSystems", "exchanges data with client systems"))
        _add_edge(edges, _diagram_edge("workflowCore", "operationalData", "records work state and acceptance evidence"))
        if any(node["id"] == "reporting" for node in nodes):
            _add_edge(edges, _diagram_edge("operationalData", "reporting", "feeds dashboards and management reports"))
            _add_edge(edges, _diagram_edge("reporting", "executiveSponsor", "shows progress and business evidence"))
        _add_edge(edges, _diagram_edge("controlPlane", "workflowCore", "gates access, audit, and sign-off"))
        _add_edge(edges, _diagram_edge("workflowCore", "observability", "emits health, exception, and support signals"))

    _append_contextual_architecture_nodes(nodes, edges, signals, pattern=pattern)
    layout = _architecture_layout(pattern, focus, nodes, edges)

    return {
        "title": f"{pattern.replace('_', ' ').title()} deployment view for {focus}",
        "notation": "Deployment flow / C4 container model",
        "view": "Deployment readiness",
        **layout,
        "nodes": nodes,
        "edges": edges,
        "structurizr_dsl": _render_structurizr_dsl(focus, nodes, edges),
    }


def _analysis_query(analysis: dict[str, Any]) -> str:
    parts = [
        str(analysis.get("business_problem") or ""),
        " ".join(str(item) for item in analysis.get("functional_requirements", [])[:5]),
        " ".join(str(item) for item in analysis.get("integration_needs", [])[:4]),
        " ".join(str(item) for item in analysis.get("data_needs", [])[:4]),
        " ".join(str(item) for item in analysis.get("domain_tags", [])[:8]),
    ]
    return " ".join(part for part in parts if part).strip()[:1800]


def _evidence_terms(analysis: dict[str, Any]) -> set[str]:
    source = " ".join(
        [
            str(analysis.get("business_problem") or ""),
            " ".join(str(item) for item in analysis.get("functional_requirements", [])[:6]),
            " ".join(str(item) for item in analysis.get("integration_needs", [])[:5]),
            " ".join(str(item) for item in analysis.get("data_needs", [])[:5]),
            " ".join(str(item) for item in analysis.get("domain_tags", [])[:8]),
        ]
    )
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+-]{3,}", source.lower())
        if token not in _EVIDENCE_STOPWORDS and not token.isdigit()
    }


def _knowledge_evidence_from_matches(matches: list[dict[str, Any]], analysis: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    query_terms = _evidence_terms(analysis or {})
    evidence: list[dict[str, Any]] = []
    for match in matches[:6]:
        title = str(match.get("title") or "Internal knowledge item").strip()
        text = _strip_reference_noise(str(match.get("text") or ""))
        if not text:
            continue
        score = round(float(match.get("score") or 0), 3)
        haystack = f"{title} {text} {' '.join(str(item) for item in match.get('tags') or [])} {' '.join(str(item) for item in match.get('tech_stack') or [])}".lower()
        overlap = {term for term in query_terms if term in haystack}
        if score < 0.45:
            continue
        if query_terms and score < 0.68 and len(overlap) < 3:
            continue
        if query_terms and not overlap:
            continue
        evidence.append(
            {
                "title": title,
                "domain": match.get("domain") or "unknown",
                "item_type": match.get("item_type") or "project",
                "score": score,
                "why_relevant": text[:420],
                "tech_stack": match.get("tech_stack") or [],
                "tags": match.get("tags") or [],
            }
        )
    return evidence


def _sentiment_analysis(analysis: dict[str, Any], raw_text: str) -> dict[str, Any]:
    tags = analysis.get("domain_tags", [])
    requirements = analysis.get("functional_requirements", [])
    integrations = analysis.get("integration_needs", [])
    data_needs = analysis.get("data_needs", [])
    missing = analysis.get("missing_information", [])
    risks = analysis.get("timeline_risks", [])
    positive_count = len(requirements) + len(tags)
    concern_count = len(integrations) + len(data_needs) + len(missing) + len(risks)
    if concern_count >= positive_count + 6:
        posture = "Cautious"
    elif positive_count >= concern_count:
        posture = "Constructive"
    else:
        posture = "Selective"
    focus = _rfp_focus(analysis, raw_text)
    points = [
        {
            "title": focus,
            "insight": str(analysis.get("business_problem") or f"The document describes {focus}, but the buyer outcome needs clarification."),
            "evidence": _joined(requirements, str(analysis.get("business_problem") or ""), limit=1),
            "implication": "Open the client call by validating the business outcome and executive success metric before discussing effort or commercials.",
        },
    ]
    for item in _specific_items(requirements, limit=3):
        label = _short_signal(item)
        points.append(
            {
                "title": label,
                "insight": f"The RFP explicitly points to '{label}', so the discussion should clarify first-release behavior, acceptance evidence, and owner sign-off.",
                "evidence": item[:260],
                "implication": "Separate mandatory scope, optional scope, client-owned dependencies, and proposal assumptions for this requirement.",
            }
        )
    if integrations:
        label = _short_signal(integrations[0])
        points.append(
            {
                "title": label,
                "insight": f"The '{label}' integration appears material to delivery success.",
                "evidence": _joined(integrations, "Integration needs are referenced in the RFP.", limit=2),
                "implication": "Do not commit fixed dates until interfaces, owners, environments, and test windows are confirmed.",
            }
        )
    if data_needs:
        label = _short_signal(data_needs[0])
        points.append(
            {
                "title": label,
                "insight": f"The '{label}' data requirement can affect delivery confidence and acceptance.",
                "evidence": _joined(data_needs, "Data needs are referenced in the RFP.", limit=2),
                "implication": "Ask for representative data, source-system ownership, quality constraints, and reconciliation responsibilities.",
            }
        )
    if any(term in raw_text.lower() for term in ("security", "confidential", "privacy", "audit", "encryption", "access control")):
        control = _short_signal((_specific_items(analysis.get("non_functional_requirements"), limit=1) or _specific_items(analysis.get("compliance_needs"), limit=1) or ["security/audit controls"])[0])
        points.append(
            {
                "title": control,
                "insight": f"The '{control}' expectation should be treated as an architecture and go-live constraint.",
                "evidence": _evidence_for(raw_text, {"security", "confidential", "privacy", "audit", "encryption", "access control"}, "Security/governance terms are present in the RFP."),
                "implication": "Confirm mandatory controls, sign-off authority, audit evidence, and production readiness gates early.",
            }
        )
    return {
        "overall_sentiment": posture,
        "summary": f"{focus} is a {posture.lower()} opportunity. The RFP gives enough signal to plan discovery, but commitments should depend on the specific requirements, integrations, data, controls, and acceptance gates extracted from this document.",
        "confidence": "medium" if raw_text and len(raw_text) > 1500 else "low",
        "points": points[:6],
        "recommended_posture": f"Proceed with executive discovery for {focus}; avoid price, timeline, and final architecture commitments until the named assumptions are validated.",
    }


def _must_ask_question_cards(
    raw_text: str,
    tags: list[str],
    analysis: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    questions = _missing_information_questions(raw_text, tags, analysis)
    cards: list[dict[str, str]] = []
    for question in questions[:10]:
        lower = question.lower()
        category = "Discovery"
        why = "This changes delivery confidence, pricing, timeline, architecture, or acceptance risk for this specific RFP."
        assumption = "The client can confirm this from source-system owners, business owners, delivery owners, or sign-off authorities before proposal commitment."
        if any(term in lower for term in ("test", "testing", "uat", "regression", "defect")):
            category = "Testing and acceptance"
            why = "Testing ownership and acceptance evidence determine when the migrated application can be considered complete."
            assumption = "The buyer has named UAT owners, representative test data, defect triage rules, and sign-off criteria."
        elif any(term in lower for term in ("upgrade", "release", "version", "branching", "promotion")):
            category = "Release governance"
            why = "The upgrade process affects ongoing delivery velocity, operational risk, and post-migration support obligations."
            assumption = "The buyer can confirm release approvals, build process, rollback expectations, and production promotion gates."
        elif any(term in lower for term in ("aws", "host", "infrastructure", "environment", "cutover", "rollback")):
            category = "Cloud migration"
            why = "Hosting, access, dependency, cutover, and rollback details decide whether the migration can be estimated safely."
            assumption = "The buyer can provide current environment details, cloud/network constraints, access path, migration window, and rollback authority."
        elif any(term in lower for term in ("security", "confidential", "cpra", "compliance", "go-live evidence", "sign-off gate")):
            category = "Security and compliance"
            why = "Security and statutory obligations can block go-live or change the delivery approach if evidence expectations are unclear."
            assumption = "The buyer can identify mandatory controls, legal/compliance reviewers, evidence format, and remediation windows."
        elif any(term in lower for term in ("out of scope", "support", "o&m", "buyer-owned")):
            category = "Scope and operations"
            why = "Scope boundaries prevent implementation work from becoming open-ended support, consulting, or unmanaged change requests."
            assumption = "The buyer can separate initial migration/build work from support, maintenance, enhancements, and buyer-owned responsibilities."
        cards.append(
            {
                "category": category,
                "question": question,
                "why_it_matters": why,
                "assumption_to_validate": assumption,
            }
        )
    return cards


def _talking_points(
    report: dict[str, Any],
    analysis: dict[str, Any] | None = None,
    raw_text: str = "",
) -> list[dict[str, str]]:
    signals = _analysis_signals(analysis)
    focus = _rfp_focus(analysis, raw_text)
    source_points: list[str] = [
        f"{focus}: agree the business outcome, success metric, and buyer decision owner before effort is discussed.",
    ]
    for item in signals["functional"][:2]:
        label = _short_signal(item)
        source_points.append(f"{label}: pin down release-one behavior, exclusions, UAT evidence, and sign-off owner.")
    for item in signals["integration"][:2]:
        label = _short_signal(item)
        source_points.append(f"{label}: ask for the interface contract, environment access, owner, payloads, and test window.")
    for item in signals["data"][:2]:
        label = _short_signal(item)
        source_points.append(f"{label}: confirm source owner, data quality, migration responsibility, and reconciliation rule.")
    for item in [*signals["non_functional"][:1], *signals["compliance"][:1]]:
        label = _short_signal(item)
        source_points.append(f"{label}: identify the reviewer, evidence format, remediation SLA, and production sign-off path.")
    prep = report.get("prospect_call_prep", {}) if isinstance(report.get("prospect_call_prep"), dict) else {}
    if len(source_points) < 5:
        source_points.extend(prep.get("strongest_talking_points") or report.get("win_strategy") or [])
    points: list[dict[str, str]] = []
    for point in _dedupe([str(item) for item in source_points])[:7]:
        lower = point.lower()
        client_angle = f"Use this to keep the call centered on the buyer's actual '{focus}' decision, not generic tender compliance."
        proof_needed = "Use the RFP phrase behind this point, a named client clarification, or a verified internal evidence item before proposal submission."
        if any(term in lower for term in ("business outcome", "success metric", "decision owner")):
            client_angle = "Start at executive value: why the buyer needs this migration or modernization now, what business risk it reduces, and who owns success."
            proof_needed = "Client-confirmed success metric, decision owner, target operating outcome, and current pain caused by the existing application setup."
        elif any(term in lower for term in ("uat", "sign-off", "release-one", "testing", "validation")):
            client_angle = "Move the conversation from task completion to acceptance: what evidence proves the migrated environment is ready."
            proof_needed = "Acceptance criteria, UAT owner, regression scope, test data readiness, defect severity rules, and final sign-off authority."
        elif any(term in lower for term in ("security", "confidential", "reviewer", "evidence format")):
            client_angle = "Position security, privacy, and confidentiality controls as go-live design constraints, not late-stage paperwork."
            proof_needed = "Mandatory controls, reviewer names, audit/security evidence, remediation windows, and confidentiality handling expectations."
        elif any(term in lower for term in ("client-owned", "dependencies", "price", "timeline")):
            client_angle = "Make buyer-owned dependencies visible before discussing price, timeline, staffing, or fixed-scope commitments."
            proof_needed = "Dependency owner list, access dates, environment readiness, decision SLAs, and change-control triggers."
        points.append(
            {
                "point": point,
                "client_angle": client_angle,
                "proof_needed": proof_needed,
            }
        )
    return points


def _narrative_from_evidence(analysis: dict[str, Any], evidence: list[dict[str, Any]], raw_text: str = "") -> dict[str, Any]:
    focus = _rfp_focus(analysis, raw_text)
    primary = evidence[0] if evidence else {}
    title = str(primary.get("title") or "").strip()
    if not title:
        return {
            "title": f"Evidence gap for {focus}",
            "story": (
                f"For {focus}, do not claim a past-project proof story until the knowledge base returns a defensible match. "
                "Lead the client conversation with the RFP's named capabilities, the assumptions that need owner confirmation, "
                "and the architecture choices that remain conditional on integrations, data, controls, and acceptance gates."
            ),
            "how_it_helps": [
                f"Keeps the {focus} conversation credible for C-suite stakeholders.",
                "Prevents unsupported internal-project claims from entering the pursuit narrative.",
                "Creates a clean follow-up action: attach the closest verified case study only after the knowledge base provides one.",
            ],
            "evidence_project_title": "",
            "confidence": "low",
        }
    domain = primary.get("domain") or "similar"
    return {
        "title": f"{title} relevance to {focus}",
        "story": (
            f"Position {title} only where it directly supports {focus}. "
            f"The useful comparison is the {domain} delivery pattern described in the knowledge base: convert unclear requirements into governed workstreams, "
            "make integrations and data ownership explicit, and use reusable architecture or operating practices only where the current RFP has matching evidence. "
            f"For {focus}, this helps the call stay proof-led without overstating similarity."
        ),
        "how_it_helps": [
            str(primary.get("why_relevant") or "Relevant implementation evidence from the internal knowledge base.")[:260],
            f"Turns the {focus} call into a proof-backed discussion around delivery risk, not only features.",
            "Keeps the bridge from past execution to this RFP tied to verified overlap rather than a generic success story.",
        ],
        "evidence_project_title": title,
        "confidence": "medium" if float(primary.get("score") or 0) < 0.7 else "high",
    }


_RFP_INTELLIGENCE_SYSTEM_PROMPT = """
You are a principal pre-sales architect and executive pursuit strategist.

Create the RFP Analysis page content for C-suite users. Use only the extracted
facts, retrieved knowledge evidence, and quoted RFP excerpt. Do not invent
client facts, integrations, budgets, dates, products, certifications, or past
projects.

Critical rules:
- Every card heading must be specific to this RFP. Do not use generic headings
  like "Integration readiness", "Data readiness", "Scope clarity", "Control
  sign-off", "Opportunity signal", "Leadership concern", or "Client dependency".
- If a section item cannot point to a specific RFP phrase, do not include it.
- Questions must ask about named assumptions from this RFP.
- Risks must be concrete, named after the actual requirement/dependency, and
  explain why that exact item threatens delivery, pricing, acceptance, or go-live.
- Talking points must sound like directors preparing for a client call, not
  generic project-management advice.
- Narrative must use retrieved knowledge only when the overlap is defensible;
  otherwise state that no strong internal evidence match is available.
- Architecture must help a client-call team. Include executive-readable
  business implications, technically specific design detail, and a deployment
  diagram whose nodes are named after actual product modules, integrations,
  data stores, control gates, environments, or operations responsibilities in
  the RFP. Avoid generic layer names.
- Architecture business_view, technical_view, data_flow, integration_flow,
  security_operations, decision_points, and call_prep_questions must not repeat
  the Must-Ask Questions, Top Risks, Talking Points, or Narrative wording.
- Return valid JSON only.
"""


async def _generate_llm_rfp_intelligence(
    raw_text: str,
    analysis: dict[str, Any],
    knowledge_evidence: list[dict[str, Any]],
    *,
    regenerate: bool = False,
) -> dict[str, Any] | None:
    llm_service = get_llm_service()
    clipped_text = raw_text[:6_000]
    evidence_text = "\n".join(
        f"- {item.get('title')} ({item.get('domain')}, score={item.get('score')}): {item.get('why_relevant')}"
        for item in knowledge_evidence[:5]
    ) or "No sufficiently relevant internal knowledge evidence was retrieved."
    user_content = f"""
Build the complete RFP Analysis intelligence object.

Extracted RFP facts:
business_problem: {analysis.get("business_problem")}
functional_requirements: {analysis.get("functional_requirements", [])[:8]}
non_functional_requirements: {analysis.get("non_functional_requirements", [])[:6]}
data_needs: {analysis.get("data_needs", [])[:6]}
integration_needs: {analysis.get("integration_needs", [])[:6]}
compliance_needs: {analysis.get("compliance_needs", [])[:6]}
timeline_risks: {analysis.get("timeline_risks", [])[:6]}
missing_information: {analysis.get("missing_information", [])[:8]}
scope_boundaries: {analysis.get("scope_boundaries", [])[:6]}
domain_tags: {analysis.get("domain_tags", [])}
estimated_complexity: {analysis.get("estimated_complexity")}

Retrieved internal knowledge evidence:
{evidence_text}

Regeneration instruction:
{"This is a regeneration. Improve specificity, vary the framing, and focus on the most decision-critical facts without changing the evidence." if regenerate else "This is the first generation. Be concise, specific, and source-grounded."}

RFP excerpt:
<rfp>
{clipped_text}
</rfp>
"""
    try:
        result: RFPIntelligenceOutput = await llm_service.structured_extract(
            system_prompt=_RFP_INTELLIGENCE_SYSTEM_PROMPT,
            user_content=user_content,
            output_schema=RFPIntelligenceOutput,
            temperature=0.15 if regenerate else 0.02,
            model_name=settings.RFP_ANALYSIS_MODEL,
        )
        payload = result.model_dump()
        if (
            payload.get("sentiment_analysis", {}).get("summary")
            and payload.get("must_ask_questions")
            and payload.get("top_risks")
            and payload.get("talking_points")
            and (
                payload.get("architecture", {}).get("diagram", {}).get("nodes")
                or payload.get("architecture", {}).get("technical_view")
            )
        ):
            return payload
    except Exception as exc:
        logger.warning(f"RFP intelligence LLM generation unavailable; using evidence fallback: {exc}")
    return None


def _tab_text_key(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return text


def _is_repeated_tab_text(key: str, seen: set[str]) -> bool:
    if not key:
        return True
    if key in seen:
        return True
    if len(key) < 18:
        return False
    return any(key in existing or existing in key for existing in seen if min(len(key), len(existing)) >= 32)


def _dedupe_dict_cards(cards: Any, text_fields: tuple[str, ...], seen: set[str], *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(cards, list):
        return []
    output: list[dict[str, Any]] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        key_source = " ".join(str(card.get(field) or "") for field in text_fields)
        key = _tab_text_key(key_source)
        if _is_repeated_tab_text(key, seen):
            continue
        seen.add(key)
        output.append(card)
        if len(output) >= limit:
            break
    return output


def _dedupe_string_items(items: Any, seen: set[str], *, limit: int, cross_tab: bool = False) -> list[str]:
    if not isinstance(items, list):
        return []
    output: list[str] = []
    local_seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        key = _tab_text_key(text)
        target_seen = seen if cross_tab else local_seen
        if _is_repeated_tab_text(key, target_seen):
            continue
        target_seen.add(key)
        output.append(text)
        if len(output) >= limit:
            break
    return output


def _dedupe_intelligence_tabs(intelligence: dict[str, Any]) -> dict[str, Any]:
    """Remove repeated card text while preserving the tab contract."""
    seen: set[str] = set()
    intelligence["must_ask_questions"] = _dedupe_dict_cards(
        intelligence.get("must_ask_questions"),
        ("question", "assumption_to_validate"),
        seen,
        limit=10,
    )
    intelligence["top_risks"] = _dedupe_dict_cards(
        intelligence.get("top_risks"),
        ("risk_title", "impact"),
        seen,
        limit=8,
    )
    intelligence["talking_points"] = _dedupe_dict_cards(
        intelligence.get("talking_points"),
        ("point", "client_angle"),
        seen,
        limit=7,
    )

    narrative = intelligence.get("narrative")
    if isinstance(narrative, dict):
        narrative["how_it_helps"] = _dedupe_string_items(narrative.get("how_it_helps"), seen, limit=5)

    evidence = intelligence.get("relevant_knowledge_evidence")
    if isinstance(evidence, list):
        evidence_seen: set[str] = set()
        filtered_evidence = []
        for item in evidence:
            if not isinstance(item, dict):
                continue
            key = _tab_text_key(f"{item.get('title')} {item.get('why_relevant')}")
            if _is_repeated_tab_text(key, evidence_seen):
                continue
            evidence_seen.add(key)
            filtered_evidence.append(item)
            if len(filtered_evidence) >= 6:
                break
        intelligence["relevant_knowledge_evidence"] = filtered_evidence

    architecture = intelligence.get("architecture")
    if isinstance(architecture, dict):
        for key, limit in (
            ("business_view", 6),
            ("technical_view", 10),
            ("data_flow", 7),
            ("integration_flow", 7),
            ("security_operations", 8),
            ("decision_points", 7),
            ("call_prep_questions", 8),
        ):
            architecture[key] = _dedupe_string_items(
                architecture.get(key),
                seen,
                limit=limit,
                cross_tab=True,
            )
    return intelligence


def _build_rfp_intelligence(
    analysis: dict[str, Any],
    raw_text: str,
    report: dict[str, Any],
    *,
    knowledge_matches: list[dict[str, Any]] | None = None,
    architecture_text: str | None = None,
    architecture_generated_by: str = "structurizr_dsl_deterministic",
    intelligence_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = _knowledge_evidence_from_matches(knowledge_matches or [], analysis)
    recommendation = _architecture_detail(raw_text, analysis)
    architecture_artifact = _build_structurizr_architecture(raw_text, analysis)
    architecture_output = architecture_text or architecture_artifact["structurizr_dsl"]
    if intelligence_override:
        architecture_candidate = intelligence_override.get("architecture")
        architecture: dict[str, Any] = architecture_candidate if isinstance(architecture_candidate, dict) else {}
        intelligence = {
            "sentiment_analysis": intelligence_override.get("sentiment_analysis") or _sentiment_analysis(analysis, raw_text),
            "must_ask_questions": intelligence_override.get("must_ask_questions") or _must_ask_question_cards(raw_text, analysis.get("domain_tags", []), analysis),
            "top_risks": intelligence_override.get("top_risks") or _risk_assessment(raw_text, analysis.get("domain_tags", []), analysis),
            "talking_points": intelligence_override.get("talking_points") or _talking_points(report, analysis, raw_text),
            "narrative": intelligence_override.get("narrative") or _narrative_from_evidence(analysis, evidence, raw_text),
            "relevant_knowledge_evidence": evidence,
            "architecture": {
                "summary": architecture.get("summary") or recommendation.get("direction") or "",
                "business_view": architecture.get("business_view") or recommendation.get("business_view") or [],
                "technical_view": architecture.get("technical_view") or recommendation.get("technical_view") or [],
                "data_flow": architecture.get("data_flow") or recommendation.get("data_flow") or [],
                "integration_flow": architecture.get("integration_flow") or recommendation.get("integration_flow") or [],
                "security_operations": architecture.get("security_operations") or recommendation.get("security_operations") or [],
                "decision_points": architecture.get("decision_points") or recommendation.get("decision_points") or [],
                "call_prep_questions": architecture.get("call_prep_questions") or recommendation.get("call_prep_questions") or [],
                "architecture_text": architecture_output,
                "mermaid": "",
                "structurizr_dsl": architecture_artifact["structurizr_dsl"],
                "diagram": {
                    key: value
                    for key, value in architecture_artifact.items()
                    if key != "structurizr_dsl"
                },
                "generated_by": architecture_generated_by,
            },
        }
        return _dedupe_intelligence_tabs(intelligence)
    intelligence = {
        "sentiment_analysis": _sentiment_analysis(analysis, raw_text),
        "must_ask_questions": _must_ask_question_cards(raw_text, analysis.get("domain_tags", []), analysis),
        "top_risks": _risk_assessment(raw_text, analysis.get("domain_tags", []), analysis),
        "talking_points": _talking_points(report, analysis, raw_text),
        "narrative": _narrative_from_evidence(analysis, evidence, raw_text),
        "relevant_knowledge_evidence": evidence,
        "architecture": {
            "summary": recommendation.get("direction") or "",
            "business_view": recommendation.get("business_view") or [],
            "technical_view": recommendation.get("technical_view") or [],
            "data_flow": recommendation.get("data_flow") or [],
            "integration_flow": recommendation.get("integration_flow") or [],
            "security_operations": recommendation.get("security_operations") or [],
            "decision_points": recommendation.get("decision_points") or [],
            "call_prep_questions": recommendation.get("call_prep_questions") or [],
            "architecture_text": architecture_output,
            "mermaid": "",
            "structurizr_dsl": architecture_artifact["structurizr_dsl"],
            "diagram": {
                key: value
                for key, value in architecture_artifact.items()
                if key != "structurizr_dsl"
            },
            "generated_by": architecture_generated_by,
        },
    }
    return _dedupe_intelligence_tabs(intelligence)


async def _generate_architecture_output(raw_text: str, analysis: dict[str, Any]) -> tuple[str, str]:
    artifact = _build_structurizr_architecture(raw_text, analysis)
    return artifact["structurizr_dsl"], "structurizr_dsl_deterministic"


async def _enrich_rfp_intelligence(raw_text: str, payload: dict[str, Any], *, regenerate: bool = False) -> dict[str, Any]:
    report = payload.get("raw_llm_output", {}).get("executive_report", {})
    knowledge_matches: list[dict[str, Any]] = []
    query = _analysis_query(payload)
    if query:
        try:
            from app.services import knowledge_service

            knowledge_matches = await knowledge_service.search_knowledge(query, limit=8)
        except Exception as exc:
            logger.warning(f"Knowledge retrieval unavailable during RFP analysis enrichment: {exc}")

    evidence = _knowledge_evidence_from_matches(knowledge_matches, payload)
    intelligence_override = await _generate_llm_rfp_intelligence(
        raw_text,
        payload,
        evidence,
        regenerate=regenerate,
    )
    if intelligence_override is None:
        meta = payload.get("raw_llm_output", {}).get("extraction_meta")
        if isinstance(meta, dict):
            meta["warnings"] = _dedupe(
                [
                    *[str(item) for item in meta.get("warnings", [])],
                    "RFP intelligence model unavailable; returned source-extracted fallback cards.",
                ]
            )[:5]
    architecture_text, architecture_generated_by = await _generate_architecture_output(raw_text, payload)
    payload["raw_llm_output"]["rfp_intelligence"] = _build_rfp_intelligence(
        payload,
        raw_text,
        report if isinstance(report, dict) else {},
        knowledge_matches=knowledge_matches,
        architecture_text=architecture_text,
        architecture_generated_by=architecture_generated_by,
        intelligence_override=intelligence_override,
    )
    return payload


def _commercial_intelligence(raw_text: str, tags: list[str]) -> dict[str, Any]:
    lower = raw_text.lower()
    drivers = ["Team duration", "Scope uncertainty", "Acceptance criteria"]
    if any(term in lower for term in ("api", "integration", "microservice", "existing system")):
        drivers.append("Integration discovery and testing")
    if any(term in lower for term in ("data", "migration", "report", "analytics", "database")):
        drivers.append("Data profiling, migration, reporting, or reconciliation")
    if any(term in lower for term in ("security", "audit", "privacy", "confidential", "encryption")):
        drivers.append("Security, audit, and compliance evidence")
    if any(term in lower for term in ("operate", "maintain", "support", "sla", "o&m")):
        drivers.append("Operations and support coverage")
    return {
        "estimate_disclaimer": "Directional estimate only; validate after scope, dependencies, and commercial terms are clarified.",
        "estimated_project_size_range": "To be validated after discovery.",
        "estimated_delivery_cost_range": "To be validated after discovery.",
        "margin_attractiveness": "Unknown until scope, timeline, and client dependencies are clarified.",
        "major_cost_drivers": _dedupe(drivers),
        "pricing_model_recommendation": "Discovery-first pricing followed by milestone-based implementation.",
        "commercial_risks": ["Ambiguous scope", "Unclear acceptance criteria", "Client dependency delays"],
    }


def _competitor_intelligence(raw_text: str, tags: list[str]) -> list[dict[str, str]]:
    return [
        {
            "competitor_category": "Large system integrators",
            "likely_positioning": "Delivery scale, process maturity, compliance comfort, and ability to staff quickly.",
            "strength": "Procurement familiarity and execution capacity.",
            "weakness": "May propose heavier delivery models with slower clarification cycles.",
            "counter_position": "Lead with sharper discovery, clearer assumptions, faster MVP governance, and evidence-backed delivery risk control.",
        },
        {
            "competitor_category": "Specialist technology firms",
            "likely_positioning": "Domain-specific expertise and faster prototyping.",
            "strength": "Focused technical depth.",
            "weakness": "May underplay governance, operations, and enterprise handover.",
            "counter_position": "Position technical depth together with delivery governance, security, documentation, and operating model clarity.",
        },
        {
            "competitor_category": "Low-cost implementation vendors",
            "likely_positioning": "Lower price and flexible staffing.",
            "strength": "Cost competitiveness.",
            "weakness": "May accept unclear scope and create delivery risk later.",
            "counter_position": "Use explicit assumptions, risk register, architecture clarity, and phased commitments to show lower total delivery risk.",
        },
    ]


def _prospect_call_prep(raw_text: str, tags: list[str], missing: list[str]) -> dict[str, Any]:
    return {
        "opening_narrative_30_seconds": "We see this as a qualification conversation: clarify the business outcome, separate delivery scope from tender process text, and identify the risks that affect timeline, cost, and acceptance.",
        "strongest_talking_points": [
            "Confirm the business outcome before discussing implementation scope.",
            "Separate mandatory requirements from optional or future-phase work.",
            "Make client-owned dependencies visible before price and timeline commitments.",
            "Use a phased delivery model tied to measurable acceptance gates.",
            "Turn every unknown into an explicit assumption, exclusion, or discovery action.",
        ],
        "must_ask_discovery_questions": missing[:10],
        "technical_questions": [
            "Which systems, user roles, workflows, integrations, data sources, and environments are in scope?",
            "What non-functional requirements are mandatory for performance, availability, observability, and security?",
            "What acceptance tests, UAT data, and sign-off process will determine completion?",
        ],
        "commercial_questions": [
            "What pricing model, budget guardrails, payment milestones, warranty period, and O&M duration should be assumed?",
            "Which client delays, data gaps, access issues, or change requests should trigger commercial change control?",
        ],
        "risk_questions": [
            "What has failed or been difficult in previous attempts?",
            "Which dependencies are client-owned and timeline-critical?",
            "What is explicitly out of scope for the first release?",
        ],
        "assumptions_to_validate": [
            "Scope can be phased into discovery, MVP, rollout, and support.",
            "Client access, data, environments, and approvals will be available on agreed dates.",
            "Acceptance criteria and sign-off ownership can be agreed before implementation starts.",
            "O&M, warranty, and change-control obligations are separately defined.",
        ],
        "avoid_overcommitting_on": [
            "Fixed price without discovery.",
            "Dates without dependency readiness.",
            "Architecture or compliance claims not confirmed by the client environment.",
        ],
    }


def _build_executive_report(
    analysis: dict[str, Any],
    raw_text: str,
    document_sections: list[dict[str, Any]],
    normalized_requirements: list[dict[str, Any]],
    excluded_noise: list[dict[str, Any]],
) -> dict[str, Any]:
    tags = analysis.get("domain_tags", [])
    missing = _missing_information_questions(raw_text, tags, analysis)
    scores = _score_bid(analysis, normalized_requirements, raw_text)
    decision = "Bid with Clarifications" if scores["overall_bid_score"] >= 70 else "Hold"
    if scores["overall_bid_score"] >= 84 and len(missing) <= 8:
        decision = "Strong Bid"
    if scores["overall_bid_score"] < 55:
        decision = "No Bid"

    ceo_brief = (
        f"{analysis.get('business_problem') or 'The buyer has described a technology initiative with unresolved scope details.'} "
        "The next action is to qualify business outcomes, must-have scope, client-owned dependencies, acceptance criteria, operating obligations, and commercial exposure before committing price or dates."
    )
    pain_points = [
        "Business pain and success metrics need validation with executive stakeholders.",
        "Unclear assumptions can affect delivery scope, architecture, pricing, and acceptance.",
    ]
    if analysis.get("integration_needs"):
        pain_points.append("Integration ownership and environment readiness may become gating delivery dependencies.")
    if analysis.get("data_needs"):
        pain_points.append("Data quality, access, ownership, and reporting expectations may affect delivery confidence.")
    if analysis.get("compliance_needs") or analysis.get("non_functional_requirements"):
        pain_points.append("Security, performance, availability, audit, or compliance expectations may affect solution design.")
    business_problem = {
        "current_state": analysis.get("business_problem") or "Not clearly stated.",
        "pain_points": _dedupe(pain_points)[:6],
        "business_consequences": [
            "Unclear success criteria can cause pricing, delivery, and acceptance risk.",
            "Unvalidated dependencies can create timeline and margin exposure.",
        ],
        "desired_future_state": "A scoped delivery plan tied to measurable business outcomes, validated dependencies, explicit assumptions, and an architecture aligned to the RFP.",
        "executive_interpretation": "Treat the first call as a qualification and scope-control conversation.",
        "confidence": "medium",
        "evidence": analysis.get("business_problem") or "",
    }

    quality_checks = _quality_checks(analysis, normalized_requirements, excluded_noise, missing, ceo_brief)
    return {
        "ceo_brief": ceo_brief,
        "bid_recommendation": {
            "decision": decision,
            "overall_score": scores["overall_bid_score"],
            "strategic_fit": scores["strategic_fit"],
            "technical_fit": scores["technical_fit"],
            "domain_fit": scores["domain_fit"],
            "delivery_risk": scores["delivery_risk"],
            "commercial_attractiveness": scores["commercial_attractiveness"],
            "competitive_position": scores["competitive_position"],
            "rationale": "Potential fit exists, but commitment quality depends on validated scope, dependencies, acceptance criteria, operating obligations, and commercial guardrails.",
            "score_breakdown": {
                "strategic_fit": scores["strategic_fit"],
                "technical_fit": scores["technical_fit"],
                "domain_fit": scores["domain_fit"],
                "delivery_risk": scores["delivery_risk"],
                "commercial_attractiveness": scores["commercial_attractiveness"],
                "competitive_position": scores["competitive_position"],
            },
            "confidence": "medium",
            "assumption": True,
        },
        "business_problem": business_problem,
        "solution_scope": normalized_requirements,
        "excluded_noise": excluded_noise,
        "missing_information": [
            {"category": "Business and success metrics", "questions": missing[:5]},
            {"category": "Data, integration, and technical readiness", "questions": missing[5:10]},
            {"category": "Delivery, operations, security, and commercial", "questions": missing[10:]},
        ],
        "risk_assessment": _risk_assessment(raw_text, tags, analysis),
        "delivery_complexity": _delivery_complexity(raw_text, tags),
        "architecture_recommendation": _architecture_recommendation(raw_text, tags, analysis),
        "commercial_intelligence": _commercial_intelligence(raw_text, tags),
        "competitor_intelligence": _competitor_intelligence(raw_text, tags),
        "win_strategy": [
            "Lead with business outcomes and measurable success criteria.",
            "Separate true solution scope from procurement/legal/admin text.",
            "Use phased discovery and implementation to control risk.",
            "Make assumptions, exclusions, dependencies, and acceptance gates explicit.",
            "Anchor the client narrative in relevant internal evidence rather than unsupported claims.",
            "Present architecture as a validated direction, not a fixed commitment before discovery.",
        ],
        "prospect_call_prep": _prospect_call_prep(raw_text, tags, missing),
        "past_expertise_match": {
            "match_type": "No match",
            "confidence_score": 0,
            "matched_assets": [],
            "reusable_components": [],
            "past_expertise_story": "No internal past project corpus connected yet. Match confidence is limited.",
            "gaps": ["Connect internal project corpus, case studies, architecture docs, and reusable code repositories to improve match evidence."],
            "assumption": True,
        },
        "proposal_outline": [
            "Executive summary",
            "Understanding of the buyer's business problem",
            "Proposed solution",
            "Technical architecture",
            "Implementation methodology",
            "Integration approach",
            "Deployment approach",
            "Security and compliance",
            "Project plan",
            "Team structure",
            "Assumptions",
            "Risks and mitigations",
            "Commercial approach",
            "Differentiators",
            "Appendix",
        ],
        "quality_checks": quality_checks,
        "document_section_summary": {
            category: sum(1 for section in document_sections if section["category"] == category)
            for category in _SECTION_CATEGORIES
        },
    }


def _quality_checks(
    analysis: dict[str, Any],
    requirements: list[dict[str, Any]],
    excluded_noise: list[dict[str, Any]],
    missing: list[str],
    ceo_brief: str,
) -> dict[str, Any]:
    requirement_text = " ".join(
        [str(item.get("requirement_name", "")) + " " + str(item.get("description", "")) for item in requirements]
    ).lower()
    functionals = " ".join(str(item) for item in analysis.get("functional_requirements", [])).lower()
    domain_tags = set(analysis.get("domain_tags", []))
    accidental_noise_terms = [
        "bids received after closing",
        "audited balance sheet",
        "statutory auditor",
        "bidder registration",
        "earnest money",
    ]
    checks = {
        "functional_requirements_are_solution_features": not any(term in functionals for term in accidental_noise_terms),
        "procurement_instructions_excluded_from_scope": bool(excluded_noise) and not any(term in requirement_text for term in accidental_noise_terms),
        "missing_information_not_empty": bool(missing),
        "domain_tags_are_specific": bool(domain_tags),
        "ceo_brief_answers_business_impact": any(term in ceo_brief.lower() for term in ("business", "outcome", "scope", "success", "risk", "recommendation")),
        "bid_recommendation_exists": True,
        "risks_clarifications_win_strategy_delivery_model_exist": True,
        "unsupported_claims_marked_as_assumptions": True,
        "hallucinated_past_projects_avoided": True,
        "evidence_present_for_extracted_scope": all(bool(item.get("evidence")) for item in requirements[:5]) if requirements else False,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "warnings": [
            "Low-confidence extraction; review source evidence before executive use."
        ] if not checks["evidence_present_for_extracted_scope"] else [],
    }


def _clean_analysis_items(items: Any, *, solution_field: bool = True) -> list[str]:
    if not isinstance(items, list):
        return []
    cleaned: list[str] = []
    for item in items:
        text = _strip_reference_noise(str(item))
        if not text or len(text) < 18:
            continue
        if _is_low_value_unit(text) or _is_noise_line(text):
            continue
        if solution_field and _is_solution_scope_noise(text):
            continue
        cleaned.append(text[:520])
    return _dedupe(cleaned)


def _apply_executive_trust_gate(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    removed: list[dict[str, str]] = []
    gated_keys = (
        "functional_requirements",
        "non_functional_requirements",
        "data_needs",
        "integration_needs",
    )
    for key in gated_keys:
        kept: list[str] = []
        for item in payload.get(key, []) or []:
            text = str(item)
            if _is_solution_scope_noise(text):
                category, _, reason = _classify_document_section(text)
                removed.append(
                    {
                        "field": key,
                        "text": text[:260],
                        "reclassified_as": category,
                        "reason": reason,
                    }
                )
            else:
                kept.append(text)
        payload[key] = _dedupe(kept)
    return payload, removed


def sanitize_executive_output(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Remove tender/admin/legal noise before anything is used for leadership output."""
    return _apply_executive_trust_gate(payload)


def _sanitize_analysis_payload(payload: dict[str, Any], raw_text: str) -> dict[str, Any]:
    units = _candidate_units(raw_text)
    business_problem = str(payload.get("business_problem") or "").strip()
    if not business_problem or _is_low_value_unit(business_problem) or len(business_problem) < 30:
        payload["business_problem"] = _business_problem_from_source(units, raw_text)

    for key in (
        "functional_requirements",
        "non_functional_requirements",
        "data_needs",
        "integration_needs",
        "compliance_needs",
        "timeline_risks",
        "scope_boundaries",
    ):
        payload[key] = _clean_analysis_items(
            payload.get(key),
            solution_field=key in {"functional_requirements", "non_functional_requirements", "data_needs", "integration_needs"},
        )

    payload, trust_gate_removed = sanitize_executive_output(payload)
    payload["_trust_gate_removed"] = trust_gate_removed

    payload["domain_tags"] = _infer_domain_tags(raw_text)
    payload["missing_information"] = _clean_analysis_items(payload.get("missing_information"), solution_field=False)
    missing_questions = _missing_information_questions(raw_text, payload["domain_tags"], payload)
    if not payload["missing_information"] or len(payload["missing_information"]) < 6:
        payload["missing_information"] = missing_questions
    else:
        payload["missing_information"] = _dedupe([*payload["missing_information"], *missing_questions])[:20]
    payload["estimated_complexity"] = _estimate_complexity(payload, raw_text)
    return payload


def _confidence(level: str) -> float:
    return {"high": 0.82, "medium": 0.64, "low": 0.45}[level]


def _insight(
    title: str,
    insight: str,
    evidence: str,
    source: str,
    confidence: str,
    recommendation: str,
) -> dict[str, Any]:
    return {
        "title": title,
        "insight": insight,
        "evidence": evidence,
        "source": source,
        "confidence": _confidence(confidence),
        "recommendation": recommendation,
    }


def _joined(items: list[str], fallback: str, limit: int = 3) -> str:
    selected = [item for item in items if item and not _is_tender_boilerplate(item)][:limit]
    return "; ".join(selected) if selected else fallback


def _capability_labels(tags: list[str]) -> list[str]:
    return [CAPABILITY_LABELS.get(tag, tag.replace("_", " ")) for tag in tags]


def _build_executive_intelligence(analysis: dict[str, Any], raw_text: str | None = None) -> dict[str, Any]:
    functional = _dedupe([item for item in analysis.get("functional_requirements", []) if not _is_tender_boilerplate(item)])
    nfrs = _dedupe([item for item in analysis.get("non_functional_requirements", []) if not _is_tender_boilerplate(item)])
    data_needs = _dedupe([item for item in analysis.get("data_needs", []) if not _is_tender_boilerplate(item)])
    integrations = _dedupe([item for item in analysis.get("integration_needs", []) if not _is_tender_boilerplate(item)])
    compliance = _dedupe([item for item in analysis.get("compliance_needs", []) if not _is_tender_boilerplate(item)])
    risks = _dedupe([item for item in analysis.get("timeline_risks", []) if not _is_tender_boilerplate(item)])
    gaps = _dedupe(analysis.get("missing_information", []))
    tags = analysis.get("domain_tags", [])
    capabilities = _capability_labels(tags)
    opportunity_title = _extract_opportunity_title(raw_text or "") if raw_text else ""
    client_name = _extract_client_name(raw_text or "") if raw_text else ""

    summary_parts = []
    business_problem = str(analysis.get("business_problem") or "").strip()
    if business_problem and not _is_low_value_unit(business_problem):
        summary_parts.append(business_problem)
    elif opportunity_title:
        summary_parts.append(
            (f"{client_name} is " if client_name else "The buyer is ")
            + "seeking "
            + opportunity_title
            + "."
        )
    if capabilities:
        summary_parts.append(
            "For leadership, the core qualification question is whether this is only resource supply or a broader delivery-capacity, governance, and dependency-control play."
        )
    summary_parts.append(
        "Leadership should qualify whether the buyer is seeking a strategic operating improvement or only a compliant vendor response."
    )
    if integrations or data_needs or nfrs:
        summary_parts.append(
            "The commercial risk is concentrated around unverified "
            + ", ".join(
                [
                    label
                    for condition, label in (
                        (bool(integrations), "integration readiness"),
                        (bool(data_needs), "data ownership and migration"),
                        (bool(nfrs), "security/service expectations"),
                    )
                    if condition
                ]
            )
            + "."
        )

    key_insights = [
        _insight(
            "Opportunity is broader than feature delivery",
            "The RFP signals a need to expand delivery capacity and improve an operating capability, not merely deliver isolated tasks.",
            _joined(functional, analysis.get("business_problem") or "Functional scope references were extracted from the RFP."),
            "inferred_from_rfp",
            "medium",
            "Open the executive conversation around business outcomes, operating model, success metrics, and phased value rather than jumping into a feature estimate.",
        ),
    ]
    if integrations:
        key_insights.append(
            _insight(
                "Integration readiness is a gating risk",
                "The delivery plan may depend on external systems, API availability, ownership, test environments, and production approval paths.",
                _joined(integrations, "Integration requirements are present in the RFP."),
                "explicit_in_rfp",
                "high",
                "Ask for API documentation, sandbox access, owner matrix, sample payloads, integration SLAs, and approval timelines before committing effort or dates.",
            )
        )
    if data_needs:
        key_insights.append(
            _insight(
                "Data quality and migration need executive ownership",
                "Data movement, reporting, or database references imply business accountability for source quality, reconciliation, retention, and reporting cadence.",
                _joined(data_needs, "Data/reporting requirements are present in the RFP."),
                "inferred_from_rfp",
                "medium",
                "Confirm source-of-truth systems, data owners, cleansing responsibility, reconciliation approach, reporting KPIs, and retention obligations.",
            )
        )
    if compliance or nfrs:
        key_insights.append(
            _insight(
                "Security and compliance should be treated as design constraints",
                "Security, audit, monitoring, or compliance references can affect architecture, staffing, cost, deployment model, and acceptance criteria.",
                _joined([*nfrs, *compliance], "Security/compliance requirements are present in the RFP."),
                "explicit_in_rfp",
                "high",
                "Validate mandatory controls, audit evidence, SIEM/monitoring expectations, access model, vulnerability testing, and sign-off authority early.",
            )
        )

    opportunity_assessment = [
        _insight(
            "Qualification priority",
            "The pursuit should be qualified on buyer clarity, dependency readiness, and executive sponsorship before pricing confidence is claimed.",
            _joined(gaps, "The RFP leaves several scoping assumptions unresolved."),
            "derived_from_industry_knowledge",
            "medium",
            "Use the first call to separate must-have scope, optional scope, buyer-owned dependencies, and non-negotiable compliance gates.",
        )
    ]
    if risks:
        opportunity_assessment.append(
            _insight(
                "Commercial exposure exists if tender timelines are accepted literally",
                "Timeline and milestone clauses may hide dependency risk if the buyer cannot provide data, access, approvals, or test environments on time.",
                _joined(risks, "Timeline or commercial clauses were extracted from the RFP."),
                "inferred_from_rfp",
                "medium",
                "Convert dates into a dependency-based delivery plan with explicit assumptions, exclusions, and change-control triggers.",
            )
        )

    recommendations = [
        "Lead with an executive discovery call focused on outcomes, decision criteria, current-state pain, and success metrics.",
        "Do not provide a fixed estimate until integration access, data readiness, security controls, UAT ownership, and support expectations are validated.",
        "Frame the solution as modular workstreams: experience/workflow, integration, data/reporting, security/compliance, operations/support, and rollout governance.",
        "Create a bid/no-bid checkpoint after validating buyer dependency ownership and commercial risk.",
    ]

    return {
        "executive_summary": " ".join(summary_parts),
        "key_insights": key_insights[:5],
        "opportunity_assessment": opportunity_assessment,
        "business_drivers": [
            "Increase software delivery capacity without losing governance over scope, quality, and cost.",
            "Accelerate modernization demand through empaneled or reusable delivery capability.",
            "Reduce dependency risk across APIs, data, security controls, acceptance gates, and production support.",
            "Create a scalable vendor engagement model rather than a one-off staff augmentation exercise.",
        ],
        "risks_and_dependencies": [
            item["insight"] + " " + item["recommendation"]
            for item in [*key_insights, *opportunity_assessment]
            if item["title"] in {"Integration readiness is a gating risk", "Data quality and migration need executive ownership", "Security and compliance should be treated as design constraints", "Commercial exposure exists if tender timelines are accepted literally"}
        ][:6],
        "recommendations": recommendations,
        "evidence_mode": "explicit/inferred/industry-labeled",
    }


async def _generate_llm_executive_intelligence(
    raw_text: str,
    extracted: dict[str, Any],
    *,
    regenerate: bool = False,
) -> dict[str, Any] | None:
    llm_service = get_llm_service()
    clipped_text = raw_text[:18_000]
    user_content = f"""
Create executive-grade RFP intelligence for this opportunity.

Do not summarize the RFP. Do not copy tender submission/legal boilerplate.
Use the extracted facts only as evidence signals; challenge ambiguity.

Extracted signals:
{extracted}

Regeneration instruction:
{"This is a regeneration. Improve specificity, risk ordering, and client-call usefulness without changing facts or inventing unsupported details." if regenerate else "This is the first generation. Stay concise and strictly grounded."}

RFP text:
<document>
{clipped_text}
</document>
"""
    try:
        result: ExecutiveIntelligenceOutput = await llm_service.structured_extract(
            system_prompt=_EXECUTIVE_SYSTEM_PROMPT,
            user_content=user_content,
            output_schema=ExecutiveIntelligenceOutput,
            temperature=0.15 if regenerate else 0.0,
            model_name=settings.RFP_ANALYSIS_MODEL,
        )
        payload = result.model_dump()
        if payload.get("executive_summary"):
            return payload
    except Exception as exc:
        logger.warning(f"Executive intelligence LLM generation unavailable; using deterministic strategy fallback: {exc}")
    return None


def _legacy_executive_intelligence_from_report(report: dict[str, Any]) -> dict[str, Any]:
    bid = report.get("bid_recommendation", {})
    risks = report.get("risk_assessment", [])
    win_strategy = report.get("win_strategy", [])
    return {
        "executive_summary": report.get("ceo_brief", ""),
        "key_insights": [
            _insight(
                "Bid decision",
                f"{bid.get('decision', 'Qualification needed')} with score {bid.get('overall_score', 'N/A')}/100.",
                bid.get("rationale", ""),
                "inferred_from_rfp",
                "medium",
                "Use clarifications to convert unknowns into proposal assumptions before pricing.",
            ),
            _insight(
                "Business problem",
                str(report.get("business_problem", {}).get("executive_interpretation", "")),
                str(report.get("business_problem", {}).get("evidence", "")),
                "inferred_from_rfp",
                "high" if report.get("business_problem", {}).get("confidence") == "high" else "medium",
                "Lead the client conversation with business impact and measurable success criteria.",
            ),
        ],
        "opportunity_assessment": [
            _insight(
                "Primary delivery risk",
                str(risks[0].get("impact", "")) if risks else "Risk assessment requires review.",
                str(risks[0].get("risk_title", "")) if risks else "",
                "inferred_from_rfp",
                "medium",
                str(risks[0].get("mitigation", "")) if risks else "Validate risks during discovery.",
            )
        ],
        "business_drivers": report.get("business_problem", {}).get("business_consequences", []),
        "risks_and_dependencies": [str(item.get("risk_title", "")) + ": " + str(item.get("mitigation", "")) for item in risks[:6]],
        "recommendations": win_strategy[:6],
        "discovery_strategy": report.get("prospect_call_prep", {}).get("must_ask_discovery_questions", [])[:6],
        "evidence_mode": "executive_report",
    }


def _finalize_analysis_payload(
    payload: dict[str, Any],
    raw_text: str,
    extraction_meta: dict[str, Any],
    executive_intelligence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_extraction_internal = {
        "business_problem": payload.get("business_problem"),
        "functional_requirements": payload.get("functional_requirements", []),
        "non_functional_requirements": payload.get("non_functional_requirements", []),
        "data_needs": payload.get("data_needs", []),
        "integration_needs": payload.get("integration_needs", []),
        "compliance_needs": payload.get("compliance_needs", []),
        "timeline_risks": payload.get("timeline_risks", []),
        "missing_information": payload.get("missing_information", []),
        "scope_boundaries": payload.get("scope_boundaries", []),
        "domain_tags": payload.get("domain_tags", []),
        "estimated_complexity": payload.get("estimated_complexity"),
    }
    payload = _sanitize_analysis_payload(payload, raw_text)
    trust_gate_removed = payload.pop("_trust_gate_removed", [])
    document_sections = _classify_document_sections(raw_text)
    excluded_noise = _excluded_noise_from_sections(document_sections)
    if trust_gate_removed:
        excluded_noise = [
            *excluded_noise,
            *[
                {
                    "category": item["reclassified_as"],
                    "text": item["text"],
                    "why_excluded": item["reason"],
                    "confidence": 0.9,
                }
                for item in trust_gate_removed
            ],
        ][:32]
    normalized_requirements = _normalized_requirements(raw_text, payload)
    executive_report = _build_executive_report(
        payload,
        raw_text,
        document_sections,
        normalized_requirements,
        excluded_noise,
    )
    rfp_intelligence = _build_rfp_intelligence(payload, raw_text, executive_report)
    if not executive_intelligence:
        executive_intelligence = _legacy_executive_intelligence_from_report(executive_report)

    payload["raw_llm_output"] = {
        **payload,
        "extraction_meta": extraction_meta,
        "raw_extraction_internal": raw_extraction_internal,
        "document_sections": document_sections,
        "normalized_requirements": normalized_requirements,
        "excluded_noise": excluded_noise,
        "executive_report": executive_report,
        "rfp_intelligence": rfp_intelligence,
        "executive_intelligence": executive_intelligence,
    }
    return payload


def _deterministic_extract(raw_text: str) -> tuple[RFPExtractionOutput, dict[str, Any]]:
    lines = _clean_lines(raw_text)
    units = _candidate_units(raw_text)

    analysis: dict[str, Any] = {
        "business_problem": _business_problem_from_source(units, raw_text),
        "functional_requirements": _pick_units(
            units,
            {
                "application",
                "mobile",
                "system",
                "software",
                "dashboard",
                "user",
                "module",
                "workflow",
                "screen",
                "nlp",
                "natural language processing",
                "string optimizer",
                "stop word",
                "stemming",
                "lemmatization",
                "tokenization",
                "normalization",
                "noise removal",
                "classification",
                "categorization",
                "tf-idf",
                "word2vec",
                "svm",
                "naive bayes",
            },
            limit=10,
            require_actionable=False,
            exclude_admin_only=True,
        ),
        "non_functional_requirements": _pick_units(
            units,
            {"performance", "security", "secure", "availability", "uptime", "scalable", "latency", "responsive", "audit", "access control"},
            limit=8,
            require_actionable=False,
            exclude_admin_only=True,
        ),
        "data_needs": _pick_units(
            units,
            {"data", "database", "records", "report", "statistical", "storage", "document", "backend", "catalog", "taxonomy", "category", "training data", "search logs"},
            limit=8,
            exclude_admin_only=True,
        ),
        "integration_needs": _pick_units(
            units,
            {"api", "apis", "integration", "integrate", "internal systems", "third party", "external", "mobile apis", "solr", "apache solr", "microservice", "micro-service"},
            limit=8,
            exclude_admin_only=True,
        ),
        "compliance_needs": _pick_units(
            units,
            {"authorization", "security", "privacy", "confidential", "regulatory", "compliance", "license", "insurance", "gst", "audit"},
            limit=8,
        ),
        "timeline_risks": _pick_units(
            units,
            {"date", "time", "deadline", "days", "weeks", "delay", "validity", "opening", "submission", "within"},
            limit=8,
        ),
        "missing_information": [],
        "scope_boundaries": _pick_units(
            units,
            {"scope", "out of scope", "in scope", "maintenance", "support", "selected bidder shall", "services", "gcc", "deployment", "hosting", "operation and maintenance", "o&m"},
            limit=8,
        ),
        "domain_tags": _infer_domain_tags(raw_text),
    }

    analysis["missing_information"] = _critical_gaps(analysis)[:8]

    analysis["estimated_complexity"] = _estimate_complexity(analysis, raw_text)
    executive_intelligence = _build_executive_intelligence(analysis, raw_text)
    evidence = {
        "mode": "deterministic_source_text",
        "confidence": 0.55 if len(lines) >= 10 else 0.35,
        "warnings": [
            "LLM structured extraction was unavailable or invalid.",
            "Fallback generated executive intelligence from source-grounded requirement signals.",
        ],
        "source_line_count": len(lines),
        "candidate_unit_count": len(units),
        "evidence_snippets": units[:12],
        "executive_intelligence": executive_intelligence,
    }
    return RFPExtractionOutput.model_validate(analysis), evidence


async def analyze_rfp_document(raw_text: str, *, regenerate: bool = False) -> dict[str, Any]:
    """
    Run the RFP Understanding Engine on extracted document text.
    """
    llm_service = get_llm_service()
    clipped_text = raw_text[:15_000]
    user_content = f"""
Analyze this RFP or client requirements document.

Return only JSON matching the schema. Do not include markdown.

<document>
{clipped_text}
</document>
"""

    logger.info(f"Running RFP extraction on {len(raw_text)} chars of text")

    extraction_meta: dict[str, Any]
    try:
        result: RFPExtractionOutput = await llm_service.structured_extract(
            system_prompt=_SYSTEM_PROMPT,
            user_content=user_content,
            output_schema=RFPExtractionOutput,
            temperature=0.1 if regenerate else 0.0,
            model_name=settings.RFP_ANALYSIS_MODEL,
        )
        extraction_meta = {
            "mode": "llm_structured",
            "confidence": 0.82,
            "warnings": [],
            "source_chars_used": len(clipped_text),
        }
    except Exception as exc:
        logger.warning("RFP LLM extraction unavailable; using deterministic grounded fallback.")
        result, extraction_meta = _deterministic_extract(raw_text)
        extraction_meta["warnings"] = _dedupe(
            [
                *[str(item) for item in extraction_meta.get("warnings", [])],
                f"LLM analysis unavailable: {str(exc)}",
            ]
        )[:4]

    payload = result.model_dump()
    # The RFP Analysis page now uses raw_llm_output.rfp_intelligence. Avoid a
    # second large executive-intelligence LLM call here so the first-page
    # intelligence and architecture calls stay within provider TPM limits.
    executive_intelligence = extraction_meta.get("executive_intelligence")
    finalized = _finalize_analysis_payload(payload, raw_text, extraction_meta, executive_intelligence)
    return await _enrich_rfp_intelligence(raw_text, finalized, regenerate=regenerate)
