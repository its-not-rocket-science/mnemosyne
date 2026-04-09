"""Add first_seen to user_knowledge.

``first_seen`` records when a user first encountered a canonical object
via /parse.  Unlike ``last_seen`` (which is updated on every encounter),
``first_seen`` is set once on INSERT and never changed.

This enables approximate time-to-mastery computation: for mastered objects
the elapsed time from ``first_seen`` to now gives an upper bound on how
long it took the user to reach mastery.  Exact mastery timestamps require
a future ``review_events`` table.

Existing rows receive NULL (unknown first-encounter date).

Revision ID: 0003
Revises: 0002
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_knowledge",
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_knowledge", "first_seen")
