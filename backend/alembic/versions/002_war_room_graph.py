"""Add war room message/output audit tables and session metadata

Revision ID: 002_war_room_graph
Revises: 001_initial
Create Date: 2026-06-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002_war_room_graph"
down_revision: str | None = "001_initial"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "war_room_sessions",
        sa.Column("review_loops", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "war_room_sessions",
        sa.Column(
            "final_recommendations",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
        ),
    )

    op.create_table(
        "war_room_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("war_room_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent", sa.String(50), nullable=False),
        sa.Column("target_agent", sa.String(50), nullable=False, server_default="all"),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(50), nullable=False, server_default="discussion"),
        sa.Column("round_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="{}"),
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
            ["war_room_session_id"],
            ["war_room_sessions.id"],
            name="fk_war_room_messages_war_room_session_id_war_room_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_war_room_messages"),
    )
    op.create_index("ix_war_room_messages_agent", "war_room_messages", ["agent"])

    op.create_table(
        "war_room_outputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("war_room_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("output_type", sa.String(50), nullable=False),
        sa.Column("source_agent", sa.String(50), nullable=True),
        sa.Column("payload", postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default="{}"),
        sa.Column("confidence", sa.Float(), nullable=True),
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
            ["war_room_session_id"],
            ["war_room_sessions.id"],
            name="fk_war_room_outputs_war_room_session_id_war_room_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_war_room_outputs"),
    )
    op.create_index("ix_war_room_outputs_output_type", "war_room_outputs", ["output_type"])


def downgrade() -> None:
    op.drop_index("ix_war_room_outputs_output_type", table_name="war_room_outputs")
    op.drop_table("war_room_outputs")
    op.drop_index("ix_war_room_messages_agent", table_name="war_room_messages")
    op.drop_table("war_room_messages")
    op.drop_column("war_room_sessions", "final_recommendations")
    op.drop_column("war_room_sessions", "review_loops")
