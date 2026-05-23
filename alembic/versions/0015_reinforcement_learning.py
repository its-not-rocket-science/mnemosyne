"""Add reinforcement learning tables: confusion pairs, progression stages.

Adds progression_stage to user_knowledge, wrong_answer + concept_type to
review_events, and two new tables: confusion_pairs and weakness_clusters.

Revision ID: 0015
Revises: 0014
"""
from __future__ import annotations

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extend existing tables ────────────────────────────────────────────────
    op.execute(
        "ALTER TABLE user_knowledge "
        "ADD COLUMN IF NOT EXISTS progression_stage VARCHAR(30) NOT NULL DEFAULT 'recognition'"
    )
    op.execute(
        "ALTER TABLE review_events "
        "ADD COLUMN IF NOT EXISTS wrong_answer TEXT"
    )
    op.execute(
        "ALTER TABLE review_events "
        "ADD COLUMN IF NOT EXISTS concept_type VARCHAR(30)"
    )

    # ── confusion_pairs ───────────────────────────────────────────────────────
    # Tracks which items a learner confuses with each other.
    # composite PK: (user_id, object_id, confused_with) makes upsert a PK lookup.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS confusion_pairs (
            user_id          VARCHAR(50)  NOT NULL,
            object_id        VARCHAR(36)  NOT NULL,
            confused_with    TEXT         NOT NULL,
            confusion_count  INTEGER      NOT NULL DEFAULT 1,
            last_confused_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            next_contrast_at TIMESTAMPTZ,
            PRIMARY KEY (user_id, object_id, confused_with)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_confusion_pairs_user "
        "ON confusion_pairs(user_id, last_confused_at DESC)"
    )

    # ── weakness_clusters ─────────────────────────────────────────────────────
    # Aggregated learner confusion patterns grouped by linguistic category.
    # Populated by background analysis; not written on every review.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS weakness_clusters (
            id           VARCHAR(36) NOT NULL PRIMARY KEY,
            user_id      VARCHAR(50) NOT NULL,
            language     VARCHAR(10) NOT NULL,
            cluster_type VARCHAR(50) NOT NULL,
            labels       JSONB       NOT NULL DEFAULT '[]',
            strength     REAL        NOT NULL DEFAULT 0.0,
            last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_weakness_clusters_user_lang "
        "ON weakness_clusters(user_id, language)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS weakness_clusters")
    op.execute("DROP TABLE IF EXISTS confusion_pairs")
    op.execute("ALTER TABLE review_events DROP COLUMN IF EXISTS concept_type")
    op.execute("ALTER TABLE review_events DROP COLUMN IF EXISTS wrong_answer")
    op.execute("ALTER TABLE user_knowledge DROP COLUMN IF EXISTS progression_stage")
