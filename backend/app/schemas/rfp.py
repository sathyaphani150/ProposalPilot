"""
ProposalPilot AI — RFP Pydantic Schemas
Request/Response models for RFP sessions and analysis.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RFPSessionCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    client_name: str | None = Field(default=None, max_length=255)


class RFPSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    client_name: str | None
    status: str
    original_filename: str
    file_size_bytes: int
    created_at: datetime
    updated_at: datetime


class RFPSessionListResponse(BaseModel):
    items: list[RFPSessionResponse]
    total: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class RFPAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    business_problem: str | None
    functional_requirements: list[Any]
    non_functional_requirements: list[Any]
    data_needs: list[Any]
    integration_needs: list[Any]
    compliance_needs: list[Any]
    timeline_risks: list[Any]
    missing_information: list[Any]
    scope_boundaries: list[Any]
    domain_tags: list[str]
    estimated_complexity: str | None
    created_at: datetime
