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
        "title": "LogiTrack Logistics Orchestrator",
        "item_type": "project",
        "domain": "logistics",
        "tech_stack": ["Python", "FastAPI", "Celery", "Redis", "Qdrant", "React", "Tailwind CSS", "Google Maps API"],
        "tags": ["route optimization", "vector database", "real-time tracking", "geographic search"],
        "description": (
            "LogiTrack is an enterprise-grade fleet monitoring, shipment tracking, and route optimization platform. "
            "It optimizes daily delivery schedules and warehouse allocations for a nationwide distribution company. "
            "The system leverages Qdrant vector database for hybrid geographic and semantic search of distribution points. "
            "Built with FastAPI and Celery/Redis for computing heavy optimization algorithms in the background. "
            "The frontend is a React + Tailwind CSS dashboard with Google Maps API integration. "
            "Streams live driver locations and ETA changes to clients via WebSockets and Server-Sent Events (SSE)."
        ),
        "extra_metadata": {
            "budget": "$220,000",
            "duration": "5 months",
            "team_size": 6,
            "architecture": "Event-Driven Worker Pattern",
            "margins": "58%"
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
