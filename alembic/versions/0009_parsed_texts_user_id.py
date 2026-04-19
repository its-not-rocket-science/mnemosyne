"""Add user_id to parsed_texts for GDPR-compliant account deletion.

Without a user_id on parsed_texts, DELETE /users/me could not remove the
user's submitted source text.  This migration adds a nullable user_id column
so that /parse and /ingest can tag rows with their owner, and account deletion
can cascade correctly.

Existing rows get user_id = NULL (unknown owner — pre-dates auth).  They are
intentionally left in place; they carry no personally identifiable information
beyond the text content and are not associated with any live user account.

Revision ID: 0009
Revises:     0008
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "parsed_texts",
        sa.Column("user_id", sa.String(50), nullable=True),
    )
    op.create_index("ix_parsed_texts_user_id", "parsed_texts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_parsed_texts_user_id", table_name="parsed_texts")
    op.drop_column("parsed_texts", "user_id")
