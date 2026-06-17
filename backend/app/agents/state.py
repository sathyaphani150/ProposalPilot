# backend/app/agents/state.py
"""
ProposalPilot AI — War Room Agent State
Shared TypedDict for LangGraph multi-agent orchestration.
"""

from typing import Annotated, Any, Dict, List, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class SimilarProject(BaseModel):
    """Matched past project from RAG."""
    title: str
    match_type: str  # exact | partial | adjacent | none
    confidence_score: float
    relevance_summary: str
    reusable_assets: List[str] = Field(default_factory=list)
    doc_id: Optional[str] = None


class WarRoomState(BaseModel):
    """Main state passed between agents in the War Room graph."""
    
    # Input context (populated before graph starts)
    rfp_session_id: str
    rfp_analysis: Dict[str, Any]
    prep_pack: Optional[Dict[str, Any]] = None
    call_notes: str = ""
    human_overrides: Dict[str, Any] = Field(default_factory=dict)
    retrieved_context: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Agent outputs (built progressively)
    architect_output: Optional[str] = None
    cfo_output: Optional[str] = None
    competitor_output: Optional[str] = None
    proposal_output: Optional[str] = None
    
    # Graph control
    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list)
    next_agent: Optional[str] = None
    iteration: int = 0
    is_complete: bool = False
    error: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


# Helper for initial state creation
def create_initial_war_room_state(
    rfp_session_id: str,
    rfp_analysis: Dict[str, Any],
    prep_pack: Optional[Dict[str, Any]] = None,
    call_notes: str = "",
) -> WarRoomState:
    return WarRoomState(
        rfp_session_id=rfp_session_id,
        rfp_analysis=rfp_analysis,
        prep_pack=prep_pack,
        call_notes=call_notes,
    )