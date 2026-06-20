"""
ProposalPilot AI — SQLAlchemy ORM Models
All models inherit from Base with UUID PKs and timestamped audit fields.
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Mixins ────────────────────────────────────────────────────────────────
class TimestampMixin:
    """Adds created_at and updated_at to any model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


# ── RFP Session ───────────────────────────────────────────────────────────
class RFPSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Top-level record for each RFP engagement.
    Status flows: uploaded → analyzing → analyzed → war_room_running →
                  war_room_done → proposal_ready
    """

    __tablename__ = "rfp_sessions"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="uploaded", index=True
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    analysis: Mapped["RFPAnalysis | None"] = relationship(
        back_populates="session", uselist=False, cascade="all, delete-orphan"
    )
    war_room_sessions: Mapped[list["WarRoomSession"]] = relationship(
        back_populates="rfp_session", cascade="all, delete-orphan"
    )
    proposals: Mapped[list["Proposal"]] = relationship(
        back_populates="rfp_session", cascade="all, delete-orphan"
    )


# ── RFP Analysis ──────────────────────────────────────────────────────────
class RFPAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Structured extraction output from the RFP Understanding Engine."""

    __tablename__ = "rfp_analyses"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfp_sessions.id", ondelete="CASCADE"), nullable=False
    )

    business_problem: Mapped[str | None] = mapped_column(Text, nullable=True)
    functional_requirements: Mapped[list[Any]] = mapped_column(JSON, default=list)
    non_functional_requirements: Mapped[list[Any]] = mapped_column(JSON, default=list)
    data_needs: Mapped[list[Any]] = mapped_column(JSON, default=list)
    integration_needs: Mapped[list[Any]] = mapped_column(JSON, default=list)
    compliance_needs: Mapped[list[Any]] = mapped_column(JSON, default=list)
    timeline_risks: Mapped[list[Any]] = mapped_column(JSON, default=list)
    missing_information: Mapped[list[Any]] = mapped_column(JSON, default=list)
    scope_boundaries: Mapped[list[Any]] = mapped_column(JSON, default=list)
    domain_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    estimated_complexity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_llm_output: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # ── Relationships ─────────────────────────────────────────────────────
    session: Mapped["RFPSession"] = relationship(back_populates="analysis")

    def to_dict(self) -> dict[str, Any]:
        """Serialize analysis for API responses without exposing ORM internals."""
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "business_problem": self.business_problem,
            "functional_requirements": self.functional_requirements or [],
            "non_functional_requirements": self.non_functional_requirements or [],
            "data_needs": self.data_needs or [],
            "integration_needs": self.integration_needs or [],
            "compliance_needs": self.compliance_needs or [],
            "timeline_risks": self.timeline_risks or [],
            "missing_information": self.missing_information or [],
            "scope_boundaries": self.scope_boundaries or [],
            "domain_tags": self.domain_tags or [],
            "estimated_complexity": self.estimated_complexity,
            "raw_llm_output": self.raw_llm_output or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ── Knowledge Base Item ───────────────────────────────────────────────────
class KnowledgeItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Represents an ingested internal document (project doc, README, case study).
    Tracks both relational metadata and the Qdrant vector point IDs.
    """

    __tablename__ = "knowledge_items"

    item_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # project | repo | doc | proposal | case_study | architecture
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    tech_stack: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    original_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    qdrant_collection: Mapped[str] = mapped_column(
        String(100), nullable=False, default="internal_knowledge_base"
    )
    qdrant_point_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


# ── War Room Session ──────────────────────────────────────────────────────
class WarRoomSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Tracks a single multi-agent war room run.
    Stores all agent outputs and human overrides as JSONB.
    """

    __tablename__ = "war_room_sessions"

    rfp_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfp_sessions.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="idle", index=True
    )  # idle | running | paused | awaiting_human | complete | failed
    call_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_overrides: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    agent_outputs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    matched_projects: Mapped[list[Any]] = mapped_column(JSON, default=list)
    review_loops: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    final_recommendations: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────────────────
    rfp_session: Mapped["RFPSession"] = relationship(
        back_populates="war_room_sessions"
    )
    messages: Mapped[list["WarRoomMessage"]] = relationship(
        back_populates="war_room_session", cascade="all, delete-orphan"
    )
    outputs: Mapped[list["WarRoomOutput"]] = relationship(
        back_populates="war_room_session", cascade="all, delete-orphan"
    )
    proposals: Mapped[list["Proposal"]] = relationship(
        back_populates="war_room_session", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict[str, Any]:
        messages = self.__dict__.get("messages", []) or []
        return {
            "id": str(self.id),
            "rfp_session_id": str(self.rfp_session_id),
            "status": self.status,
            "call_notes": self.call_notes,
            "human_overrides": self.human_overrides or {},
            "agent_outputs": self.agent_outputs or {},
            "matched_projects": self.matched_projects or [],
            "review_loops": self.review_loops,
            "final_recommendations": self.final_recommendations or {},
            "discussion_log": [
                message.to_dict() for message in messages
            ],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class WarRoomMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "war_room_messages"

    war_room_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("war_room_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_agent: Mapped[str] = mapped_column(String(50), nullable=False, default="all")
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(50), nullable=False, default="discussion")
    round_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    war_room_session: Mapped["WarRoomSession"] = relationship(back_populates="messages")

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "target_agent": self.target_agent,
            "comment": self.comment,
            "message_type": self.message_type,
            "round_index": self.round_index,
            "payload": self.payload or {},
            "timestamp": self.created_at.isoformat() if self.created_at else None,
        }


class WarRoomOutput(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "war_room_outputs"

    war_room_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("war_room_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    output_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_agent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    war_room_session: Mapped["WarRoomSession"] = relationship(back_populates="outputs")


# ── Proposal ──────────────────────────────────────────────────────────────
class Proposal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Generated final proposal document.
    Content is stored as structured JSON sections.
    """

    __tablename__ = "proposals"

    rfp_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfp_sessions.id", ondelete="CASCADE"), nullable=False
    )
    war_room_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("war_room_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    proposal_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # final_proposal
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    docx_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Relationships ─────────────────────────────────────────────────────
    rfp_session: Mapped["RFPSession"] = relationship(back_populates="proposals")
    war_room_session: Mapped["WarRoomSession | None"] = relationship(
        back_populates="proposals"
    )
