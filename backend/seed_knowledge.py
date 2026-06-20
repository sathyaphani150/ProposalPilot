"""
ProposalPilot AI — Seed Knowledge Base Script
Populates the database and Qdrant with realistic reference projects for RAG matching.
"""
import asyncio
import sys
import os

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import AsyncSessionLocal, engine
from app.services.knowledge_service import create_knowledge_item
from sqlalchemy import select
from app.models import KnowledgeItem

PROJECTS = [
    {
        "title": "PayGuard FinTech API Gateway",
        "item_type": "project",
        "domain": "fintech",
        "tech_stack": ["FastAPI", "PostgreSQL", "Redis", "Docker", "AWS", "Stripe", "slowapi", "asyncpg"],
        "tags": ["PCI-DSS", "payment gateway", "rate limiting", "asynchronous database"],
        "description": (
            "PayGuard is a highly secure, high-throughput API gateway designed for a leading digital bank. "
            "It handles PCI-DSS compliant payment processing, microservice routing, and user rate limiting. "
            "The backend is built with FastAPI and PostgreSQL using asyncpg for concurrent connection pooling. "
            "Redis is used for rate limiting (slowapi) and as a Celery task queue broker for transaction reconciliation. "
            "Implemented using Docker containers and deployed to AWS ECS. "
            "Security compliance features include end-to-end encryption, OAuth2 JWT authorization, and automated audit logs."
        ),
        "extra_metadata": {
            "budget": "$150,000",
            "duration": "4 months",
            "team_size": 5,
            "architecture": "Microservices Gateway",
            "margins": "62%"
        }
    },
    {
        "title": "HealthLink Patient Portal",
        "item_type": "project",
        "domain": "healthcare",
        "tech_stack": ["React", "TypeScript", "Next.js", "Python", "PostgreSQL", "FHIR API", "Azure", "MinIO"],
        "tags": ["HIPAA", "patient portal", "EHR integration", "WebSockets", "encryption"],
        "description": (
            "HealthLink is a comprehensive, HIPAA-compliant patient portal and clinical dashboard. "
            "The platform allows patients to schedule appointments, view test results, and communicate securely with physicians. "
            "Built with a Next.js (React + TypeScript) frontend and a Python FastAPI backend. "
            "Integrates directly with Electronic Health Record (EHR) databases via FHIR APIs. "
            "Uses PostgreSQL for relational data and encrypted MinIO storage for clinical document uploads. "
            "Real-time alerts and patient-doctor chat are powered by WebSockets. "
            "Features strict role-based access control (RBAC) and security audits."
        ),
        "extra_metadata": {
            "budget": "$280,000",
            "duration": "6 months",
            "team_size": 8,
            "architecture": "Hub-and-Spoke Integration",
            "margins": "55%"
        }
    },
    {
        "title": "ShopFlow E-Commerce Suite",
        "item_type": "project",
        "domain": "ecommerce",
        "tech_stack": ["React", "Tailwind CSS", "Node.js", "MongoDB", "Elasticsearch", "Redis", "AWS S3"],
        "tags": ["B2B marketplace", "multi-tenant", "search optimization", "caching"],
        "description": (
            "ShopFlow is a highly scalable B2B e-commerce marketplace suite supporting multi-tenant vendor stores. "
            "It features catalog management, inventory tracking, coupon management, and integrated billing. "
            "Frontend built on React and Tailwind CSS for a premium, fast customer experience. "
            "Backend uses Node.js with MongoDB for flexible catalog schemas and Elasticsearch for fast product searching. "
            "Redis handles session caching and cart states, while static assets are stored in AWS S3. "
            "Capable of handling 10,000 concurrent user sessions with average load times under 150ms."
        ),
        "extra_metadata": {
            "budget": "$190,000",
            "duration": "4.5 months",
            "team_size": 6,
            "architecture": "Monolithic Backend with Search Replicas",
            "margins": "60%"
        }
    },
    {
        "title": "AeroSpace Certification & Compliance Engine",
        "item_type": "project",
        "domain": "aerospace",
        "tech_stack": ["Python", "FastAPI", "SQLAlchemy", "PostgreSQL", "Alembic", "Docker", "PyMuPDF"],
        "tags": ["SOC2", "compliance matrix", "document auditing", "PDF parsing"],
        "description": (
            "AeroSpace Compliance Engine is a document tracking and compliance auditing platform for aerospace supplier certifications. "
            "It parses massive PDF manuals and certifications using PyMuPDF to construct automated compliance matrices. "
            "Maintains a detailed audit trail of all actions and certificates in PostgreSQL. "
            "The backend is built with FastAPI, SQLAlchemy, and Alembic for robust schema evolution. "
            "Designed to meet strict aerospace security standards and prepare organizations for SOC2 audits."
        ),
        "extra_metadata": {
            "budget": "$340,000",
            "duration": "8 months",
            "team_size": 10,
            "architecture": "Modular Structured Monolith",
            "margins": "50%"
        }
    },
    {
        "title": "CivicSearch NLP Procurement Discovery",
        "item_type": "project",
        "domain": "public_sector",
        "tech_stack": ["Python", "FastAPI", "Apache Solr", "spaCy", "PostgreSQL", "Redis", "React"],
        "tags": ["NLP", "search relevance", "query optimization", "taxonomy", "public procurement"],
        "description": (
            "CivicSearch improved discovery across a public procurement marketplace where buyers used inconsistent search terms. "
            "The project added query normalization, synonym expansion, stop-word handling, taxonomy-aware category classification, and Solr integration through an API layer. "
            "A relevance dashboard tracked zero-result queries, click-through, Precision@K, and category misclassification. "
            "The delivery approach separated discovery, relevance baseline, pilot rollout, and managed tuning so the client could validate impact before full deployment."
        ),
        "extra_metadata": {"budget": "$260,000", "duration": "5 months", "team_size": 7, "architecture": "NLP Search Augmentation", "margins": "57%"}
    },
    {
        "title": "GovAssist Citizen Services Workflow Platform",
        "item_type": "case_study",
        "domain": "public_sector",
        "tech_stack": ["React", "FastAPI", "PostgreSQL", "Keycloak", "Kafka", "Azure Monitor"],
        "tags": ["case management", "approval workflow", "audit trail", "citizen services"],
        "description": (
            "GovAssist replaced spreadsheet-driven citizen-service approvals with a secure workflow portal. "
            "The platform supported case intake, role-based routing, document upload, review queues, SLA tracking, audit trails, and executive dashboards. "
            "Key delivery risks were data migration quality, sign-off ownership, role mapping, and UAT acceptance criteria. "
            "The team used phased rollout and dependency registers to keep scope under control."
        ),
        "extra_metadata": {"budget": "$310,000", "duration": "7 months", "team_size": 9, "architecture": "Event-Driven Case Management", "margins": "53%"}
    },
    {
        "title": "RetailSense Catalog Intelligence Engine",
        "item_type": "project",
        "domain": "retail",
        "tech_stack": ["Python", "scikit-learn", "Elasticsearch", "Airflow", "PostgreSQL", "React"],
        "tags": ["catalog classification", "semantic search", "data quality", "ML pipeline"],
        "description": (
            "RetailSense automated product categorization and catalog quality checks for a multi-vendor retail platform. "
            "The system combined rules, TF-IDF features, supervised classification, synonym dictionaries, and manual review workflows. "
            "It reduced duplicate categories and improved product findability by using labeled product data and search analytics. "
            "Architecture included batch model training, API inference, catalog validation, and monitoring for classification drift."
        ),
        "extra_metadata": {"budget": "$180,000", "duration": "4 months", "team_size": 6, "architecture": "ML Classification Pipeline", "margins": "61%"}
    },
    {
        "title": "InsureOps Claims Triage Automation",
        "item_type": "project",
        "domain": "insurance",
        "tech_stack": ["FastAPI", "React", "PostgreSQL", "Celery", "Redis", "Azure Blob Storage", "OCR"],
        "tags": ["claims workflow", "document ingestion", "triage", "auditability"],
        "description": (
            "InsureOps digitized claims intake and triage for an insurer handling high document volume. "
            "The solution ingested claim forms, extracted metadata, routed tasks by policy type, flagged missing documents, and produced operational dashboards. "
            "Executive risks centered on OCR accuracy, policy-system integration, exception handling, audit trail completeness, and SLA reporting."
        ),
        "extra_metadata": {"budget": "$240,000", "duration": "6 months", "team_size": 8, "architecture": "Document Workflow Automation", "margins": "56%"}
    },
    {
        "title": "BankOps Customer 360 Integration Hub",
        "item_type": "architecture",
        "domain": "banking",
        "tech_stack": ["Java", "Kafka", "PostgreSQL", "Redis", "OpenAPI", "Kubernetes", "Grafana"],
        "tags": ["customer 360", "API integration", "event streaming", "data governance"],
        "description": (
            "BankOps unified customer signals from CRM, core banking, card, and support systems into a governed Customer 360 layer. "
            "The architecture used API adapters, event streams, entity resolution, consent checks, golden-record storage, and observability dashboards. "
            "The proposal separated buyer-owned data governance from vendor-owned integration implementation to avoid scope ambiguity."
        ),
        "extra_metadata": {"budget": "$420,000", "duration": "9 months", "team_size": 11, "architecture": "Integration Hub", "margins": "49%"}
    },
    {
        "title": "MedFlow Referral Management Portal",
        "item_type": "case_study",
        "domain": "healthcare",
        "tech_stack": ["Next.js", "FastAPI", "PostgreSQL", "FHIR", "Azure", "WebSockets"],
        "tags": ["referrals", "EHR integration", "HIPAA", "workflow"],
        "description": (
            "MedFlow coordinated patient referrals between clinics and specialists. "
            "The portal provided referral intake, eligibility checks, appointment coordination, secure messaging, document exchange, and status dashboards. "
            "Key assumptions validated before contract were FHIR interface readiness, patient-consent handling, EHR sandbox access, and clinical sign-off workflows."
        ),
        "extra_metadata": {"budget": "$330,000", "duration": "7 months", "team_size": 9, "architecture": "Healthcare Workflow Portal", "margins": "52%"}
    },
    {
        "title": "SmartGrid Field Service Command Center",
        "item_type": "project",
        "domain": "utilities",
        "tech_stack": ["React", "FastAPI", "PostgreSQL", "Kafka", "TimescaleDB", "Mapbox"],
        "tags": ["field service", "dispatch", "IoT telemetry", "incident response"],
        "description": (
            "SmartGrid gave a utility company a command center for outages, field crews, and asset telemetry. "
            "It combined incident intake, work order dispatch, map visualization, IoT event ingestion, SLA alerts, and executive reporting. "
            "Discovery focused on telemetry ownership, field-device reliability, offline workflows, and integration with legacy work-management systems."
        ),
        "extra_metadata": {"budget": "$390,000", "duration": "8 months", "team_size": 10, "architecture": "Operational Command Center", "margins": "51%"}
    },
    {
        "title": "EduAssess Adaptive Learning Analytics",
        "item_type": "project",
        "domain": "education",
        "tech_stack": ["Python", "Django", "React", "PostgreSQL", "Airflow", "Power BI"],
        "tags": ["learning analytics", "dashboards", "assessment", "data warehouse"],
        "description": (
            "EduAssess consolidated assessment data from multiple learning platforms into analytics dashboards for administrators and faculty. "
            "It included ingestion pipelines, learner-progress metrics, cohort segmentation, role-based dashboards, and data-quality checks. "
            "Risks included inconsistent source data, privacy constraints, stakeholder definitions of success, and report acceptance criteria."
        ),
        "extra_metadata": {"budget": "$175,000", "duration": "4 months", "team_size": 5, "architecture": "Analytics Data Mart", "margins": "59%"}
    },
    {
        "title": "MfgVision Quality Inspection AI",
        "item_type": "project",
        "domain": "manufacturing",
        "tech_stack": ["Python", "PyTorch", "FastAPI", "PostgreSQL", "Edge Runtime", "React"],
        "tags": ["computer vision", "quality inspection", "edge inference", "MLOps"],
        "description": (
            "MfgVision detected production defects from inspection images on manufacturing lines. "
            "The project covered image capture, labeling workflow, model training, edge inference, exception review, and quality dashboards. "
            "Contract guardrails separated model accuracy targets from client-owned image quality, labeling volume, and production-line access."
        ),
        "extra_metadata": {"budget": "$360,000", "duration": "8 months", "team_size": 10, "architecture": "Edge AI Inspection", "margins": "48%"}
    },
    {
        "title": "LegalDoc Contract Intelligence Workspace",
        "item_type": "case_study",
        "domain": "legal",
        "tech_stack": ["FastAPI", "React", "PostgreSQL", "Qdrant", "OCR", "LLM"],
        "tags": ["document intelligence", "semantic search", "clause extraction", "review workflow"],
        "description": (
            "LegalDoc helped legal teams search, compare, and review contract clauses across a large document corpus. "
            "It combined OCR, chunking, embeddings, metadata filters, clause extraction, reviewer workflow, and audit history. "
            "The team validated retrieval quality, sensitive-data handling, human review requirements, and defensible citation behavior before rollout."
        ),
        "extra_metadata": {"budget": "$295,000", "duration": "6 months", "team_size": 8, "architecture": "RAG Document Review", "margins": "54%"}
    },
    {
        "title": "TransitPulse Mobility Operations Dashboard",
        "item_type": "project",
        "domain": "transportation",
        "tech_stack": ["React", "Node.js", "PostgreSQL", "Kafka", "Redis", "Grafana"],
        "tags": ["real-time dashboard", "operations", "SLA monitoring", "data integration"],
        "description": (
            "TransitPulse integrated vehicle telemetry, route schedules, incident data, and passenger alerts into an operations dashboard. "
            "It supported real-time monitoring, service disruption alerts, operator workflows, and performance reporting. "
            "The project emphasized integration reliability, data freshness SLAs, escalation workflows, and observability from day one."
        ),
        "extra_metadata": {"budget": "$270,000", "duration": "5 months", "team_size": 7, "architecture": "Streaming Operations Dashboard", "margins": "55%"}
    },
    {
        "title": "EnergyBid Compliance Proposal Factory",
        "item_type": "proposal",
        "domain": "energy",
        "tech_stack": ["FastAPI", "React", "PostgreSQL", "PyMuPDF", "LLM", "Qdrant"],
        "tags": ["RFP compliance", "proposal automation", "document parsing", "knowledge retrieval"],
        "description": (
            "EnergyBid automated compliance mapping for renewable-energy RFP responses. "
            "The system parsed tender documents, extracted compliance obligations, linked evidence from previous submissions, and generated review-ready response outlines. "
            "The highest-value lesson was to separate procurement boilerplate from true delivery commitments and keep all leadership outputs evidence-grounded."
        ),
        "extra_metadata": {"budget": "$145,000", "duration": "3 months", "team_size": 5, "architecture": "RFP Intelligence Workflow", "margins": "63%"}
    },
    {
        "title": "SupplyRisk Vendor Risk Intelligence",
        "item_type": "project",
        "domain": "supply_chain",
        "tech_stack": ["Python", "FastAPI", "PostgreSQL", "Airflow", "React", "OpenSearch"],
        "tags": ["vendor risk", "risk scoring", "third-party data", "dashboards"],
        "description": (
            "SupplyRisk assessed supplier reliability using operational records, third-party risk feeds, contract data, and incident history. "
            "The product delivered risk scoring, exception queues, evidence drill-down, and executive dashboards. "
            "Commercial guardrails focused on third-party data licensing, explainability, score acceptance, and client ownership of risk policy."
        ),
        "extra_metadata": {"budget": "$225,000", "duration": "5 months", "team_size": 6, "architecture": "Risk Intelligence Platform", "margins": "58%"}
    },
    {
        "title": "TravelOps Revenue Recovery Engine",
        "item_type": "project",
        "domain": "travel",
        "tech_stack": ["Python", "FastAPI", "PostgreSQL", "Kafka", "React", "dbt"],
        "tags": ["revenue leakage", "analytics", "workflow", "exception management"],
        "description": (
            "TravelOps identified revenue leakage from booking, refund, and settlement records. "
            "The system ingested transaction feeds, matched exceptions, routed recovery tasks, and reported recovered value. "
            "The sales narrative tied technical integration directly to measurable ROI, which helped executives approve a phased pilot."
        ),
        "extra_metadata": {"budget": "$205,000", "duration": "4 months", "team_size": 6, "architecture": "Exception Analytics Workflow", "margins": "60%"}
    },
    {
        "title": "HRFlow Employee Service Desk Automation",
        "item_type": "project",
        "domain": "enterprise_hr",
        "tech_stack": ["React", "FastAPI", "PostgreSQL", "Rasa", "SSO", "ServiceNow API"],
        "tags": ["employee service", "ticket routing", "chatbot", "workflow automation"],
        "description": (
            "HRFlow automated HR service requests, knowledge lookup, and ticket routing for a large enterprise. "
            "The solution included employee self-service, intent classification, approval workflows, ServiceNow integration, SLA dashboards, and feedback loops. "
            "Discovery clarified HR policy ownership, SSO roles, escalation rules, and how chatbot confidence would be handled."
        ),
        "extra_metadata": {"budget": "$165,000", "duration": "4 months", "team_size": 5, "architecture": "Workflow plus Conversational Intake", "margins": "62%"}
    },
    {
        "title": "AgriMarket Farmer Advisory Platform",
        "item_type": "case_study",
        "domain": "agriculture",
        "tech_stack": ["Flutter", "FastAPI", "PostgreSQL", "SMS Gateway", "Weather API", "React"],
        "tags": ["advisory", "mobile app", "offline workflow", "localized content"],
        "description": (
            "AgriMarket delivered crop advisory, weather alerts, marketplace listings, and field-agent workflows for rural users. "
            "The architecture balanced mobile-first UX, offline capture, SMS fallback, content governance, and analytics. "
            "The team validated language coverage, data ownership, field adoption, and operational support assumptions early."
        ),
        "extra_metadata": {"budget": "$210,000", "duration": "6 months", "team_size": 7, "architecture": "Mobile Advisory Platform", "margins": "56%"}
    },
    {
        "title": "CyberPosture Security Evidence Portal",
        "item_type": "architecture",
        "domain": "cybersecurity",
        "tech_stack": ["React", "FastAPI", "PostgreSQL", "S3", "SIEM API", "Open Policy Agent"],
        "tags": ["security evidence", "audit", "compliance", "access control"],
        "description": (
            "CyberPosture centralized security evidence collection for audits and customer due diligence. "
            "The portal handled evidence requests, owner assignment, document storage, control mapping, SIEM evidence links, approvals, and immutable audit history. "
            "Architecture decisions focused on role-based access, evidence retention, encryption, and traceable sign-off."
        ),
        "extra_metadata": {"budget": "$235,000", "duration": "5 months", "team_size": 6, "architecture": "Secure Evidence Workflow", "margins": "57%"}
    },
    {
        "title": "FinLedger Reconciliation Control Tower",
        "item_type": "project",
        "domain": "finance",
        "tech_stack": ["Python", "FastAPI", "PostgreSQL", "Celery", "Redis", "React", "SFTP"],
        "tags": ["reconciliation", "exception workflow", "audit trail", "finance operations"],
        "description": (
            "FinLedger automated daily reconciliation between payment files, ledger entries, and settlement reports. "
            "It included file ingestion, matching rules, exception queues, approval workflow, audit history, and finance dashboards. "
            "The project de-risked delivery by validating source-file formats, reconciliation tolerances, sign-off authority, and operating support windows."
        ),
        "extra_metadata": {"budget": "$195,000", "duration": "4 months", "team_size": 6, "architecture": "Batch Reconciliation Workflow", "margins": "61%"}
    }
]


async def main():
    print("Connecting to database...")
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(KnowledgeItem.title))
        existing_titles = {title for title in result.scalars().all()}

        print("Seeding missing knowledge items...")
        for p in PROJECTS:
            if p["title"] in existing_titles:
                print(f"Skipping existing item: '{p['title']}'")
                continue
            print(f"Creating item: '{p['title']}'...")
            await create_knowledge_item(
                db=db,
                item_type=p["item_type"],
                title=p["title"],
                description=p["description"],
                domain=p["domain"],
                tech_stack=p["tech_stack"],
                tags=p["tags"],
                extra_metadata=p["extra_metadata"]
            )
        
        await db.commit()
        print("Knowledge base seed completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
