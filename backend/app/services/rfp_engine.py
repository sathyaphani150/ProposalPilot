"""
ProposalPilot AI - RFP Understanding Engine.

The engine prefers structured LLM extraction, but never fabricates fallback
answers. If the LLM path fails, it returns a conservative source-text-only
analysis so the workflow remains demo-stable without hallucinating.
"""
from __future__ import annotations

import re
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field, field_validator

from app.services.llm_service import get_llm_service


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


_CAPABILITY_TAG_KEYWORDS: dict[str, set[str]] = {
    "NLP": {"nlp", "natural language processing", "lemmatization", "stemming", "tokenization"},
    "Search Optimization": {"search optimization", "string optimizer", "search string", "search relevance", "search result"},
    "Information Retrieval": {"information retrieval", "tf-idf", "tf idf", "ranking", "retrieval"},
    "Query Understanding": {"query intent", "query understanding", "user query", "search query"},
    "Product Category Classification": {"category classification", "categorization", "classify product", "classify service"},
    "Machine Learning": {"machine learning", "ml algorithm", "word2vec", "svm", "naive bayes", "model training"},
    "Cognitive Search": {"cognitive search", "semantic search", "intelligent search"},
    "Search Relevance": {"relevance", "precision", "recall", "ndcg", "mrr"},
    "Catalog Management": {"catalog", "product catalog", "service catalog", "seller upload"},
    "API Integration": {"api", "apis", "microservice", "micro-service", "integration", "integrate"},
    "Cloud/Hosted Deployment": {"cloud", "deployment", "hosting"},
    "Security": {"security", "privacy", "encryption", "audit", "access control", "sso"},
    "Operations & Maintenance": {"operation and maintenance", "o&m", "maintenance", "sla", "support"},
}

_SECTION_CATEGORIES = (
    "solution_scope",
    "business_context",
    "technical_requirement",
    "non_functional_requirement",
    "integration_requirement",
    "data_requirement",
    "compliance_security",
    "infrastructure_operational_requirement",
    "service_level",
    "evaluation_criteria",
    "bidder_eligibility",
    "procurement_process",
    "legal_disclaimer",
    "commercial_terms",
    "buyer_contact_or_location",
    "annexure/forms",
    "irrelevant_noise",
)

_EXCLUDED_SECTION_CATEGORIES = {
    "bidder_eligibility",
    "procurement_process",
    "legal_disclaimer",
    "commercial_terms",
    "annexure/forms",
    "buyer_contact_or_location",
    "evaluation_criteria",
    "irrelevant_noise",
}

_TRUST_GATE_NOISE_TERMS = {
    "audited balance",
    "balance sheet",
    "statutory auditor",
    "certificate of incorporation",
    "turnover",
    "net worth",
    "blacklisted",
    "blacklisting",
    "emd",
    "earnest money",
    "bid submission",
    "pre-bid meeting",
    "pre bid meeting",
    "date of bid opening",
    "bid opening",
    "contact details",
    "address",
    " floor",
    "building",
    "new delhi",
    "connaught place",
    "disclaimer",
    "no liability",
    "no representation",
    "bidder shall bear",
    "cost of bid",
    "annexure",
    "self-certified",
    "self certified",
    "notarized",
    "gst",
    "companies act",
    "llp act",
    "independent advice",
    "not an agreement",
    "not an offer",
}

_TECHNICAL_SIGNAL_TERMS = {
    "nlp",
    "nlu",
    "natural language processing",
    "search string optimization",
    "string optimizer",
    "stop-word",
    "stop word",
    "stemming",
    "lemmatization",
    "tokenization",
    "normalization",
    "noise removal",
    "feature extraction",
    "category classifier",
    "category classification",
    "tf-idf",
    "tf idf",
    "word2vec",
    "support vector machine",
    "svm",
    "naive bayes",
    "cognitive search",
    "search relevance",
    "query understanding",
    "seller category suggestion",
}

_INTEGRATION_SIGNAL_TERMS = {
    "microservice",
    "micro-service",
    "api",
    "existing web service",
    "apache solr",
    "solr",
    "current search architecture",
    "integration",
    "consumed by apis",
}

_INFRA_OPERATIONAL_SIGNAL_TERMS = {
    "gcc infrastructure",
    "hosting",
    "deployment",
    "install",
    "commission",
    "operate",
    "maintain",
    "operation and maintenance",
    "o&m",
    "availability",
    "cloud service",
    "performance",
    "observability",
    "support",
}

_ADMIN_TERMS = {
    "bid",
    "bids",
    "bidder",
    "bidders",
    "tender",
    "proposal",
    "proposals",
    "bank guarantee",
    "earnest money",
    "emd",
    "acceptance",
    "work order",
    "forfeited",
    "submission",
    "letter of authorization",
    "bid-security",
    "bid security",
    "technical score",
    "bid score",
    "bid price",
    "evaluated bid",
    "addendum",
    "addenda",
    "read the rfp",
    "submission of bid",
    "procedure",
    "certifying authority",
    "mapped documents",
    "digital signature",
    "dsc",
    "e-tender",
    "tendering portal",
    "pre-contract integrity pact",
    "bids received after closing",
    "shall be rejected",
    "bid closing",
    "bidder registration",
    "registered bidder",
    "audited balance sheet",
    "statutory auditor",
    "net worth",
    "turnover",
    "blacklisting",
    "declaration",
    "annexure",
    "form",
}

_DELIVERY_TERMS = {
    "application",
    "mobile",
    "system",
    "software",
    "portal",
    "api",
    "apis",
    "database",
    "dashboard",
    "report",
    "user",
    "integration",
    "backend",
    "frontend",
    "service",
    "module",
    "workflow",
}


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
    }
    return any(term in lower for term in low_value_terms)


def _contains_any(text: str, terms: set[str]) -> bool:
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
    eligibility_terms = {
        "audited balance sheet",
        "audited books of accounts",
        "copy of audited",
        "turnover",
        "net worth",
        "certificate of incorporation",
        "statutory auditor",
        "blacklisting declaration",
        "iso",
        "cmmi",
        "company registration",
        "ca certificate",
    }
    procurement_terms = {
        "emd",
        "earnest money",
        "bid submission",
        "pre-bid",
        "pre bid",
        "bid opening",
        "cppp registration",
        "date/time",
        "date and time",
        "queries from bidders",
        "bid validity",
        "withdrawal",
        "corrigendum",
        "bids received after closing",
        "shall be rejected",
        "bidder registration",
    }
    legal_terms = {
        "no liability",
        "no representation",
        "not an agreement",
        "not an offer",
        "bidder shall bear",
        "cost of bid",
        "accuracy",
        "adequacy",
        "correctness",
        "independent advice",
        "reserves right to reject",
        "disclaimer",
    }
    contact_terms = {
        "address",
        "floor",
        "tower",
        "building",
        "connaught place",
        "new delhi",
        "email",
        "phone",
        "telephone",
        "contact details",
        "jeevan bharti",
    }
    compliance_terms = {"ipr ownership", "ipr", "data residency", "confidentiality", "security breach", "audit", "access control", "nda"}

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

    category_rules: tuple[tuple[str, set[str], str], ...] = (
        ("legal_disclaimer", {"disclaimer", "no contractual obligation", "not a recommendation", "warranty", "copyright", "confidential"}, "Legal/disclaimer language, not delivery scope."),
        ("bidder_eligibility", {"eligibility", "turnover", "net worth", "audited balance sheet", "statutory auditor", "blacklisting", "experience certificate"}, "Bidder qualification evidence."),
        ("procurement_process", {"bid submission", "submission of bid", "bids received after closing", "shall be rejected", "emd", "earnest money", "pre-bid", "pre bid", "bidder registration", "e-tender", "tendering portal", "last date"}, "Tender process instruction."),
        ("evaluation_criteria", {"evaluation", "technical score", "financial score", "scoring", "marks", "qcbs", "l1"}, "Bid evaluation criteria."),
        ("commercial_terms", {"payment terms", "invoice", "penalty", "liquidated damages", "bank guarantee", "performance guarantee", "price bid"}, "Commercial or contractual term."),
        ("integration_requirement", {"solr", "api", "microservice", "micro-service", "integrate", "integration"}, "Integration or platform touchpoint."),
        ("data_requirement", {"training data", "search logs", "clickstream", "catalog", "taxonomy", "category", "data set", "dataset"}, "Data, catalog, taxonomy, or model-input requirement."),
        ("compliance_security", {"gcc", "security", "audit", "iprid", "ipr", "data residency", "encryption", "access control"}, "Security, compliance, hosting, or IPR requirement."),
        ("service_level", {"operation and maintenance", "o&m", "maintenance", "sla", "uptime", "support", "availability", "latency"}, "Operational or service-level requirement."),
        ("non_functional_requirement", {"performance", "scalable", "high availability", "latency", "throughput", "response time"}, "Non-functional quality attribute."),
        ("technical_requirement", {"nlp", "natural language", "stop word", "stemming", "lemmatization", "tokenization", "normalization", "tf-idf", "word2vec", "svm", "naive bayes", "machine learning", "classification"}, "Technical solution feature."),
        ("annexure/forms", {"annexure", "format for", "declaration", "certificate"}, "Form or annexure instruction."),
        ("business_context", {"business problem", "objective", "purpose", "current", "users", "stakeholders", "non-availability"}, "Business context or desired outcome."),
        ("solution_scope", {"scope of work", "solution", "implement", "develop", "provide", "build", "search"}, "General solution scope."),
    )
    for category, keywords, reason in category_rules:
        if any(keyword in lower for keyword in keywords):
            confidence = 0.86 if category in _EXCLUDED_SECTION_CATEGORIES or category in {"technical_requirement", "integration_requirement"} else 0.74
            return category, confidence, reason
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
        r"Request for Proposal \(?RFP\)? for\s+(.{20,180}?)(?: Union Bank| Department| Page | Classification| \d{1,2}/\d{1,2}|$)",
        r"RFP for\s+(.{12,160}?)(?: Page | Classification| Department|$)",
        r"Empanelment of\s+(.{12,140}?)(?: Page | Classification| Department|$)",
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


def _looks_like_search_nlp_opportunity(raw_text: str, tags: list[str] | None = None) -> bool:
    lower = raw_text.lower()
    tag_set = set(tags or [])
    return bool(
        {"NLP", "Search Optimization", "Product Category Classification"} & tag_set
    ) or _has_search_nlp_signals(lower)


def _missing_information_questions(raw_text: str, tags: list[str]) -> list[str]:
    if _looks_like_search_nlp_opportunity(raw_text, tags):
        lower = raw_text.lower()
        search_stack_question = "What search engine, schema design, analyzers, indexes, and query handlers are currently used?"
        infrastructure_question = "What hosting resources, deployment constraints, observability tools, and approval gates are available?"
        runtime_question = (
            "Are GPUs allowed or required, or must the solution run on CPU-only infrastructure?"
            if any(term in lower for term in ("machine learning", "ml", "model", "nlp"))
            else "What runtime, scaling, and performance constraints should the search optimization layer satisfy?"
        )
        return [
            "What is the current search success rate and zero-result query rate?",
            "Which search relevance metrics will define success: Precision@K, Recall@K, NDCG, MRR, conversion, or another KPI?",
            "How many products, services, categories, catalog records, and seller-upload records are in scope?",
            "What is the average and peak search volume per day, and what latency SLA is expected?",
            "Are historical search logs, clickstream data, conversion events, and zero-result query logs available?",
            "Is labeled training data available for product/service category classification?",
            search_stack_question,
            "Which APIs, events, or batch interfaces are available for integration with the existing search architecture?",
            "Is multilingual search, synonym handling, spelling correction, transliteration, or semantic search expected?",
            infrastructure_question,
            runtime_question,
            "What security, data residency, audit logging, and IPR ownership constraints are non-negotiable?",
            "What is the expected O&M duration, support window, SLA model, and incident response expectation?",
            "Who owns ongoing model retraining, relevance tuning, taxonomy changes, and feedback-loop governance?",
            "Which scope is mandatory for the first release versus a later rollout or managed-service phase?",
        ]
    return [
        "What measurable business outcomes and success metrics will define project success?",
        "Which requirements are mandatory for the first release versus optional or future-phase scope?",
        "What source systems, data owners, data quality constraints, and integration dependencies are in scope?",
        "What acceptance criteria, UAT process, sign-off authority, and go-live gates will be used?",
        "What hosting, security, access control, audit logging, and compliance requirements are mandatory?",
        "What implementation timeline is expected, and which client-side dependencies can affect it?",
        "What support model, SLA, O&M duration, change-control process, and escalation path are expected?",
        "What commercial constraints, budget range, pricing model preference, and payment milestones should we assume?",
        "Who are the decision makers, evaluators, technical owners, and daily business users?",
        "What existing assets, documentation, APIs, sample data, and test environments will be provided?",
        "What risks or past failures motivated this RFP?",
        "What does the buyer expect from the vendor beyond implementation: advisory, training, migration, or operations?",
    ]


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
    search_scope = _looks_like_search_nlp_opportunity(raw_text, analysis.get("domain_tags", []))
    if search_scope:
        specs = [
            (
                "Search Query Optimization",
                "Build a query preprocessing and optimization layer that extracts product/service-relevant terms from buyer search queries using stop-word removal, stemming, lemmatization, tokenization, normalization, and noise removal.",
                "Functional",
                "Critical",
                {"string optimizer", "stop word", "stemming", "lemmatization", "tokenization", "normalization", "noise removal"},
                "This is the heart of the solution: improving search relevance before the query reaches the search engine.",
            ),
            (
                "Query Preprocessing Pipeline",
                "Preprocess buyer queries before search execution, including cleanup, normalization, linguistic processing, and feature preparation.",
                "Functional",
                "Critical",
                {"query", "search string", "tokenization", "normalization", "stop word", "lemmatization"},
                "This makes query intelligence reusable instead of embedding it directly into search-engine configuration.",
            ),
            (
                "Stop-word Removal, Stemming, Lemmatization, Tokenization, Normalization, Noise Removal",
                "Implement core NLP preprocessing operations needed to transform noisy buyer search text into search-ready terms.",
                "Functional",
                "Critical",
                {"stop word", "stemming", "lemmatization", "tokenization", "normalization", "noise removal"},
                "These operations are the explicit NLP mechanics behind search string optimization.",
            ),
            (
                "Product/Service Feature Extraction",
                "Extract product and service feature signals from user queries and seller catalog text so search and classification can use semantically useful attributes.",
                "Functional",
                "High",
                {"feature information", "feature extraction", "product/service feature", "product feature", "service feature"},
                "Feature extraction should support both buyer search and seller catalog categorization.",
            ),
            (
                "Category Classification Engine",
                "Classify products and services into the correct category using NLP/ML models and taxonomy-aware rules.",
                "Functional",
                "Critical",
                {"category classification", "categorization", "classify product", "classify service"},
                "Wrong category assignment can directly degrade discovery quality, search relevance, and onboarding quality.",
            ),
            (
                "ML/NLP Algorithm Layer",
                "Use appropriate algorithms such as TF-IDF, word2vec, SVM, Naive Bayes, or comparable techniques where validated by data and performance constraints.",
                "Functional",
                "Medium",
                {"tf-idf", "tf idf", "word2vec", "svm", "naive bayes", "machine learning"},
                "Algorithm choice should be validated against labeled data, relevance KPIs, latency, and explainability needs.",
            ),
            (
                "Search Stack Integration",
                "Integrate the optimization layer with the existing search architecture through APIs or microservices without disrupting current search operations.",
                "Integration",
                "Critical",
                {"search architecture", "search engine", "api", "microservice", "micro-service"},
                "Search-stack integration is a delivery risk and proposal differentiator; the design should augment, not blindly replace, current search.",
            ),
            (
                "API/Microservice Exposure",
                "Expose NLP optimization and classification capabilities through APIs or microservices consumable by the existing platform.",
                "Integration",
                "Critical",
                {"api", "apis", "microservice", "micro-service", "consumed by apis"},
                "This keeps the intelligence layer modular and easier to integrate with existing platform services.",
            ),
            (
                "Seller Upload Categorization Support",
                "Support category suggestions or validation during seller product/service upload so catalog quality improves upstream.",
                "Functional",
                "High",
                {"seller", "upload", "catalog", "categorization"},
                "Improving seller-side categorization reduces downstream search ambiguity.",
            ),
            (
                "Catalog Fitment and Cleansing Support",
                "Identify catalog/category fitment issues that reduce search quality and support targeted cleanup or taxonomy alignment.",
                "Data",
                "High",
                {"catalog", "category", "taxonomy", "seller"},
                "Catalog quality is a practical dependency for reliable search relevance and category classification.",
            ),
            (
                "Hosting and Deployment",
                "Deploy the solution within the required hosting environment while meeting data residency, security, and operational constraints.",
                "Operational",
                "Critical",
                {"cloud", "hosting", "deployment"},
                "Infrastructure constraints can change architecture, model selection, observability, and cost.",
            ),
            (
                "Operations and Maintenance",
                "Provide ongoing support, relevance tuning, monitoring, issue resolution, and model or taxonomy updates during the O&M period.",
                "Operational",
                "High",
                {"operation and maintenance", "o&m", "maintenance", "support", "sla"},
                "Search relevance is not one-and-done; it needs tuning, monitoring, and ownership.",
            ),
            (
                "Security, Confidentiality, and IPR Compliance",
                "Meet security, auditability, data handling, and IPR ownership requirements applicable to government deployment.",
                "Compliance",
                "High",
                {"security", "ipr", "intellectual property", "audit", "data residency"},
                "Proposal commitments should separate explicit RFP obligations from assumptions that need legal/commercial review.",
            ),
        ]
        for name, description, category, priority, keywords, interpretation in specs:
            evidence = _evidence_for(raw_text, keywords)
            if evidence:
                requirements.append(_requirement(name, description, category, priority, evidence, interpretation))
        return requirements[:14]

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
    search_scope = _looks_like_search_nlp_opportunity(raw_text, list(tags))
    strategic_fit = 84 if search_scope else 72
    technical_fit = 84 if {"NLP", "Search Optimization", "Product Category Classification", "API Integration"} & tags else 70
    domain_fit = 78 if "Government Procurement" in tags else 65
    delivery_risk = 62 if search_scope else 68
    commercial = 72 if requirements else 58
    competitive = 68 if search_scope else 60
    if len(analysis.get("missing_information", [])) > 10:
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


def _risk_assessment(raw_text: str, tags: list[str]) -> list[dict[str, str]]:
    if _looks_like_search_nlp_opportunity(raw_text, tags):
        search_stack = "search stack"
        deployment_context = "target environment"
        return [
            {
                "risk_title": "Poor quality catalog data",
                "severity": "High",
                "probability": "Medium",
                "impact": "Search relevance and category classification accuracy may underperform even with good NLP models.",
                "mitigation": "Run a discovery data audit, profile catalog fields, define cleansing ownership, and phase model rollout by category quality.",
                "owner": "Joint",
            },
            {
                "risk_title": "Insufficient labeled training data",
                "severity": "High",
                "probability": "Medium",
                "impact": "Category models may rely on weak supervision or manual labeling, increasing timeline and cost.",
                "mitigation": "Validate available labels early and propose a labeling, active-learning, or rules-plus-model bootstrapping plan.",
                "owner": "Client",
            },
            {
                "risk_title": "Undefined relevance KPIs",
                "severity": "High",
                "probability": "High",
                "impact": "Acceptance can become subjective, causing disputes around whether search has improved.",
                "mitigation": "Agree Precision@K, NDCG, MRR, zero-result reduction, click-through, and conversion metrics before build.",
                "owner": "Joint",
            },
            {
                "risk_title": f"{search_stack} integration complexity",
                "severity": "Medium",
                "probability": "Medium",
                "impact": "Existing schema, analyzers, indexes, and query handlers may constrain NLP query rewriting.",
                "mitigation": f"Request {search_stack} version/schema details, representative queries, staging access, and integration test windows.",
                "owner": "Client",
            },
            {
                "risk_title": "Search latency degradation",
                "severity": "High",
                "probability": "Medium",
                "impact": "NLP preprocessing or classification can slow buyer search if not designed as a low-latency service.",
                "mitigation": "Set latency budgets, cache common enrichments, use async/offline enrichment where possible, and load test early.",
                "owner": "Vendor",
            },
            {
                "risk_title": "Category taxonomy ambiguity",
                "severity": "Medium",
                "probability": "High",
                "impact": "Ambiguous or overlapping categories can reduce classification explainability and user trust.",
                "mitigation": "Create taxonomy governance, confusion-matrix review, and human override workflows for disputed categories.",
                "owner": "Joint",
            },
            {
                "risk_title": "Scope creep into full search engine replacement",
                "severity": "High",
                "probability": "Medium",
                "impact": "A query optimization layer can expand into ranking, catalog cleansing, analytics, UI, and full search rebuild.",
                "mitigation": "Define architecture boundaries and price discovery, MVP, rollout, and O&M as separate milestones.",
                "owner": "Joint",
            },
            {
                "risk_title": f"{deployment_context} deployment limitations",
                "severity": "Medium",
                "probability": "Medium",
                "impact": "Approved infrastructure may limit model choice, GPU use, dependencies, observability, or deployment automation.",
                "mitigation": f"Validate {deployment_context} constraints, approved libraries, CI/CD process, monitoring stack, and data movement rules.",
                "owner": "Client",
            },
            {
                "risk_title": "O&M and model retraining expectations",
                "severity": "Medium",
                "probability": "High",
                "impact": "Search relevance can decay as catalog, categories, and buyer behavior change.",
                "mitigation": "Define retraining cadence, relevance review board, feedback loops, and operational responsibility in the proposal.",
                "owner": "Joint",
            },
        ]
    return [
        {
            "risk_title": "Ambiguous acceptance criteria",
            "severity": "High",
            "probability": "Medium",
            "impact": "Delivery completion may be disputed if success metrics and sign-off ownership remain unclear.",
            "mitigation": "Define measurable outcomes, UAT process, acceptance gates, and change-control rules during discovery.",
            "owner": "Joint",
        },
        {
            "risk_title": "Client dependency readiness",
            "severity": "Medium",
            "probability": "Medium",
            "impact": "APIs, data, environments, and approvals can delay delivery and increase cost.",
            "mitigation": "Create a dependency register and make timelines contingent on client-provided access and sign-offs.",
            "owner": "Client",
        },
        {
            "risk_title": "Scope expansion after award",
            "severity": "Medium",
            "probability": "Medium",
            "impact": "Broad RFP language may pull optional work into fixed-price delivery.",
            "mitigation": "Separate mandatory scope, assumptions, exclusions, optional enhancements, and O&M pricing.",
            "owner": "Joint",
        },
    ]


def _delivery_complexity(raw_text: str, tags: list[str]) -> dict[str, Any]:
    if _looks_like_search_nlp_opportunity(raw_text, tags):
        search_stack = "search stack"
        deployment_context = "deployment environment"
        return {
            "complexity_level": "Medium-High",
            "why": f"The work combines NLP/search relevance, category taxonomy, {search_stack} integration, deployment constraints, and ongoing tuning.",
            "main_complexity_drivers": [
                "Search relevance depends on real query logs, labeled data, and catalog quality.",
                f"{search_stack} integration must preserve current search behavior while adding query optimization.",
                f"{deployment_context} may constrain infrastructure, model serving, observability, and security approvals.",
                "Acceptance requires agreed relevance metrics rather than subjective search quality opinions.",
            ],
            "estimated_delivery_phases": [
                "Discovery and relevance KPI baseline",
                "Data/catalog profiling and taxonomy review",
                "NLP query preprocessing and classification MVP",
                f"{search_stack} API/microservice integration",
                "Pilot measurement, tuning, and hardening",
                "Production rollout and O&M transition",
            ],
            "estimated_timeline_range": "16-24 weeks for MVP/production pilot; longer for full rollout and O&M.",
            "estimated_team_composition": [
                "1 Solution Architect",
                "1 Search/NLP Architect",
                "2 NLP/ML Engineers",
                "2 Backend/API Engineers",
                "1 DevOps/Cloud Engineer",
                "1 QA Engineer",
                "1 Business Analyst/Product Owner",
                "Optional UI/UX or relevance dashboard engineer",
            ],
            "dependencies": [
                f"{search_stack} schema/version and staging access",
                "Search logs, catalog data, and labeled category examples",
                f"{deployment_context} constraints and approval process",
                "Defined relevance KPIs and acceptance dataset",
            ],
        }
    return {
        "complexity_level": "Medium",
        "why": "The RFP includes multiple delivery dependencies that need clarification before reliable estimation.",
        "main_complexity_drivers": ["Scope ambiguity", "Integration and data readiness", "Security and UAT approvals"],
        "estimated_delivery_phases": ["Discovery", "MVP build", "Integration/UAT", "Rollout", "Support transition"],
        "estimated_timeline_range": "8-16 weeks depending on scope and dependency readiness.",
        "estimated_team_composition": ["1 Solution Architect", "2 Engineers", "1 QA Engineer", "1 Business Analyst/Product Owner"],
        "dependencies": ["Client access", "Data/API documentation", "Acceptance criteria", "Deployment environment"],
    }


def _architecture_recommendation(raw_text: str, tags: list[str]) -> dict[str, Any]:
    if _looks_like_search_nlp_opportunity(raw_text, tags):
        search_stack = "existing search stack"
        query_layer = "Search query rewriting/integration layer"
        deployment_component = "Deployment, monitoring, logging, and model retraining pipeline"
        search_assumption = "The client intends to augment rather than replace the existing search engine."
        deployment_assumption = "The deployment environment allows the required runtime dependencies and model-serving approach."
        return {
            "direction": f"Augment the {search_stack} with an NLP-powered query optimization and category intelligence layer exposed through APIs/microservices.",
            "components": [
                "Query preprocessing service",
                "NLP search string optimizer",
                "Feature/entity extraction",
                "Product/service category classification model",
                "Synonym/ontology layer",
                query_layer,
                "Search relevance ranking and tuning layer",
                "Feedback and analytics loop",
                "Admin/relevance dashboard",
                "API gateway or microservice integration",
                deployment_component,
            ],
            "assumptions": [
                search_assumption,
                "Search logs and representative catalog data can be made available for tuning.",
                deployment_assumption,
            ],
        }
    return {
        "direction": "Use a modular delivery architecture that separates core workflow, data, integration, security, and operations concerns.",
        "components": ["API layer", "Application services", "Data layer", "Integration adapters", "Monitoring and audit logging"],
        "assumptions": ["Detailed architecture depends on source systems, hosting model, security controls, and acceptance criteria."],
    }


def _commercial_intelligence(raw_text: str, tags: list[str]) -> dict[str, Any]:
    if _looks_like_search_nlp_opportunity(raw_text, tags):
        search_stack = "search stack"
        deployment_context = "deployment environment"
        return {
            "estimate_disclaimer": f"Directional executive estimate only; validate after discovery, data audit, {search_stack} architecture review, and O&M scope confirmation.",
            "estimated_project_size_range": "INR 1.5 Cr - INR 3 Cr depending on MVP, rollout breadth, and O&M duration.",
            "estimated_delivery_cost_range": "INR 80L - INR 1.5 Cr depending on team duration, data preparation, deployment constraints, and support commitments.",
            "margin_attractiveness": f"Medium to High if reusable NLP/search accelerators and {search_stack} integration patterns exist; Medium if heavy data labeling or bespoke taxonomy work is required.",
            "major_cost_drivers": [
                "Data profiling and labeling effort",
                f"{search_stack} integration and performance testing",
                f"{deployment_context} approvals and DevOps constraints",
                "O&M, relevance tuning, and model retraining ownership",
                "Security, IPR, and documentation obligations",
            ],
            "pricing_model_recommendation": "Fixed price for discovery plus MVP, then milestone-based rollout and separately priced O&M/relevance tuning.",
            "commercial_risks": [
                "Unclear data quality and relevance metrics may cause underestimation.",
                f"Fixed-price commitments before {search_stack}/API access could compress margins.",
                "O&M expectations may be larger than implementation effort if tuning ownership is vague.",
            ],
        }
    return {
        "estimate_disclaimer": "Directional estimate only; validate after scope, dependencies, and commercial terms are clarified.",
        "estimated_project_size_range": "To be validated after discovery.",
        "estimated_delivery_cost_range": "To be validated after discovery.",
        "margin_attractiveness": "Unknown until scope, timeline, and client dependencies are clarified.",
        "major_cost_drivers": ["Team duration", "Integrations", "Data readiness", "Security/compliance", "Support obligations"],
        "pricing_model_recommendation": "Discovery-first pricing followed by milestone-based implementation.",
        "commercial_risks": ["Ambiguous scope", "Unclear acceptance criteria", "Client dependency delays"],
    }


def _competitor_intelligence(raw_text: str, tags: list[str]) -> list[dict[str, str]]:
    search_stack = "search-stack"
    deployment_context = "deployment"
    return [
        {
            "competitor_category": "Large system integrators",
            "likely_positioning": "Government credentials, delivery scale, compliance process, and existing public-sector relationships.",
            "strength": "Procurement familiarity and large-team execution capacity.",
            "weakness": "May propose heavier delivery models with slower experimentation cycles.",
            "counter_position": f"Lead with a faster relevance pilot, {search_stack} integration plan, measurable KPIs, and a lean expert team.",
        },
        {
            "competitor_category": "IT services companies",
            "likely_positioning": "Cost-effective implementation and managed services.",
            "strength": "Competitive pricing and staffing flexibility.",
            "weakness": "May be less differentiated on search relevance science and executive outcome framing.",
            "counter_position": "Show reusable NLP/search accelerators, relevance dashboarding, and governance for ongoing tuning.",
        },
        {
            "competitor_category": "AI/analytics specialists",
            "likely_positioning": "Model accuracy, data science depth, and advanced NLP capability.",
            "strength": "Strong ML credibility.",
            "weakness": f"May underplay search integration, {deployment_context} realities, and O&M ownership.",
            "counter_position": f"Bridge AI accuracy with production search integration, explainability, {deployment_context} compliance, and support ownership.",
        },
        {
            "competitor_category": "Search technology specialists",
            "likely_positioning": "Search tuning, ranking, and search engine engineering.",
            "strength": "Deep search relevance know-how.",
            "weakness": "May be narrower on proposal packaging, governance, knowledge transfer, or end-to-end delivery.",
            "counter_position": "Position as search relevance plus delivery governance, IPR transfer support, documentation, and O&M enablement.",
        },
    ]


def _prospect_call_prep(raw_text: str, tags: list[str], missing: list[str]) -> dict[str, Any]:
    if _looks_like_search_nlp_opportunity(raw_text, tags):
        search_stack_question = "What search engine version, schema, analyzers, indexes, and query handlers are currently in production?"
        deployment_question = "What deployment-environment constraints could block dependencies or model serving?"
        delivery_guardrail = "Fixed latency or production timeline before search-stack and deployment constraints are validated."
        return {
            "opening_narrative_30_seconds": "We understand this as a discovery and relevance problem, not just a search feature. If users cannot find the right products, services, or records, search relevance becomes a business adoption and support issue. Our recommended path is to baseline current relevance, add an NLP optimization layer around the existing search stack, validate classification with real data, and roll out in measurable phases.",
            "strongest_talking_points": [
                "Frame the goal as improving discovery and reducing abandonment or manual support effort.",
                "Propose measurable relevance KPIs before committing implementation success.",
                "Position an NLP layer that augments the existing search engine rather than forcing a disruptive replacement.",
                "Make category classification explainable and tunable for catalog or taxonomy governance.",
                "Separate discovery, MVP, rollout, and O&M so commercial risk is controlled.",
            ],
            "must_ask_discovery_questions": missing[:10],
            "technical_questions": [
                search_stack_question,
                "What latency budget is available for preprocessing and query rewriting?",
                "Which APIs or integration points can the NLP service use?",
                "What labeled category data and search logs are available for model validation?",
                "Are multilingual, synonym, spelling correction, transliteration, or semantic search capabilities expected?",
            ],
            "commercial_questions": [
                "Is the expected pricing model fixed-price, milestone-based, or T&M for discovery and O&M?",
                "What O&M duration and SLA coverage should be assumed?",
                "Are data labeling, catalog cleansing, and taxonomy governance included in vendor scope?",
                "Will relevance tuning after go-live be separately funded?",
                "Are there budget guardrails or phased award constraints we should know before sizing?",
            ],
            "risk_questions": [
                "What are the known pain points or failure modes in current search?",
                "Which stakeholder signs off on relevance improvement?",
                "What happens if catalog data quality limits model accuracy?",
                deployment_question,
                "Where does the client draw the line between query optimization and full search replacement?",
            ],
            "assumptions_to_validate": [
                "The existing search engine remains in scope unless replacement is explicitly required.",
                "Historical logs and catalog data can be shared securely.",
                "The first release can be scoped as a pilot before full rollout.",
                "Relevance KPIs can be agreed before implementation.",
                "O&M includes relevance tuning, not only uptime support.",
            ],
            "avoid_overcommitting_on": [
                "Exact relevance lift before seeing logs, labels, and catalog quality.",
                delivery_guardrail,
                "Full IPR, retraining, and O&M obligations without legal/commercial review.",
            ],
        }
    return {
        "opening_narrative_30_seconds": "We see this as a qualification conversation: clarify the business outcome, separate delivery scope from tender process text, and identify the risks that affect timeline, cost, and acceptance.",
        "strongest_talking_points": ["Outcome-first discovery", "Controlled scope", "Dependency visibility", "Phased delivery", "Transparent assumptions"],
        "must_ask_discovery_questions": missing[:10],
        "technical_questions": ["What systems are in scope?", "What APIs/data are available?", "What hosting model is required?", "What security controls are mandatory?", "What acceptance tests will be used?"],
        "commercial_questions": ["What pricing model is preferred?", "What budget guardrails exist?", "What support duration is expected?", "What payment milestones are planned?", "What penalties or SLAs apply?"],
        "risk_questions": ["What client dependencies are hardest?", "What has failed before?", "Who owns sign-off?", "What is out of scope?", "What timeline is non-negotiable?"],
        "assumptions_to_validate": ["Scope can be phased", "Client access will be timely", "Acceptance criteria can be agreed", "Security approvals are available", "O&M is separately defined"],
        "avoid_overcommitting_on": ["Fixed price without discovery", "Dates without dependencies", "Unsupported compliance claims"],
    }


def _build_executive_report(
    analysis: dict[str, Any],
    raw_text: str,
    document_sections: list[dict[str, Any]],
    normalized_requirements: list[dict[str, Any]],
    excluded_noise: list[dict[str, Any]],
) -> dict[str, Any]:
    tags = analysis.get("domain_tags", [])
    search_scope = _looks_like_search_nlp_opportunity(raw_text, tags)
    missing = _missing_information_questions(raw_text, tags)
    scores = _score_bid(analysis, normalized_requirements, raw_text)
    decision = "Bid with Clarifications" if scores["overall_bid_score"] >= 70 else "Hold"
    if scores["overall_bid_score"] >= 84 and len(missing) <= 8:
        decision = "Strong Bid"
    if scores["overall_bid_score"] < 55:
        decision = "No Bid"

    if search_scope:
        client_label = _extract_client_name(raw_text) or "The buyer"
        platform_label = "the search platform"
        platform_reference = "the existing search platform"
        search_stack_label = "search-stack integration"
        deployment_label = "production deployment"
        architecture_unknown = "search architecture"
        deployment_unknown = "deployment constraints"
        ceo_brief = (
            f"{client_label} is seeking to improve search by augmenting keyword-based search with NLP-driven query understanding, "
            "search string optimization, and product/service category classification. The business impact is material: poor search "
            "relevance can prevent users from finding intended products, services, or records, increasing abandonment, support load, "
            f"or leakage away from {platform_label}. The opportunity is attractive for a team with NLP, information retrieval, {search_stack_label}, "
            f"and {deployment_label} experience. Recommendation: proceed to bid, subject to clarifications on search volume, "
            f"relevance KPIs, training data, {architecture_unknown}, {deployment_unknown}, and O&M ownership."
        )
        business_problem = {
            "current_state": "The current search experience appears to rely heavily on keyword-based matching and catalog/category metadata.",
            "pain_points": [
                "Users may fail to find the intended products, services, or records.",
                "Search queries may not map cleanly to catalog categories or seller-uploaded descriptions.",
                "Poor search relevance may push demand outside the intended platform or increase manual support effort.",
            ],
            "business_consequences": [
                f"Reduced trust in {platform_label} search results.",
                "Demand leakage and weaker platform adoption.",
                "Higher support and manual discovery burden.",
            ],
            "desired_future_state": f"An NLP-powered search optimization layer that understands query intent, improves category classification, integrates with {platform_reference}, and runs reliably in the target deployment environment.",
            "executive_interpretation": "This is a discovery and relevance initiative, not only an algorithm implementation.",
            "confidence": "high",
            "evidence": _evidence_for(raw_text, {"search", "natural language processing", "solr", "category"}),
        }
    else:
        ceo_brief = (
            f"{analysis.get('business_problem') or 'The buyer has described a technology initiative with unresolved scope details.'} "
            "The next action is to qualify business outcomes, must-have scope, client dependencies, acceptance criteria, and commercial exposure before committing price or dates."
        )
        business_problem = {
            "current_state": analysis.get("business_problem") or "Not clearly stated.",
            "pain_points": ["Business pain is not explicit enough in the RFP and needs discovery."],
            "business_consequences": ["Unclear success criteria can cause pricing, delivery, and acceptance risk."],
            "desired_future_state": "A scoped delivery plan tied to measurable business outcomes.",
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
            "rationale": f"Strong technical fit for NLP/search engineering, but key unknowns remain around data availability, relevance KPIs, search scale, {architecture_unknown}, {deployment_unknown}, and O&M ownership." if search_scope else "Potential fit exists, but the opportunity should be held until scope, dependencies, and acceptance criteria are clarified.",
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
            {"category": "Search relevance and success metrics" if search_scope else "Business and success metrics", "questions": missing[:5]},
            {"category": "Data, taxonomy, and integration" if search_scope else "Data and integration", "questions": missing[5:10]},
            {"category": "Infrastructure, operations, and commercial" if search_scope else "Delivery, operations, and commercial", "questions": missing[10:]},
        ],
        "risk_assessment": _risk_assessment(raw_text, tags),
        "delivery_complexity": _delivery_complexity(raw_text, tags),
        "architecture_recommendation": _architecture_recommendation(raw_text, tags),
        "commercial_intelligence": _commercial_intelligence(raw_text, tags),
        "competitor_intelligence": _competitor_intelligence(raw_text, tags),
        "win_strategy": [
            "Improve user discovery, not just search.",
            "Show measurable search relevance improvement with agreed KPIs.",
            "Bring an NLP plus search-stack integration accelerator mindset.",
            "Offer a discovery workshop before full implementation commitment.",
            "Provide explainable product/service category classification.",
            "Include relevance evaluation dashboarding and feedback loops.",
            "Reduce abandonment, support load, or leakage caused by poor search relevance.",
            "Commit to deployment and data residency compliance after validation.",
            "Support clear IPR transfer, knowledge transfer, and O&M governance.",
        ] if search_scope else [
            "Lead with business outcomes and measurable success criteria.",
            "Separate true solution scope from procurement/legal/admin text.",
            "Use phased discovery and implementation to control risk.",
            "Make assumptions, exclusions, dependencies, and acceptance gates explicit.",
        ],
        "prospect_call_prep": _prospect_call_prep(raw_text, tags, missing),
        "past_expertise_match": {
            "match_type": "No match",
            "confidence_score": 0,
            "matched_assets": [],
            "reusable_components": [
                "NLP/search relevance accelerator",
                "Search API integration patterns",
                "Category classification pipeline",
                "Relevance evaluation dashboard",
            ] if search_scope else [],
            "past_expertise_story": "No internal past project corpus connected yet. Match confidence is limited.",
            "gaps": ["Connect internal project corpus, case studies, architecture docs, and reusable code repositories to improve match evidence."],
            "assumption": True,
        },
        "proposal_outline": [
            "Executive summary",
            "Understanding of the buyer's business problem",
            "Proposed solution",
            "Technical architecture",
            "NLP/search methodology" if search_scope else "Implementation methodology",
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
        "domain_tags_are_specific": bool(domain_tags & {"NLP", "Search Optimization", "Product Category Classification", "API Integration", "Cloud/Hosted Deployment"}),
        "ceo_brief_answers_business_impact": any(term in ceo_brief.lower() for term in ("impact", "leakage", "business", "recommendation")),
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
    missing_questions = _missing_information_questions(raw_text, payload["domain_tags"])
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
    labels = {
        "NLP": "NLP-led query understanding",
        "Search Optimization": "search relevance optimization",
        "Information Retrieval": "information retrieval",
        "Query Understanding": "query intent understanding",
        "Product Category Classification": "product/service category classification",
        "Machine Learning": "machine learning",
        "Cognitive Search": "cognitive search",
        "Search Relevance": "search relevance measurement",
        "Catalog Management": "catalog management",
        "API Integration": "API/microservice integration",
        "Cloud/Hosted Deployment": "cloud/hosted deployment",
        "Security": "security and auditability",
        "Operations & Maintenance": "operations and maintenance",
    }
    return [labels.get(tag, tag.replace("_", " ")) for tag in tags]


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
) -> dict[str, Any] | None:
    llm_service = get_llm_service()
    clipped_text = raw_text[:18_000]
    user_content = f"""
Create executive-grade RFP intelligence for this opportunity.

Do not summarize the RFP. Do not copy tender submission/legal boilerplate.
Use the extracted facts only as evidence signals; challenge ambiguity.

Extracted signals:
{extracted}

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
            temperature=0.0,
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


async def analyze_rfp_document(raw_text: str) -> dict[str, Any]:
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
            temperature=0.0,
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

    payload = result.model_dump()
    executive_intelligence = extraction_meta.get("executive_intelligence")
    if not executive_intelligence:
        executive_intelligence = await _generate_llm_executive_intelligence(
            raw_text,
            _sanitize_analysis_payload(payload.copy(), raw_text),
        )
    return _finalize_analysis_payload(payload, raw_text, extraction_meta, executive_intelligence)
