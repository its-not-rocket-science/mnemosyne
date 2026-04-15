"""Add user_language_preferences table.

Stores per-user, per-language study preferences: transliteration toggle,
script variant, and lesson-mode override.  These are orthogonal to the FSRS
knowledge state — they describe how to present content, not what the user
knows.

The table is keyed on (user_id, language_code) so that each user can have
independent settings per language they study.  Rows are sparse: only
languages where the user has changed a default need a row.

Revision ID: 0004
Revises:     0003
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_language_preferences",
        sa.Column("user_id", sa.String(50), nullable=False),
        sa.Column("language_code", sa.String(10), nullable=False),
        sa.Column("show_transliteration", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("script_preference", sa.String(50), nullable=True),
        sa.Column("lesson_mode_override", sa.String(30), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("user_id", "language_code"),
    )


def downgrade() -> None:
    op.drop_table("user_language_preferences")
