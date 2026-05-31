"""corpus_collections, corpus_collection_items, corpus_import_log

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "corpus_collections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_corpus_collections_user_id", "corpus_collections", ["user_id"])

    op.create_table(
        "corpus_collection_items",
        sa.Column(
            "collection_id",
            sa.String(36),
            sa.ForeignKey("corpus_collections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "source_document_id",
            sa.String(36),
            sa.ForeignKey("source_documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", sa.String(50), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "corpus_import_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(50), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column("source_document_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_corpus_import_log_user_id", "corpus_import_log", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_corpus_import_log_user_id", table_name="corpus_import_log")
    op.drop_table("corpus_import_log")
    op.drop_table("corpus_collection_items")
    op.drop_index("ix_corpus_collections_user_id", table_name="corpus_collections")
    op.drop_table("corpus_collections")
