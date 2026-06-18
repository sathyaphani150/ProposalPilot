"""
ProposalPilot AI — Document Ingestion Tasks
Background Celery tasks for async RFP analysis and KB ingestion.
"""
import asyncio
from loguru import logger
from app.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="app.tasks.ingestion_tasks.analyze_rfp_task",
    max_retries=2,
    default_retry_delay=30,
    queue="ingestion",
)
def analyze_rfp_task(self, session_id: str) -> dict:
    """
    Background task: runs the RFP Understanding Engine on an uploaded document.
    Updates session status in DB when complete.
    """
    logger.info(f"[Task {self.request.id}] Starting RFP analysis for session {session_id}")

    async def _run():
        from app.database import AsyncSessionLocal, engine
        from app.models import RFPSession, RFPAnalysis
        from app.services.rfp_service import record_analysis_failure
        from app.services.rfp_engine import analyze_rfp_document
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            session: RFPSession | None = None
            try:
                # Fetch session
                result = await db.execute(
                    select(RFPSession).where(RFPSession.id == session_id)
                )
                session = result.scalar_one_or_none()
                if not session:
                    logger.error(f"Session {session_id} not found in analysis task")
                    return {"status": "error", "reason": "session_not_found"}

                if not session.raw_text:
                    await record_analysis_failure(
                        db,
                        session,
                        error_code="NO_READABLE_TEXT",
                        message=(
                            "No readable text could be extracted from the uploaded file. "
                            "Try a text-based PDF, DOCX, TXT, or MD file."
                        ),
                        detail={
                            "session_id": str(session.id),
                            "filename": session.original_filename,
                        },
                    )
                    return {"status": "error", "reason": "no_text_extracted"}

                # Run extraction
                session.status = "analyzing"
                await db.commit()

                analysis_data = await analyze_rfp_document(session.raw_text)

                existing_result = await db.execute(
                    select(RFPAnalysis).where(RFPAnalysis.session_id == session.id)
                )
                for existing in existing_result.scalars().all():
                    await db.delete(existing)
                await db.flush()

                # Save analysis
                analysis = RFPAnalysis(
                    session_id=session.id,
                    **analysis_data,
                )
                db.add(analysis)
                session.status = "analyzed"
                await db.commit()
                await db.refresh(analysis)

                logger.info(f"[Task] RFP analysis complete for session {session_id}")
                return {"status": "success", "analysis_id": str(analysis.id)}

            except Exception as e:
                logger.error(f"[Task] RFP analysis FAILED for session {session_id}: {e}")
                if session is not None:
                    try:
                        await record_analysis_failure(
                            db,
                            session,
                            error_code="ANALYSIS_FAILED",
                            message="RFP analysis failed while generating structured insights.",
                            detail=str(e),
                        )
                    except Exception:
                        pass
                raise
            finally:
                await engine.dispose()

    try:
        return asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="app.tasks.ingestion_tasks.ingest_knowledge_item_task",
    max_retries=2,
    default_retry_delay=30,
    queue="ingestion",
)
def ingest_knowledge_item_task(self, knowledge_item_id: str) -> dict:
    """
    Background task: chunk, embed, and store a knowledge base document in Qdrant.
    """
    logger.info(f"[Task] Ingesting knowledge item {knowledge_item_id}")

    async def _run():
        from app.database import AsyncSessionLocal, engine
        from app.models import KnowledgeItem
        from app.services.knowledge_service import process_knowledge_item
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(KnowledgeItem).where(KnowledgeItem.id == knowledge_item_id)
                )
                item = result.scalar_one_or_none()
                if not item:
                    return {"status": "error", "reason": "item_not_found"}

                point_ids, chunk_count = await process_knowledge_item(item)
                item.qdrant_point_ids = point_ids
                item.chunk_count = chunk_count
                await db.commit()
                return {"status": "success", "chunks": chunk_count}
            except Exception as e:
                logger.error(f"[Task] Knowledge base ingestion FAILED: {e}")
                raise
            finally:
                await engine.dispose()

    try:
        return asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
