"""
ProposalPilot AI — Qdrant Vector Database Service
Handles collection creation, document ingestion, and hybrid search.
"""
from __future__ import annotations

import uuid
from typing import Any

from loguru import logger
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import get_settings
from app.exceptions import VectorDBError

settings = get_settings()

# ── Vector dimensions per model ────────────────────────────────────────────
VECTOR_SIZE = settings.EMBEDDING_DIMENSIONS  # 1536 for text-embedding-3-small

# ── Collection definitions ─────────────────────────────────────────────────
COLLECTIONS = {
    settings.QDRANT_COLLECTION_RFP: {
        "description": "RFP document chunks",
    },
    settings.QDRANT_COLLECTION_KB: {
        "description": "Internal knowledge base documents",
    },
    settings.QDRANT_COLLECTION_PROPOSALS: {
        "description": "Past proposal chunks",
    },
}


def _use_qdrant_https() -> bool:
    local_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "qdrant"}
    return bool(settings.QDRANT_API_KEY and settings.QDRANT_HOST.lower() not in local_hosts)


def get_qdrant_client() -> AsyncQdrantClient:
    """Returns a configured async Qdrant client. Call once per request."""
    return AsyncQdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT,
        api_key=settings.QDRANT_API_KEY or None,
        https=_use_qdrant_https(),
        timeout=30,
    )


async def initialize_qdrant_collections() -> None:
    """
    Create all required Qdrant collections on app startup.
    Skips creation if a collection already exists (idempotent).
    Each collection uses:
      - Dense vectors for semantic similarity
      - Sparse vectors (BM25) for keyword matching
      - Payload index on 'doc_id' for fast filtered queries
    """
    client = get_qdrant_client()

    for collection_name in COLLECTIONS:
        try:
            await client.get_collection(collection_name)
            logger.info(f"Qdrant collection already exists: '{collection_name}'")
        except UnexpectedResponse:
            # Collection does not exist — create it
            await client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE,
                    distance=models.Distance.COSINE,
                    on_disk=False,
                ),
                sparse_vectors_config={
                    "bm25": models.SparseVectorParams(
                        modifier=models.Modifier.IDF,
                    )
                },
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                    full_scan_threshold=10_000,
                ),
                optimizers_config=models.OptimizersConfigDiff(
                    indexing_threshold=20_000,
                ),
            )

            # Create payload index for fast filter on source doc ID
            await client.create_payload_index(
                collection_name=collection_name,
                field_name="doc_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            await client.create_payload_index(
                collection_name=collection_name,
                field_name="domain",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            logger.info(f"Created Qdrant collection: '{collection_name}'")

    await client.close()


async def upsert_chunks(
    collection_name: str,
    chunks: list[str],
    embeddings: list[list[float]],
    doc_id: str,
    metadata: dict[str, Any],
) -> list[str]:
    """
    Upsert text chunks with their embeddings into a Qdrant collection.
    Returns list of point IDs created.

    Args:
        collection_name: Target Qdrant collection.
        chunks: List of text chunks.
        embeddings: Corresponding dense embeddings (same length as chunks).
        doc_id: Source document identifier (PostgreSQL UUID as string).
        metadata: Extra payload fields (domain, title, item_type, etc.).

    Returns:
        List of string UUIDs representing the Qdrant point IDs.
    """
    if len(chunks) != len(embeddings):
        raise VectorDBError("Chunks and embeddings must have the same length.")

    client = get_qdrant_client()
    point_ids: list[str] = []

    try:
        points: list[models.PointStruct] = []
        for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            point_id = str(uuid.uuid4())
            point_ids.append(point_id)
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "doc_id": doc_id,
                        "chunk_index": i,
                        "text": chunk,
                        **metadata,
                    },
                )
            )

        # Batch upsert in chunks of 100 to avoid payload limits
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            await client.upsert(collection_name=collection_name, points=batch, wait=True)

        logger.info(
            f"Upserted {len(points)} chunks into '{collection_name}' "
            f"for doc_id={doc_id}"
        )
        return point_ids

    except Exception as e:
        logger.error(f"Qdrant upsert failed for doc_id={doc_id}: {e}")
        raise VectorDBError(f"Failed to store document vectors: {str(e)}")
    finally:
        await client.close()


async def hybrid_search(
    collection_name: str,
    query_vector: list[float],
    query_text: str,
    *,
    top_k: int = 10,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Perform hybrid search combining dense vector similarity + BM25 sparse search.
    Results are fused using Reciprocal Rank Fusion (RRF).

    Args:
        collection_name: Qdrant collection to search.
        query_vector: Dense query embedding.
        query_text: Raw query string (for BM25).
        top_k: Number of results to return.
        filters: Optional payload filter dict (e.g., {"domain": "fintech"}).

    Returns:
        List of result dicts with 'text', 'score', 'doc_id', and metadata.
    """
    client = get_qdrant_client()

    qdrant_filter: models.Filter | None = None
    if filters:
        must_conditions: list[Any] = [
            models.FieldCondition(
                key=key,
                match=models.MatchValue(value=value),
            )
            for key, value in filters.items()
            if value is not None
        ]
        if must_conditions:
            qdrant_filter = models.Filter(must=must_conditions)

    try:
        results = await client.query_points(
            collection_name=collection_name,
            prefetch=[
                # Dense vector search
                models.Prefetch(
                    query=query_vector,
                    limit=top_k * 2,
                    filter=qdrant_filter,
                ),
                # Sparse BM25 search
                models.Prefetch(
                    query=models.SparseVector(
                        indices=_text_to_sparse_indices(query_text),
                        values=_text_to_sparse_values(query_text),
                    ),
                    using="bm25",
                    limit=top_k * 2,
                    filter=qdrant_filter,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=top_k,
            with_payload=True,
        )

        output: list[dict[str, Any]] = []
        for r in results.points:
            payload = r.payload if isinstance(r.payload, dict) else {}
            output.append(
                {
                    "point_id": str(r.id),
                    "score": r.score,
                    "text": payload.get("text", ""),
                    "doc_id": payload.get("doc_id", ""),
                    "chunk_index": payload.get("chunk_index", 0),
                    **{k: v for k, v in payload.items() if k not in ("text", "chunk_index")},
                }
            )
        return output

    except Exception as e:
        logger.error(f"Hybrid search failed on '{collection_name}': {e}")
        raise VectorDBError(f"Vector search failed: {str(e)}")
    finally:
        await client.close()


async def delete_by_doc_id(collection_name: str, doc_id: str) -> None:
    """Delete all points associated with a document ID."""
    client = get_qdrant_client()
    try:
        await client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="doc_id",
                            match=models.MatchValue(value=doc_id),
                        )
                    ]
                )
            ),
        )
        logger.info(f"Deleted vectors for doc_id={doc_id} from '{collection_name}'")
    except Exception as e:
        raise VectorDBError(f"Failed to delete vectors for doc_id={doc_id}: {str(e)}")
    finally:
        await client.close()


async def check_qdrant_health() -> bool:
    """Health check — verifies Qdrant is reachable."""
    client = get_qdrant_client()
    try:
        await client.get_collections()
        return True
    except Exception as exc:
        logger.warning(f"Qdrant health check failed: {exc}")
        return False
    finally:
        await client.close()


# ── BM25 sparse vector helpers ─────────────────────────────────────────────
def _text_to_sparse_indices(text: str) -> list[int]:
    """Generate token hash indices for BM25 sparse vector."""
    import hashlib
    tokens = text.lower().split()
    seen: dict[int, None] = {}
    indices: list[int] = []
    for token in tokens:
        idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % 30_000
        if idx not in seen:
            seen[idx] = None
            indices.append(idx)
    return indices


def _text_to_sparse_values(text: str) -> list[float]:
    """Generate TF-IDF-like values for BM25 sparse vector (uniform 1.0 for hackathon)."""
    indices = _text_to_sparse_indices(text)
    return [1.0] * len(indices)
