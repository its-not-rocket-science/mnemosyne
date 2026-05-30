"""Add corpus_document_notes table and content_hash to source_documents.

Revision ID: 0018
Revises: 0017
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "corpus_document_notes",
        sa.Column("user_id", sa.String(50), primary_key=True),
        sa.Column(
            "source_document_id",
            sa.String(36),
            sa.ForeignKey("source_documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("note", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "source_documents",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_source_documents_content_hash",
        "source_documents",
        ["content_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_source_documents_content_hash", table_name="source_documents")
    op.drop_column("source_documents", "content_hash")
    op.drop_table("corpus_document_notes")
