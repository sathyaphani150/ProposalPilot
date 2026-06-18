"""
Shared RFP taxonomy and signal rules.

These values are product configuration for source-grounded extraction, not
business logic. Keeping them here makes the RFP engine easier to review and
lets us expand domain coverage without burying keyword tables in workflow code.
"""
from __future__ import annotations

from dataclasses import dataclass


CAPABILITY_TAG_KEYWORDS: dict[str, frozenset[str]] = {
    "NLP": frozenset({"nlp", "natural language processing", "lemmatization", "stemming", "tokenization"}),
    "Search Optimization": frozenset({"search optimization", "string optimizer", "search string", "search relevance", "search result"}),
    "Information Retrieval": frozenset({"information retrieval", "tf-idf", "tf idf", "ranking", "retrieval"}),
    "Query Understanding": frozenset({"query intent", "query understanding", "user query", "search query"}),
    "Product Category Classification": frozenset({"category classification", "categorization", "classify product", "classify service"}),
    "Machine Learning": frozenset({"machine learning", "ml algorithm", "word2vec", "svm", "naive bayes", "model training"}),
    "Cognitive Search": frozenset({"cognitive search", "semantic search", "intelligent search"}),
    "Search Relevance": frozenset({"relevance", "precision", "recall", "ndcg", "mrr"}),
    "Catalog Management": frozenset({"catalog", "product catalog", "service catalog", "seller upload"}),
    "API Integration": frozenset({"api", "apis", "microservice", "micro-service", "integration", "integrate"}),
    "Cloud/Hosted Deployment": frozenset({"cloud", "deployment", "hosting"}),
    "Security": frozenset({"security", "privacy", "encryption", "audit", "access control", "sso"}),
    "Operations & Maintenance": frozenset({"operation and maintenance", "o&m", "maintenance", "sla", "support"}),
}

CAPABILITY_LABELS: dict[str, str] = {
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

SECTION_CATEGORIES: tuple[str, ...] = (
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

EXCLUDED_SECTION_CATEGORIES: frozenset[str] = frozenset(
    {
        "bidder_eligibility",
        "procurement_process",
        "legal_disclaimer",
        "commercial_terms",
        "annexure/forms",
        "buyer_contact_or_location",
        "evaluation_criteria",
        "irrelevant_noise",
    }
)

TRUST_GATE_NOISE_TERMS: frozenset[str] = frozenset(
    {
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
)

TECHNICAL_SIGNAL_TERMS: frozenset[str] = frozenset(
    {
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
)

INTEGRATION_SIGNAL_TERMS: frozenset[str] = frozenset(
    {
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
)

INFRA_OPERATIONAL_SIGNAL_TERMS: frozenset[str] = frozenset(
    {
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
)

ADMIN_TERMS: frozenset[str] = frozenset(
    {
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
)

DELIVERY_TERMS: frozenset[str] = frozenset(
    {
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
)

PUBLIC_RESPONSE_NOISE_TERMS: frozenset[str] = frozenset(
    {
        "audited balance sheet",
        "audited books",
        "balance sheet",
        "statutory auditor",
        "turnover",
        "net worth",
        "certificate of incorporation",
        "blacklisting",
        "blacklisted",
        "earnest money",
        "emd",
        "pre-bid",
        "pre bid",
        "bid submission",
        "bid opening",
        "date/time",
        "last date",
        "cppp",
        "e-tender",
        "tendering portal",
        "bidder registration",
        "annexure",
        "bid-security",
        "bank guarantee",
        "technical score",
        "financial score",
        "evaluated bid",
        "bid price",
        "no liability",
        "no representation",
        "not an agreement",
        "not an offer",
        "bidder shall bear",
        "cost of bid",
        "independent advice",
        "reserves right to reject",
        "contact details",
        "copy of the audited",
        "copy of audited",
        "this rfp document includes statements",
        "this rfp document may not be appropriate",
    }
)

LOW_VALUE_PUBLIC_PHRASES: frozenset[str] = frozenset(
    {
        "delivery-capacity",
        "delivery capacity and improve an operating capability",
        "only resource supply or a broader delivery-capacity",
        "strategic operating improvement or only a compliant vendor response",
    }
)

RFP_SIGNAL_CATEGORY_KEYWORDS: dict[str, frozenset[str]] = {
    "functional": frozenset(
        {
            "application",
            "module",
            "portal",
            "workflow",
            "dashboard",
            "service",
            "feature",
            "system",
            "development",
            "customization",
            "enhancement",
            "search",
            "mobile",
            "interface",
        }
    ),
    "integration": frozenset(
        {
            "api",
            "apis",
            "integration",
            "integrate",
            "interface",
            "web service",
            "microservice",
            "external",
            "third party",
            "source system",
            "etl",
            "sync",
        }
    ),
    "data": frozenset(
        {
            "data",
            "database",
            "migration",
            "record",
            "report",
            "analytics",
            "dashboard",
            "repository",
            "catalog",
            "taxonomy",
            "source code",
            "storage",
            "etl",
        }
    ),
    "control": frozenset(
        {
            "security",
            "audit",
            "compliance",
            "privacy",
            "encryption",
            "access",
            "performance",
            "availability",
            "hosting",
            "warranty",
            "maintenance",
            "support",
            "sla",
            "gigw",
            "clearance",
        }
    ),
    "timeline": frozenset(
        {
            "timeline",
            "milestone",
            "schedule",
            "deliverable",
            "deadline",
            "duration",
            "days",
            "weeks",
            "payment milestone",
            "go-live",
            "uat",
        }
    ),
    "scope": frozenset(
        {
            "scope",
            "support",
            "maintenance",
            "operation",
            "o&m",
            "hosting",
            "management",
            "warranty",
            "services",
        }
    ),
}

GENERIC_SIGNAL_TERMS: frozenset[str] = frozenset(
    {
        "request for proposal",
        "rfp document",
        "inter changing terms",
        "instructions for submission",
        "date of issuance",
        "date time of opening",
        "time schedule for tendering",
        "miscellaneous documents",
        "release issue of rfp document",
    }
)

EVIDENCE_STOPWORDS: frozenset[str] = frozenset(
    {
        "application",
        "system",
        "service",
        "services",
        "development",
        "software",
        "management",
        "support",
        "project",
        "platform",
        "portal",
        "data",
        "integration",
        "api",
        "apis",
        "cloud",
        "security",
        "document",
        "documents",
        "current",
        "complete",
        "additional",
        "resources",
        "requires",
        "process",
        "environment",
        "build",
        "testing",
        "validation",
    }
)

SECTION_CLASSIFIER_TERMS: dict[str, frozenset[str]] = {
    "eligibility": frozenset(
        {
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
    ),
    "procurement": frozenset(
        {
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
    ),
    "legal": frozenset(
        {
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
    ),
    "contact": frozenset(
        {
            "address",
            "floor",
            "tower",
            "building",
            "email",
            "phone",
            "telephone",
            "contact details",
        }
    ),
    "compliance": frozenset({"ipr ownership", "ipr", "data residency", "confidentiality", "security breach", "audit", "access control", "nda"}),
}


@dataclass(frozen=True)
class SectionCategoryRule:
    category: str
    keywords: frozenset[str]
    reason: str


SECTION_CATEGORY_RULES: tuple[SectionCategoryRule, ...] = (
    SectionCategoryRule("legal_disclaimer", frozenset({"disclaimer", "no contractual obligation", "not a recommendation", "warranty", "copyright", "confidential"}), "Legal/disclaimer language, not delivery scope."),
    SectionCategoryRule("bidder_eligibility", frozenset({"eligibility", "turnover", "net worth", "audited balance sheet", "statutory auditor", "blacklisting", "experience certificate"}), "Bidder qualification evidence."),
    SectionCategoryRule("procurement_process", frozenset({"bid submission", "submission of bid", "bids received after closing", "shall be rejected", "emd", "earnest money", "pre-bid", "pre bid", "bidder registration", "e-tender", "tendering portal", "last date"}), "Tender process instruction."),
    SectionCategoryRule("evaluation_criteria", frozenset({"evaluation", "technical score", "financial score", "scoring", "marks", "qcbs", "l1"}), "Bid evaluation criteria."),
    SectionCategoryRule("commercial_terms", frozenset({"payment terms", "invoice", "penalty", "liquidated damages", "bank guarantee", "performance guarantee", "price bid"}), "Commercial or contractual term."),
    SectionCategoryRule("integration_requirement", frozenset({"solr", "api", "microservice", "micro-service", "integrate", "integration"}), "Integration or platform touchpoint."),
    SectionCategoryRule("data_requirement", frozenset({"training data", "search logs", "clickstream", "catalog", "taxonomy", "category", "data set", "dataset"}), "Data, catalog, taxonomy, or model-input requirement."),
    SectionCategoryRule("compliance_security", frozenset({"gcc", "security", "audit", "iprid", "ipr", "data residency", "encryption", "access control"}), "Security, compliance, hosting, or IPR requirement."),
    SectionCategoryRule("service_level", frozenset({"operation and maintenance", "o&m", "maintenance", "sla", "uptime", "support", "availability", "latency"}), "Operational or service-level requirement."),
    SectionCategoryRule("non_functional_requirement", frozenset({"performance", "scalable", "high availability", "latency", "throughput", "response time"}), "Non-functional quality attribute."),
    SectionCategoryRule("technical_requirement", frozenset({"nlp", "natural language", "stop word", "stemming", "lemmatization", "tokenization", "normalization", "tf-idf", "word2vec", "svm", "naive bayes", "machine learning", "classification"}), "Technical solution feature."),
    SectionCategoryRule("annexure/forms", frozenset({"annexure", "format for", "declaration", "certificate"}), "Form or annexure instruction."),
    SectionCategoryRule("business_context", frozenset({"business problem", "objective", "purpose", "current", "users", "stakeholders", "non-availability"}), "Business context or desired outcome."),
    SectionCategoryRule("solution_scope", frozenset({"scope of work", "solution", "implement", "develop", "provide", "build", "search"}), "General solution scope."),
)
