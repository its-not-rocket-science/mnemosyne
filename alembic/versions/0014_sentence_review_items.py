"""Add sentence_review_items and user_sentence_review tables.

Revision ID: 0014
Revises: 0013
"""
from __future__ import annotations

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sentence_review_items (
            id                VARCHAR(36)   NOT NULL PRIMARY KEY,
            sentence_id       VARCHAR(36)   NOT NULL REFERENCES sentences(id),
            language          VARCHAR(10)   NOT NULL,
            item_type         VARCHAR(30)   NOT NULL,
            prompt            TEXT          NOT NULL,
            target_span       VARCHAR(500)  NOT NULL,
            answer            TEXT          NOT NULL,
            distractors       JSONB,
            hint              TEXT,
            grammar_concept   VARCHAR(100),
            cefr_level        VARCHAR(2),
            difficulty_score  REAL,
            target_object_ids JSONB,
            created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sentence_review_items_sentence_id "
        "ON sentence_review_items(sentence_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sentence_review_items_language "
        "ON sentence_review_items(language)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_sentence_review_item "
        "ON sentence_review_items(sentence_id, item_type, target_span)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_sentence_review (
            user_id          VARCHAR(50)  NOT NULL,
            item_id          VARCHAR(36)  NOT NULL,
            fsrs_state       JSONB,
            mastery_score    REAL         NOT NULL DEFAULT 0.0,
            total_reviews    INTEGER      NOT NULL DEFAULT 0,
            due_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            last_reviewed_at TIMESTAMPTZ,
            streak           INTEGER      NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, item_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_sentence_review_due "
        "ON user_sentence_review(user_id, due_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_sentence_review_item "
        "ON user_sentence_review(item_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_sentence_review")
    op.execute("DROP TABLE IF EXISTS sentence_review_items")
