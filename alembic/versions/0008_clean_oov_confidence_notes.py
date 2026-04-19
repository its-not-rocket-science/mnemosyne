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

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

_STALE_NOTE = "word not found in model vocabulary"


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE canonical_objects
        SET    lesson_data = lesson_data - 'confidence_note'
        WHERE  lesson_data ? 'confidence_note'
          AND  lesson_data->>'confidence_note' LIKE '%{_STALE_NOTE}%'
        """
    )


def downgrade() -> None:
    # The removed confidence_note values cannot be restored; this is a
    # one-way data-quality fix.
    pass
