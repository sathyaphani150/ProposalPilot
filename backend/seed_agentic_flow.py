"""
ProposalPilot AI - Seed / Test Script for the Full Agentic Flow.

This script seeds a realistic knowledge base, creates a demo RFP session,
generates its structured analysis, runs the War Room agent graph, and
produces the final proposal record.

Usage:
    cd backend
    python seed_agentic_flow.py

Optional flags:
    --skip-knowledge   Skip knowledge base seeding
    --skip-proposal    Stop after the War Room run
    --output-json PATH Write a summary JSON file to PATH
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any

from sqlalchemy import select


BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import KnowledgeItem, RFPAnalysis, RFPSession
from app.services.knowledge_service import create_knowledge_item
from app.services.proposal_service import generate_final_proposal
from app.services.rfp_engine import analyze_rfp_document
from app.services.vector_service import initialize_qdrant_collections
from app.services.war_room_service import start_war_room
from seed_knowledge import PROJECTS


settings = get_settings()


DEMO_RFP_TITLE = "Demo: Agentic Flow Validation - Supplier Intelligence Platform"
DEMO_CLIENT_NAME = "Northstar Procurement Group"
DEMO_FILENAME = "demo_agentic_flow_rfp.txt"

DEMO_RFP_TEXT = dedent(
    """
    Northstar Procurement Group is seeking a delivery partner to design and implement a Supplier Intelligence Platform.

    The platform will help procurement teams upload vendor documents, evaluate responses, compare proposals, and
    surface reusable insights from prior bids and delivery projects. The business wants a modern, secure portal that
    can support semantic search across historical proposals, document extraction from PDF and DOCX files, and role-based
    access for internal users and external suppliers.

    Core goals:
    - Centralize vendor documents, statements of work, security questionnaires, and pricing sheets.
    - Extract structured data from uploaded documents.
    - Provide search and filtering across prior proposals and reference projects.
    - Generate executive summaries, solution recommendations, and commercial comparisons.
    - Support an audit trail for document access and review actions.
    - Expose APIs for integration with Salesforce, Microsoft 365, and an internal ERP system.

    Technical expectations:
    - Web application with a responsive UI for analysts, managers, and reviewers.
    - Secure authentication with SSO and role-based permissions.
    - REST APIs for document upload, analysis, search, and reporting.
    - Background processing for document parsing and intelligence generation.
    - Dashboard views for pipeline status, bid readiness, and approval tracking.
    - Deployment on AWS with observability, backups, and disaster recovery.

    Non-functional expectations:
    - High availability during business hours.
    - Strong security controls, logging, and auditability.
    - Ability to support 200+ internal users across multiple regions.
    - Initial rollout in 12 weeks with a phased delivery approach.

    Success criteria:
    - Faster proposal review cycles.
    - Better reuse of existing assets and prior delivery knowledge.
    - Clear commercial and technical differentiation for competitive bids.
    """
).strip()

CALL_NOTES = (
    "Discovery call: client wants a fast but credible implementation. "
    "Lead with secure document intelligence, reuse of prior delivery assets, and phased rollout."
)

HUMAN_OVERRIDES = {
    "guidance": (
        "Emphasize AWS, FastAPI, React, secure document processing, and a realistic phased delivery plan. "
        "Call out integration risk with Salesforce and the ERP system."
    )
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed and run the full agentic flow.")
    parser.add_argument(
        "--skip-knowledge",
        action="store_true",
        help="Skip seeding the sample knowledge base items.",
    )
    parser.add_argument(
        "--skip-proposal",
        action="store_true",
        help="Stop after the War Room completes and do not generate the final proposal.",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default="",
        help="Optional path to write a JSON summary of the seeded flow.",
    )
    return parser.parse_args()


def _build_test_payload() -> bytes:
    return DEMO_RFP_TEXT.encode("utf-8")


async def _seed_knowledge_base(db) -> list[KnowledgeItem]:
    existing = await db.execute(select(KnowledgeItem.title))
    existing_titles = {title for title in existing.scalars().all()}

    seeded_items: list[KnowledgeItem] = []
    for project in PROJECTS:
        if project["title"] in existing_titles:
            continue

        item = await create_knowledge_item(
            db=db,
            item_type=project["item_type"],
            title=project["title"],
            description=project["description"],
            domain=project["domain"],
            tech_stack=project["tech_stack"],
            tags=project["tags"],
            extra_metadata=project["extra_metadata"],
        )
        seeded_items.append(item)

    if seeded_items:
        await db.commit()

    return seeded_items


async def _create_demo_session(db) -> RFPSession:
    uploads_dir = Path(settings.UPLOAD_DIR)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    file_path = uploads_dir / f"{uuid.uuid4()}_{DEMO_FILENAME}"
    file_path.write_bytes(_build_test_payload())

    raw_text = DEMO_RFP_TEXT
    session = RFPSession(
        id=uuid.uuid4(),
        title=DEMO_RFP_TITLE,
        client_name=DEMO_CLIENT_NAME,
        status="uploaded",
        original_filename=DEMO_FILENAME,
        file_path=str(file_path),
        file_size_bytes=file_path.stat().st_size,
        raw_text=raw_text,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


async def _create_demo_analysis(db, session: RFPSession) -> RFPAnalysis:
    analysis_data = await analyze_rfp_document(session.raw_text or "")
    analysis = RFPAnalysis(
        session_id=session.id,
        **analysis_data,
    )
    db.add(analysis)
    session.status = "analyzed"
    await db.flush()
    await db.refresh(analysis)
    return analysis


async def _main_async(args: argparse.Namespace) -> dict[str, Any]:
    await initialize_qdrant_collections()

    async with AsyncSessionLocal() as db:
        summary: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "knowledge_items_seeded": 0,
        }

        if not args.skip_knowledge:
            seeded_items = await _seed_knowledge_base(db)
            summary["knowledge_items_seeded"] = len(seeded_items)

        session = await _create_demo_session(db)
        analysis = await _create_demo_analysis(db, session)

        war_room = await start_war_room(
            db=db,
            session_id=session.id,
            call_notes=CALL_NOTES,
            human_overrides=HUMAN_OVERRIDES,
        )

        summary.update(
            {
                "rfp_session": {
                    "id": str(session.id),
                    "title": session.title,
                    "status": session.status,
                },
                "analysis": {
                    "id": str(analysis.id),
                    "business_problem": analysis.business_problem,
                    "domain_tags": analysis.domain_tags,
                    "estimated_complexity": analysis.estimated_complexity,
                },
                "war_room": {
                    "id": str(war_room.id),
                    "status": war_room.status,
                    "agent_outputs": list((war_room.agent_outputs or {}).keys()),
                },
            }
        )

        if not args.skip_proposal:
            proposal = await generate_final_proposal(db=db, session_id=session.id)
            summary["proposal"] = {
                "id": str(proposal.id),
                "type": proposal.proposal_type,
                "version": proposal.version,
            }

        await db.commit()

        return summary


def main() -> None:
    args = _parse_args()
    summary = asyncio.run(_main_async(args))

    print("Full agentic flow seeded and executed successfully.")
    print(f"RFP session: {summary['rfp_session']['id']}")
    print(f"War Room: {summary['war_room']['id']}")
    if "proposal" in summary:
        print(f"Proposal: {summary['proposal']['id']}")
    print(f"Knowledge items seeded: {summary['knowledge_items_seeded']}")

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Summary written to: {output_path}")


if __name__ == "__main__":
    main()
