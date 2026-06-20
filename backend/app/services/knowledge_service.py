"""
ProposalPilot AI — Knowledge Base Ingestion Service
Handles chunking, embedding, and storing KB documents in vector & relational DBs.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeItem
from app.database import AsyncSessionLocal
from app.services.document_parser import parse_document
from app.services.llm_service import get_llm_service
from app.services.vector_service import upsert_chunks, hybrid_search, delete_by_doc_id
from app.config import get_settings
from app.exceptions import NotFoundError

settings = get_settings()

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9.+#/-]*")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "for",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "using",
    "with",
}


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
        await db.refresh(item)
        logger.info(
            f"Created and indexed knowledge item {item.id} with {chunk_count} chunks"
        )
    except Exception as exc:
        item.qdrant_point_ids = []
        item.chunk_count = await estimate_chunk_count(item)
        await db.flush()
        await db.refresh(item)
        logger.warning(
            f"Knowledge item {item.id} was saved, but vector indexing failed. "
            f"Database keyword search will remain available. Reason: {exc}"
        )

    return item


async def extract_knowledge_text(item: KnowledgeItem) -> str:
    """Return the searchable source text for a knowledge item."""
    if item.file_path and os.path.exists(item.file_path):
        try:
            return await parse_document(item.file_path)
        except Exception as e:
            logger.error(f"Failed to parse document file {item.file_path}: {e}")
            if item.description:
                return item.description
            raise

    return item.description or ""


async def estimate_chunk_count(item: KnowledgeItem) -> int:
    """Best-effort chunk count used when vector indexing is unavailable."""
    try:
        return len(chunk_text(await extract_knowledge_text(item)))
    except Exception:
        return 0


async def process_knowledge_item(item: KnowledgeItem) -> tuple[list[str], int]:
    """
    Parse document, chunk it, embed, and store in Qdrant.
    Returns (point_ids, chunk_count).
    """
    logger.info(f"Processing knowledge item {item.id} of type {item.item_type}")
    
    # 1. Get raw text
    raw_text = await extract_knowledge_text(item)
    if not raw_text:
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
    db: AsyncSession | None = None,
) -> list[dict[str, Any]]:
    """
    Perform resilient KB search.

    Vector retrieval is preferred when available, but database lexical search is
    always merged in so newly ingested records remain searchable even if Qdrant,
    embeddings, or Celery are unavailable during a demo.
    """
    vector_results: list[dict[str, Any]] = []

    try:
        llm_service = get_llm_service()
        query_vector = await llm_service.embed_query(query)

        filters = {}
        if domain:
            filters["domain"] = domain
        if item_type:
            filters["item_type"] = item_type

        vector_results = await hybrid_search(
            collection_name=settings.QDRANT_COLLECTION_KB,
            query_vector=query_vector,
            query_text=query,
            top_k=limit,
            filters=filters if filters else None,
        )
    except Exception as exc:
        logger.warning(f"Vector KB search unavailable; using database search fallback: {exc}")

    if db is not None:
        db_results = await keyword_search_knowledge_items(
            db,
            query=query,
            domain=domain,
            item_type=item_type,
            limit=limit,
        )
    else:
        async with AsyncSessionLocal() as temp_db:
            db_results = await keyword_search_knowledge_items(
                temp_db,
                query=query,
                domain=domain,
                item_type=item_type,
                limit=limit,
            )

    return _merge_search_results(vector_results, db_results, limit)


async def keyword_search_knowledge_items(
    db: AsyncSession,
    *,
    query: str,
    domain: str | None = None,
    item_type: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Deterministic metadata/content search over saved KB records."""
    stmt = select(KnowledgeItem).where(KnowledgeItem.is_active.is_(True))
    if domain:
        stmt = stmt.where(KnowledgeItem.domain == domain)
    if item_type:
        stmt = stmt.where(KnowledgeItem.item_type == item_type)

    result = await db.execute(stmt.order_by(KnowledgeItem.created_at.desc()).limit(500))
    scored: list[tuple[float, KnowledgeItem]] = []
    for item in result.scalars().all():
        score = _score_knowledge_item(item, query)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [_knowledge_item_to_search_result(item, score) for score, item in scored[:limit]]


def _tokenize(text: str) -> list[str]:
    tokens = [match.group(0) for match in TOKEN_RE.finditer(text.lower())]
    return [token for token in tokens if token not in STOP_WORDS]


def _metadata_text(item: KnowledgeItem) -> str:
    values: list[str] = []
    metadata = item.extra_metadata or {}
    for value in metadata.values():
        if isinstance(value, (str, int, float)):
            values.append(str(value))
        elif isinstance(value, list):
            values.extend(str(entry) for entry in value if isinstance(entry, (str, int, float)))
    return " ".join(values)


def _score_knowledge_item(item: KnowledgeItem, query: str) -> float:
    tokens = _tokenize(query)
    if not tokens:
        return 0.0

    fields = [
        (item.title or "", 1.0),
        (" ".join(item.tech_stack or []), 0.9),
        (" ".join(item.tags or []), 0.9),
        (item.domain or "", 0.7),
        (item.item_type or "", 0.45),
        (item.description or "", 0.7),
        (_metadata_text(item), 0.5),
        (item.original_filename or "", 0.35),
    ]
    lowered_fields = [(text.lower(), weight) for text, weight in fields if text]

    weighted_total = 0.0
    matched_tokens = 0
    for token in tokens:
        token_weight = max(
            (weight for text, weight in lowered_fields if token in text),
            default=0.0,
        )
        if token_weight:
            matched_tokens += 1
            weighted_total += token_weight

    if matched_tokens == 0:
        return 0.0

    phrase = query.lower().strip()
    phrase_bonus = 0.0
    if phrase and item.title and phrase in item.title.lower():
        phrase_bonus += 0.2
    if phrase and item.description and phrase in item.description.lower():
        phrase_bonus += 0.15

    coverage = matched_tokens / len(tokens)
    weighted = weighted_total / len(tokens)
    return min(0.98, 0.12 + (coverage * 0.38) + (weighted * 0.36) + phrase_bonus)


def _knowledge_item_to_search_result(item: KnowledgeItem, score: float) -> dict[str, Any]:
    text = item.description or _metadata_text(item) or item.title
    if len(text) > 900:
        text = text[:897].rstrip() + "..."
    return {
        "point_id": f"db:{item.id}",
        "score": score,
        "text": text,
        "doc_id": str(item.id),
        "chunk_index": 0,
        "item_type": item.item_type,
        "title": item.title,
        "domain": item.domain,
        "tech_stack": item.tech_stack or [],
        "tags": item.tags or [],
    }


def _merge_search_results(
    vector_results: list[dict[str, Any]],
    db_results: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    for result in [*vector_results, *db_results]:
        doc_id = str(result.get("doc_id") or result.get("point_id") or "")
        if not doc_id:
            continue
        existing = merged.get(doc_id)
        if existing is None or float(result.get("score") or 0) > float(existing.get("score") or 0):
            merged[doc_id] = result

    return sorted(
        merged.values(),
        key=lambda item: float(item.get("score") or 0),
        reverse=True,
    )[:limit]


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
