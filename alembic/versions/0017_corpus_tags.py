"""Add corpus_document_tags table for user-defined labels.

Revision ID: 0017
Revises: 0016
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "corpus_document_tags",
        sa.Column("user_id", sa.String(50), primary_key=True),
        sa.Column(
            "source_document_id",
            sa.String(36),
            sa.ForeignKey("source_documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("tag", sa.String(50), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_corpus_document_tags_user_id",
        "corpus_document_tags",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_corpus_document_tags_user_id", table_name="corpus_document_tags")
    op.drop_table("corpus_document_tags")
