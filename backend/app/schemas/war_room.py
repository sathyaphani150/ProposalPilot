from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WarRoomRunRequest(BaseModel):
    session_id: uuid.UUID
    call_notes: str | None = None
    user_overrides: dict[str, Any] = Field(default_factory=dict)


class WarRoomOverrideRequest(BaseModel):
    session_id: uuid.UUID
    override: dict[str, Any]


class WarRoomAgentOutput(BaseModel):
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


class WarRoomSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rfp_session_id: uuid.UUID
    status: str
    call_notes: str | None
    human_overrides: dict[str, Any]
    agent_outputs: dict[str, Any]
    matched_projects: list[Any]
    error_message: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
