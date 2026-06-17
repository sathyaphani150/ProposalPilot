# backend/app/schemas/war_room.py
"""
ProposalPilot AI — Pydantic Schemas for War Room
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class SimilarProjectSchema(BaseModel):
    title: str
    match_type: str
    confidence_score: float
    relevance_summary: str
    reusable_assets: List[str] = Field(default_factory=list)
    doc_id: Optional[str] = None


class WarRoomSessionResponse(BaseModel):
    id: str
    rfp_session_id: str
    status: str
    call_notes: Optional[str] = None
    human_overrides: Dict[str, Any] = Field(default_factory=dict)
    agent_outputs: Dict[str, Optional[str]] = Field(default_factory=dict)
    matched_projects: List[SimilarProjectSchema] = Field(default_factory=list)
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WarRoomStartRequest(BaseModel):
    call_notes: Optional[str] = None
    human_overrides: Dict[str, Any] = Field(default_factory=dict)


class WarRoomOverrideRequest(BaseModel):
    guidance: str
    # Can be extended with more structured overrides later


# For internal use
class WarRoomSessionCreate(BaseModel):
    rfp_session_id: str
    status: str = "running"
    call_notes: Optional[str] = None
    human_overrides: Dict[str, Any] = Field(default_factory=dict)
    agent_outputs: Dict[str, Optional[str]] = Field(default_factory=dict)
    matched_projects: List[Dict[str, Any]] = Field(default_factory=list)