"""Initial migration — create all tables

Revision ID: 001_initial
Revises: 
Create Date: 2026-06-06

This is the initial migration that creates:
  - rfp_sessions
  - rfp_analyses
  - knowledge_items
  - war_room_sessions
  - proposals
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ── rfp_sessions ─────────────────────────────────────────────────────
    op.create_table(
        "rfp_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("client_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="uploaded"),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rfp_sessions"),
    )
    op.create_index("ix_rfp_sessions_status", "rfp_sessions", ["status"])

    # ── rfp_analyses ──────────────────────────────────────────────────────
    op.create_table(
        "rfp_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_problem", sa.Text(), nullable=True),
        sa.Column("functional_requirements", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("non_functional_requirements", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("data_needs", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("integration_needs", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("compliance_needs", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("timeline_risks", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("missing_information", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("scope_boundaries", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("domain_tags", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("estimated_complexity", sa.String(50), nullable=True),
        sa.Column("raw_llm_output", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["rfp_sessions.id"],
            name="fk_rfp_analyses_session_id_rfp_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rfp_analyses"),
    )

    # ── knowledge_items ───────────────────────────────────────────────────
    op.create_table(
        "knowledge_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("tech_stack", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("tags", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("original_filename", sa.String(500), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("qdrant_collection", sa.String(100), nullable=False, server_default="internal_knowledge_base"),
        sa.Column("qdrant_point_ids", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("extra_metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_items"),
    )
    op.create_index("ix_knowledge_items_item_type", "knowledge_items", ["item_type"])
    op.create_index("ix_knowledge_items_domain", "knowledge_items", ["domain"])

    # ── war_room_sessions ─────────────────────────────────────────────────
    op.create_table(
        "war_room_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rfp_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="idle"),
        sa.Column("call_notes", sa.Text(), nullable=True),
        sa.Column("human_overrides", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="{}"),
        sa.Column("agent_outputs", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="{}"),
        sa.Column("matched_projects", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["rfp_session_id"],
            ["rfp_sessions.id"],
            name="fk_war_room_sessions_rfp_session_id_rfp_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_war_room_sessions"),
    )
    op.create_index("ix_war_room_sessions_status", "war_room_sessions", ["status"])

    # ── proposals ─────────────────────────────────────────────────────────
    op.create_table(
        "proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rfp_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("war_room_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("proposal_type", sa.String(50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="{}"),
        sa.Column("docx_path", sa.Text(), nullable=True),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["rfp_session_id"],
            ["rfp_sessions.id"],
            name="fk_proposals_rfp_session_id_rfp_sessions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["war_room_session_id"],
            ["war_room_sessions.id"],
            name="fk_proposals_war_room_session_id_war_room_sessions",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_proposals"),
    )
    op.create_index("ix_proposals_proposal_type", "proposals", ["proposal_type"])


def downgrade() -> None:
    op.drop_table("proposals")
    op.drop_table("war_room_sessions")
    op.drop_table("knowledge_items")
    op.drop_table("rfp_analyses")
    op.drop_table("rfp_sessions")
