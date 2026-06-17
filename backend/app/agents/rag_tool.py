# backend/app/agents/tools/rag_tool.py
"""
ProposalPilot AI — RAG Tool for Agents
Provides hybrid search capabilities to all War Room agents.
Grounds every agent response in real internal knowledge.
"""

from typing import Any, Dict, List, Optional

from loguru import logger

from app.services.llm_service import get_llm_service
from app.services.knowledge_service import search_knowledge
from app.services.vector_service import hybrid_search


async def search_rag(
    query: str,
    domain: Optional[str] = None,
    item_type: Optional[str] = None,
    limit: int = 6,
    collection: str = "internal_knowledge_base",
) -> List[Dict[str, Any]]:
    """
    Perform hybrid vector + keyword search across the knowledge base.
    Returns rich context for agents.
    """
    try:
        # Use knowledge_service wrapper (which handles embedding)
        results = await search_knowledge(
            query=query,
            domain=domain,
            item_type=item_type,
            limit=limit,
        )

        logger.info(f"RAG search for '{query[:80]}...' returned {len(results)} results")
        return results

    except Exception as e:
        logger.error(f"RAG search failed: {e}")
        # Fallback to direct hybrid search if needed
        try:
            query_vector = await get_llm_service().embed_query(query)
            return await hybrid_search(
                collection_name=collection,
                query_vector=query_vector,
                query_text=query,
                top_k=limit,
            )
        except Exception as fallback_err:
            logger.error(f"RAG fallback also failed: {fallback_err}")
            return []


async def search_similar_projects(
    rfp_analysis: Dict[str, Any],
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Specialized search for past projects matching the current RFP.
    """
    # Build a strong search query from RFP analysis
    query_parts = [
        rfp_analysis.get("business_problem", ""),
        " ".join(rfp_analysis.get("functional_requirements", [])[:3]),
        rfp_analysis.get("domain_tags", [""])[0] if rfp_analysis.get("domain_tags") else "",
    ]
    search_query = " ".join([p for p in query_parts if p]).strip()

    if not search_query:
        search_query = "past project experience case study"

    results = await search_rag(
        query=search_query,
        item_type="project",
        limit=limit,
    )
    return results


# Tool interface for LangGraph (can be bound to LLM)
RAG_TOOLS = [
    {
        "name": "search_rag",
        "description": "Search the internal knowledge base for relevant past projects, architectures, and proposals.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "domain": {"type": "string", "description": "Optional domain filter"},
                "limit": {"type": "integer", "description": "Number of results", "default": 6},
            },
            "required": ["query"],
        },
    }
]
