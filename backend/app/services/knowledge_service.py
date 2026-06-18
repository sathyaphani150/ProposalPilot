"""
ProposalPilot AI — Knowledge Base Ingestion Service
Handles chunking, embedding, and storing KB documents in vector & relational DBs.
"""
from __future__ import annotations

import os
import uuid
import re
from pathlib import Path
from typing import Any
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeItem
from app.services.document_parser import parse_document
from app.services.llm_service import get_llm_service
from app.services.vector_service import upsert_chunks, hybrid_search, delete_by_doc_id
from app.config import get_settings
from app.exceptions import NotFoundError

settings = get_settings()


_KNOWLEDGE_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "shall",
    "will",
    "must",
    "should",
    "project",
    "proposal",
    "document",
    "solution",
    "service",
    "services",
    "system",
    "platform",
    "case",
    "study",
    "internal",
    "knowledge",
    "base",
}


def _important_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_.+#/-]{2,}", text.lower())
    return {token for token in tokens if token not in _KNOWLEDGE_STOPWORDS and len(token) >= 4}


def _rerank_score(query: str, result: dict[str, Any]) -> float:
    haystack = " ".join(
        str(result.get(key) or "")
        for key in ("title", "project_name", "domain", "item_type", "text")
    )
    for key in ("tech_stack", "tags"):
        value = result.get(key) or []
        if isinstance(value, list):
            haystack += " " + " ".join(str(item) for item in value)

    query_tokens = _important_tokens(query)
    result_tokens = _important_tokens(haystack)
    if not query_tokens or not result_tokens:
        return 0.0

    overlap = len(query_tokens & result_tokens)
    coverage = overlap / max(len(query_tokens), 1)
    density = overlap / max(len(result_tokens), 1)
    return round(max(0.0, min((coverage * 0.65) + (density * 0.35), 1.0)), 2)


def _confidence(vector_score: float, rerank_score: float) -> float:
    return round((vector_score * 0.7) + (rerank_score * 0.3), 2)


def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:
    """
    Split text into character-based chunks with overlap.
    """
    if not text:
        return []
    
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        if end >= text_len:
            chunks.append(text[start:])
            break
            
        # Try to find a sentence boundary or double newline in the overlap window
        search_min = max(start, end - chunk_overlap)
        boundary = -1
        
        # Look for double newline
        idx = text.rfind("\n\n", search_min, end)
        if idx != -1:
            boundary = idx + 2
        else:
            # Look for single newline
            idx = text.rfind("\n", search_min, end)
            if idx != -1:
                boundary = idx + 1
            else:
                # Look for sentence boundary
                idx = text.rfind(". ", search_min, end)
                if idx != -1:
                    boundary = idx + 2
        
        if boundary != -1 and boundary > start:
            chunks.append(text[start:boundary])
            start = boundary
        else:
            chunks.append(text[start:end])
            start = end - chunk_overlap
            
    return [c.strip() for c in chunks if c.strip()]


async def create_knowledge_item(
    db: AsyncSession,
    *,
    item_type: str,
    title: str,
    description: str | None = None,
    domain: str | None = None,
    tech_stack: list[str] | None = None,
    tags: list[str] | None = None,
    extra_metadata: dict[str, Any] | None = None,
    filename: str | None = None,
    content: bytes | None = None,
) -> KnowledgeItem:
    """
    Creates a new KnowledgeItem, saves any uploaded file, and triggers background ingestion.
    """
    item_id = uuid.uuid4()
    tech_stack = tech_stack or []
    tags = tags or []
    extra_metadata = extra_metadata or {}
    file_path = None

    if filename and content:
        ext = Path(filename).suffix.lower()
        safe_filename = f"kb_{item_id}{ext}"
        # Ensure uploads directory exists
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

        # Write file contents
        import aiofiles
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

    item = KnowledgeItem(
        id=item_id,
        item_type=item_type,
        title=title,
        description=description,
        domain=domain,
        tech_stack=tech_stack,
        tags=tags,
        original_filename=filename,
        file_path=file_path,
        qdrant_collection=settings.QDRANT_COLLECTION_KB,
        chunk_count=0,
        extra_metadata=extra_metadata,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)

    try:
        point_ids, chunk_count = await process_knowledge_item(item)
        item.qdrant_point_ids = point_ids
        item.chunk_count = chunk_count
        await db.flush()
        logger.info(
            f"Created and indexed knowledge item {item.id} with {chunk_count} chunks"
        )
    except Exception as exc:
        logger.warning(
            f"Immediate indexing failed for knowledge item {item.id}; "
            f"falling back to Celery task: {exc}"
        )
        from app.tasks.ingestion_tasks import ingest_knowledge_item_task

        task = ingest_knowledge_item_task.delay(str(item.id))
        logger.info(f"Dispatched KB ingestion task {task.id} for {item.id}")

    return item


async def process_knowledge_item(item: KnowledgeItem) -> tuple[list[str], int]:
    """
    Parse document, chunk it, embed, and store in Qdrant.
    Returns (point_ids, chunk_count).
    """
    logger.info(f"Processing knowledge item {item.id} of type {item.item_type}")
    
    # 1. Get raw text
    raw_text = ""
    if item.file_path and os.path.exists(item.file_path):
        try:
            raw_text = await parse_document(item.file_path)
        except Exception as e:
            logger.error(f"Failed to parse document file {item.file_path}: {e}")
            if item.description:
                raw_text = item.description
            else:
                raise
    elif item.description:
        raw_text = item.description
    else:
        logger.warning(f"Knowledge item {item.id} has no file path or description")
        return [], 0
        
    # 2. Chunk text
    chunks = chunk_text(raw_text)
    if not chunks:
        logger.warning(f"No chunks generated for knowledge item {item.id}")
        return [], 0
        
    # 3. Generate embeddings
    llm_service = get_llm_service()
    embeddings = await llm_service.embed_texts(chunks)
    
    # 4. Store in Qdrant
    metadata = {
        "title": item.title,
        "item_type": item.item_type,
        "domain": item.domain or "unknown",
        "tech_stack": item.tech_stack,
        "tags": item.tags,
    }
    
    point_ids = await upsert_chunks(
        collection_name=item.qdrant_collection,
        chunks=chunks,
        embeddings=embeddings,
        doc_id=str(item.id),
        metadata=metadata,
    )
    
    return point_ids, len(chunks)


async def search_knowledge(
    query: str,
    *,
    domain: str | None = None,
    item_type: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Perform hybrid search in the knowledge base.
    """
    llm_service = get_llm_service()
    query_vector = await llm_service.embed_query(query)

    filters = {}
    if domain:
        filters["domain"] = domain
    if item_type:
        filters["item_type"] = item_type

    results = await hybrid_search(
        collection_name=settings.QDRANT_COLLECTION_KB,
        query_vector=query_vector,
        query_text=query,
        top_k=limit,
        filters=filters if filters else None,
    )
    enriched_results: list[dict[str, Any]] = []
    for result in results:
        vector_score = round(float(result.get("score") or 0.0), 2)
        rerank_score = _rerank_score(query, result)
        confidence = _confidence(vector_score, rerank_score)
        project_name = str(result.get("title") or result.get("project_name") or "Internal knowledge item").strip()
        enriched_results.append(
            {
                **result,
                "project_name": project_name,
                "vector_score": vector_score,
                "rerank_score": rerank_score,
                "confidence": confidence,
                "score": vector_score,
            }
        )
    return enriched_results


async def list_items(
    db: AsyncSession, *, skip: int = 0, limit: int = 20
) -> tuple[list[KnowledgeItem], int]:
    """List all knowledge base items from database."""
    total_result = await db.execute(select(func.count(KnowledgeItem.id)))
    total = total_result.scalar_one()

    result = await db.execute(
        select(KnowledgeItem)
        .order_by(KnowledgeItem.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = list(result.scalars().all())
    return items, total


async def get_item_or_404(db: AsyncSession, item_id: uuid.UUID) -> KnowledgeItem:
    """Fetch knowledge item by ID or raise 404."""
    result = await db.execute(select(KnowledgeItem).where(KnowledgeItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundError(f"Knowledge item {item_id} not found.")
    return item


async def delete_knowledge_item(db: AsyncSession, item_id: uuid.UUID) -> None:
    """Delete a knowledge item and its vectors in Qdrant."""
    item = await get_item_or_404(db, item_id)

    # Delete from Qdrant
    try:
        await delete_by_doc_id(item.qdrant_collection, str(item_id))
    except Exception as e:
        logger.error(f"Failed to delete Qdrant vectors for {item_id}: {e}")

    # Remove file from disk
    if item.file_path and Path(item.file_path).exists():
        try:
            Path(item.file_path).unlink()
        except Exception as e:
            logger.warning(f"Could not delete file {item.file_path}: {e}")

    await db.delete(item)
    logger.info(f"Deleted knowledge item {item_id}")
