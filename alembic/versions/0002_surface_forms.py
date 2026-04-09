"""Add surface_forms to canonical_objects.

``surface_forms`` is a JSON array that accumulates every distinct
inflected surface form ever seen for a canonical object.  For example,
the canonical vocabulary object for "gato" grows its list as the user
encounters "gato", "gatos", "gata", "gatas" across different texts.

This is the only schema change in this revision; no data migration is
required — existing rows start with an empty array.

Revision ID: 0002
Revises: 0001
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "canonical_objects",
        sa.Column(
            "surface_forms",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("canonical_objects", "surface_forms")
