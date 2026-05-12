"""Add term_progress table for per-user highlighted term tracking.

Revision ID: 0011
Revises: 0010
"""
from __future__ import annotations

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS term_progress (
            user_id           VARCHAR(50)   NOT NULL,
            language          VARCHAR(10)   NOT NULL,
            term              TEXT          NOT NULL,
            lemma             TEXT,
            first_seen        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            last_seen         TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            exposure_count    INT           NOT NULL DEFAULT 0,
            review_count      INT           NOT NULL DEFAULT 0,
            correct_count     INT           NOT NULL DEFAULT 0,
            incorrect_count   INT           NOT NULL DEFAULT 0,
            mastery_score     DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            next_review_at    TIMESTAMPTZ,
            source_lesson_ids JSON          NOT NULL DEFAULT '[]',
            PRIMARY KEY (user_id, language, term)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_term_progress_user_lang_next "
        "ON term_progress(user_id, language, next_review_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS term_progress")
