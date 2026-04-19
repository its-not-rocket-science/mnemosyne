"""Remove stale 'word not found in model vocabulary' confidence_note from canonical_objects.

lesson_data is a JSONB column populated at parse time.  Before the OOV-bypass
fix in the Spanish conjugation path, finite verb forms for known A1 lemmas
(e.g. 'dará') were tagged with confidence_note: "word not found in model
vocabulary".  Those stale notes persisted in the DB even after the plugin code
was corrected.  This migration strips the key from every affected row so
lessons served from the DB-first path show clean output.

Revision ID: 0008
Revises:     0007
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # lesson_data is stored as JSON (not JSONB), so cast to jsonb for the
    # key-removal operator (-) and cast back to json when storing.
    # Using ->>'confidence_note' IS NOT NULL instead of the jsonb ? operator
    # to avoid both the json-type limitation and asyncpg treating ? as a
    # positional parameter placeholder.
    op.execute(sa.text(
        "UPDATE canonical_objects "
        "SET    lesson_data = (lesson_data::jsonb - 'confidence_note')::json "
        "WHERE  lesson_data->>'confidence_note' IS NOT NULL "
        "  AND  lesson_data->>'confidence_note' LIKE '%word not found in model vocabulary%'"
    ))


def downgrade() -> None:
    # The removed confidence_note values cannot be restored; this is a
    # one-way data-quality fix.
    pass
