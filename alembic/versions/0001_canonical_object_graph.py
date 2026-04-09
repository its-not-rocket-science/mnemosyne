"""Introduce canonical object graph.

Replaces the ``learnable_objects`` table (string PKs) with three new tables:

  canonical_objects   — deduplicated objects with deterministic UUID PKs
  object_relations    — directed relationships between canonical objects
  sentence_objects    — join table linking sentences to canonical objects

Also updates ``review_states.object_id`` values: the old string keys
(e.g. ``es:vocab:hola``) are recomputed to deterministic UUID-v5 values
so that existing review history is preserved.

Revision ID: 0001
Revises: (none — first migration)
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

# Fixed namespace — must match backend/parsing/canonical.py _NAMESPACE.
_NAMESPACE = uuid.UUID("12e3d947-f3c4-4e2b-a9a1-0d3c2e1f5b7a")

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _canonical_object_id(language: str, type_: str, canonical_form: str) -> str:
    key = f"{language}\x00{type_}\x00{canonical_form}"
    return str(uuid.uuid5(_NAMESPACE, key))


def _parse_old_id(old_id: str) -> tuple[str, str, str] | None:
    """Decompose ``{lang}:{type}:{canonical_form}`` into its three parts.

    Returns None for IDs that cannot be decomposed (e.g. malformed rows).
    The ``canonical_form`` for conjugations contains colons, so we split on
    the first two colons only.
    """
    parts = old_id.split(":", 2)
    if len(parts) != 3:
        return None
    lang, type_slug, canonical_form = parts
    # Map old type slugs to LearnableType values.
    type_map = {
        "vocab":     "vocabulary",
        "conj":      "conjugation",
        "agreement": "agreement",
    }
    learnable_type = type_map.get(type_slug)
    if learnable_type is None:
        return None
    return lang, learnable_type, canonical_form


def upgrade() -> None:
    # ── Create new tables ────────────────────────────────────────────────────

    op.create_table(
        "canonical_objects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("canonical_form", sa.String(), nullable=False),
        sa.Column("display_label", sa.String(), nullable=False),
        sa.Column("lesson_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("language", "type", "canonical_form", name="uq_canonical_object"),
    )

    op.create_table(
        "object_relations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "source_id",
            sa.String(36),
            sa.ForeignKey("canonical_objects.id"),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            sa.String(36),
            sa.ForeignKey("canonical_objects.id"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(50), nullable=False),
        sa.UniqueConstraint(
            "source_id", "target_id", "relation_type", name="uq_object_relation"
        ),
    )

    op.create_table(
        "sentence_objects",
        sa.Column(
            "sentence_id",
            sa.String(36),
            sa.ForeignKey("sentences.id"),
            primary_key=True,
        ),
        sa.Column(
            "object_id",
            sa.String(36),
            sa.ForeignKey("canonical_objects.id"),
            primary_key=True,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
    )

    # ── Migrate learnable_objects → canonical_objects ────────────────────────
    conn = op.get_bind()

    rows = conn.execute(
        sa.text(
            "SELECT id, language, type, label, lesson_data, confidence, created_at "
            "FROM learnable_objects"
        )
    ).fetchall()

    now_sql = sa.func.now()

    for row in rows:
        parsed = _parse_old_id(row.id)
        if parsed is None:
            continue
        lang, learnable_type, canonical_form = parsed
        new_id = _canonical_object_id(lang, learnable_type, canonical_form)

        conn.execute(
            sa.text(
                "INSERT INTO canonical_objects "
                "(id, language, type, canonical_form, display_label, lesson_data, confidence, created_at, updated_at) "
                "VALUES (:id, :language, :type, :canonical_form, :display_label, :lesson_data, :confidence, :created_at, :updated_at) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {
                "id": new_id,
                "language": lang,
                "type": learnable_type,
                "canonical_form": canonical_form,
                "display_label": row.label,
                "lesson_data": row.lesson_data,
                "confidence": row.confidence,
                "created_at": row.created_at,
                "updated_at": row.created_at,
            },
        )

    # ── Migrate review_states.object_id ─────────────────────────────────────
    review_rows = conn.execute(
        sa.text("SELECT object_id, state, updated_at FROM review_states")
    ).fetchall()

    for row in review_rows:
        parsed = _parse_old_id(row.object_id)
        if parsed is None:
            continue
        lang, learnable_type, canonical_form = parsed
        new_id = _canonical_object_id(lang, learnable_type, canonical_form)
        if new_id == row.object_id:
            continue  # already a UUID (shouldn't happen, but be safe)
        conn.execute(
            sa.text(
                "INSERT INTO review_states (object_id, state, updated_at) "
                "VALUES (:new_id, :state, :updated_at) "
                "ON CONFLICT (object_id) DO NOTHING"
            ),
            {"new_id": new_id, "state": row.state, "updated_at": row.updated_at},
        )
        conn.execute(
            sa.text("DELETE FROM review_states WHERE object_id = :old_id"),
            {"old_id": row.object_id},
        )

    # ── Drop old table ───────────────────────────────────────────────────────
    op.drop_table("learnable_objects")


def downgrade() -> None:
    op.drop_table("sentence_objects")
    op.drop_table("object_relations")
    op.create_table(
        "learnable_objects",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("lesson_data", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Data migration back is not implemented — downgrade empties learnable_objects.
    op.drop_table("canonical_objects")
