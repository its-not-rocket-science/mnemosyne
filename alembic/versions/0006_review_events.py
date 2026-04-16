"""Add review_events table for per-review history.

Stores one row per review interaction: quality rating, mastery score before
and after, and the review timestamp.  Enables retention curves, study streaks,
and per-session statistics that cannot be derived from the current-state-only
``user_knowledge`` table.

Revision ID: 0006
Revises:     0005
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(50), nullable=False),
        sa.Column("object_id", sa.String, nullable=False),
        sa.Column("quality", sa.Integer, nullable=False),
        sa.Column("mastery_score_before", sa.Float, nullable=False),
        sa.Column("mastery_score_after", sa.Float, nullable=False),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_events_user_id", "review_events", ["user_id"])
    op.create_index("ix_review_events_reviewed_at", "review_events", ["reviewed_at"])


def downgrade() -> None:
    op.drop_index("ix_review_events_reviewed_at", table_name="review_events")
    op.drop_index("ix_review_events_user_id", table_name="review_events")
    op.drop_table("review_events")
