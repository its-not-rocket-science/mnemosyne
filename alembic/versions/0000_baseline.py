"""Baseline schema — all tables that existed before alembic was introduced.

Creates every pre-alembic table using ``CREATE TABLE IF NOT EXISTS`` so
this migration is safe to apply against databases that were bootstrapped
with ``Base.metadata.create_all()`` before the alembic chain was introduced.

On a fresh (empty) database this migration creates the full pre-alembic
schema; subsequent migrations then build on it.  On an existing database
every statement is a silent no-op and the migration simply records itself
in ``alembic_version``.

Tables covered
──────────────
Legacy tables (no ORM model; only needed so migration 0001 can run its
data migration against empty tables without raising "relation does not
exist"):
  learnable_objects   — pre-canonical-graph vocabulary/conjugation store
  review_states       — single-user per-object review state (before multi-user)

Live ORM tables that pre-date alembic (still in models.py):
  parsed_texts        — one row per /parse call
  sentences           — one row per sentence within a ParsedText
  user_knowledge      — FSRS state per (user, object) pair
                        NB: the ``first_seen`` column is added by migration
                        0003 — do NOT include it here.
  source_documents    — ingested document metadata
  source_chunks       — links a SourceDocument to a ParsedText parse
  source_progression  — per-(user, document) reading progress

Tables NOT covered here (each is created by a later migration):
  canonical_objects, object_relations, sentence_objects  → 0001
  user_language_preferences                              → 0004
  users                                                  → 0005
  review_events                                          → 0006
  user_fsrs_params                                       → 0007

Revision ID: 0000
Revises:     (none — first in chain)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0000"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # All statements use IF NOT EXISTS so the migration is idempotent on
    # databases that were already bootstrapped with Base.metadata.create_all().

    # ── Legacy: learnable_objects ────────────────────────────────────────────
    # Migration 0001 reads from and drops this table as part of migrating to
    # the canonical-object-graph schema.  Created empty here so 0001 can run
    # on a fresh database without "relation does not exist" errors.
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS learnable_objects (
            id          VARCHAR       NOT NULL PRIMARY KEY,
            language    VARCHAR(10)   NOT NULL,
            type        VARCHAR(50)   NOT NULL,
            label       VARCHAR       NOT NULL,
            lesson_data JSON          NOT NULL DEFAULT '{}',
            confidence  FLOAT,
            created_at  TIMESTAMP
        )
    """))

    # ── Legacy: review_states ────────────────────────────────────────────────
    # Migration 0001 reads and updates this table to remap string object IDs
    # to deterministic UUIDs.  Replaced by user_knowledge (multi-user) but
    # never explicitly dropped; created empty here so 0001 can run cleanly.
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS review_states (
            object_id   VARCHAR     NOT NULL PRIMARY KEY,
            state       JSON,
            updated_at  TIMESTAMP
        )
    """))

    # ── parsed_texts ─────────────────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS parsed_texts (
            id          VARCHAR(36)  NOT NULL PRIMARY KEY,
            language    VARCHAR(10),
            source_text TEXT,
            source_url  VARCHAR,
            created_at  TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))

    # ── sentences ────────────────────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS sentences (
            id              VARCHAR(36)  NOT NULL PRIMARY KEY,
            parsed_text_id  VARCHAR(36)  REFERENCES parsed_texts(id)
                                         ON DELETE CASCADE,
            position        INTEGER      NOT NULL,
            text            TEXT         NOT NULL
        )
    """))

    # ── user_knowledge ───────────────────────────────────────────────────────
    # NB: ``first_seen`` is intentionally omitted — migration 0003 adds it via
    # op.add_column so that existing rows receive NULL on upgrade.
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS user_knowledge (
            user_id        VARCHAR(50)  NOT NULL,
            object_id      VARCHAR      NOT NULL,
            language       VARCHAR(10),
            fsrs_state     JSON,
            mastery_score  FLOAT        NOT NULL DEFAULT 0.0,
            last_seen      TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP,
            total_reviews  INTEGER      NOT NULL DEFAULT 0,
            due_at         TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, object_id)
        )
    """))

    # ── source_documents ─────────────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS source_documents (
            id            VARCHAR(36)   NOT NULL PRIMARY KEY,
            language      VARCHAR(10)   NOT NULL,
            content_type  VARCHAR(50)   NOT NULL,
            title         VARCHAR(512),
            author        VARCHAR(256),
            source_url    VARCHAR,
            filename      VARCHAR(256),
            char_count    INTEGER       NOT NULL DEFAULT 0,
            script_hint   VARCHAR(32),
            created_at    TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))

    # ── source_chunks ─────────────────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS source_chunks (
            id                  VARCHAR(36)  NOT NULL PRIMARY KEY,
            source_document_id  VARCHAR(36)  NOT NULL
                                             REFERENCES source_documents(id)
                                             ON DELETE CASCADE,
            parsed_text_id      VARCHAR(36)  NOT NULL
                                             REFERENCES parsed_texts(id),
            chunk_index         INTEGER      NOT NULL DEFAULT 0,
            char_start          INTEGER      NOT NULL DEFAULT 0,
            char_end            INTEGER      NOT NULL DEFAULT 0
        )
    """))

    # ── source_progression ───────────────────────────────────────────────────
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS source_progression (
            user_id              VARCHAR(50)  NOT NULL,
            source_document_id   VARCHAR(36)  NOT NULL
                                              REFERENCES source_documents(id)
                                              ON DELETE CASCADE,
            next_position        INTEGER      NOT NULL DEFAULT 0,
            sentences_total      INTEGER      NOT NULL DEFAULT 0,
            avg_comprehension    FLOAT        NOT NULL DEFAULT 0.0,
            completion_fraction  FLOAT        NOT NULL DEFAULT 0.0,
            last_read_at         TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at           TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, source_document_id)
        )
    """))


def downgrade() -> None:
    # Downgrade only drops tables that are genuinely empty on a fresh install
    # (legacy tables only — live data tables are not dropped on downgrade).
    op.execute(sa.text("DROP TABLE IF EXISTS review_states"))
    op.execute(sa.text("DROP TABLE IF EXISTS learnable_objects"))
    # NB: source_progression, source_chunks, source_documents, user_knowledge,
    # sentences, parsed_texts are NOT dropped on downgrade because they may
    # contain live user data.  A full DB wipe is a separate operator action.
