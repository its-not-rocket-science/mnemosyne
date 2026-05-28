"""Add privacy-conscious analytics: learning_events table, users.analytics_opt_out.

Creates the learning_events table for aggregate, non-identifiable session
counts and adds analytics_opt_out to the users table.

Revision ID: 0016
Revises: 0015
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("analytics_opt_out", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.create_table(
        "learning_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(50), nullable=False, index=True),
        sa.Column("event_type", sa.String(50), nullable=False, index=True),
        sa.Column("language", sa.String(10), nullable=True, index=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("learning_events")
    op.drop_column("users", "analytics_opt_out")
