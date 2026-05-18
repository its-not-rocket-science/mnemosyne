"""Add corpus_ingestions table for idempotent corpus build tracking.

Revision ID: 0013
Revises: 0012
"""
from __future__ import annotations

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS corpus_ingestions (
            id                       VARCHAR(36)   NOT NULL PRIMARY KEY,
            source_identity          VARCHAR(64)   NOT NULL,
            manifest_entry_hash      VARCHAR(64)   NOT NULL,
            raw_content_hash         VARCHAR(64),
            normalized_content_hash  VARCHAR(64),
            language                 VARCHAR(20)   NOT NULL,
            framework                VARCHAR(30)   NOT NULL,
            level                    VARCHAR(20)   NOT NULL,
            cefr_equivalent          VARCHAR(2),
            source_document_id       VARCHAR(36),
            pipeline_version         VARCHAR(20)   NOT NULL DEFAULT '1.0',
            acquired_at              TIMESTAMPTZ,
            normalized_at            TIMESTAMPTZ,
            ingested_at              TIMESTAMPTZ,
            status                   VARCHAR(20)   NOT NULL DEFAULT 'pending',
            error_message            TEXT
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_corpus_ingestions_source_identity "
        "ON corpus_ingestions(source_identity)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_corpus_ingestions_language "
        "ON corpus_ingestions(language, status)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS corpus_ingestions")
