# backend/app/models/war_room.py
"""
ProposalPilot AI — SQLAlchemy Models for War Room
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class WarRoomSession(Base):
    """War Room session model for Agentic multi-agent execution."""

    __tablename__ = "war_room_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rfp_session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("rfp_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    status = Column(String(50), nullable=False, server_default="idle")  # idle, running, complete, failed
    call_notes = Column(Text, nullable=True)
    human_overrides = Column(JSON, nullable=False, server_default="{}")
    agent_outputs = Column(JSON, nullable=False, server_default="{}")
    matched_projects = Column(JSON, nullable=False, server_default="[]")
    error_message = Column(Text, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default="now()", nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default="now()", onupdate=datetime.utcnow, nullable=False)

    # Relationships
    rfp_session = relationship("RFPSession", back_populates="war_rooms")
    proposals = relationship("Proposal", back_populates="war_room_session", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "rfp_session_id": str(self.rfp_session_id),
            "status": self.status,
            "call_notes": self.call_notes,
            "human_overrides": self.human_overrides,
            "agent_outputs": self.agent_outputs,
            "matched_projects": self.matched_projects,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at is not None else None,
        }


# Update existing RFPSession model to include relationship (add this if not present)
# In backend/app/models/rfp.py → add:
# war_rooms = relationship("WarRoomSession", back_populates="rfp_session", cascade="all, delete-orphan")
