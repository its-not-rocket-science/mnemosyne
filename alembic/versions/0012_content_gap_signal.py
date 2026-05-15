"""Add content_gap_signal table for tracking empty /recommend results.

Revision ID: 0012
Revises: 0011
"""
from __future__ import annotations

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS content_gap_signal (
            id                VARCHAR(36)   NOT NULL PRIMARY KEY,
            language          VARCHAR(20)   NOT NULL,
            user_id           VARCHAR(50)   NOT NULL,
            has_parsed_texts  BOOLEAN       NOT NULL DEFAULT FALSE,
            requested_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_content_gap_signal_language "
        "ON content_gap_signal(language, requested_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS content_gap_signal")
