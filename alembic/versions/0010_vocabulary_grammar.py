"""Add vocabulary_entries and grammar_rules tables.

Revision ID: 0010
Revises: 0009
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS vocabulary_entries (
            id              BIGSERIAL PRIMARY KEY,
            language        VARCHAR(10)  NOT NULL,
            lemma           TEXT         NOT NULL,
            pos             VARCHAR(20),
            cefr_level      VARCHAR(2)   NOT NULL
                                CHECK (cefr_level IN ('A1','A2','B1','B2','C1','C2')),
            definition      TEXT,
            frequency_rank  INT,
            source          VARCHAR(80)  NOT NULL,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_vocab_lang_lemma_pos UNIQUE (language, lemma, pos)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_vocab_lang_level ON vocabulary_entries(language, cefr_level)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vocab_lang_lemma ON vocabulary_entries(language, lemma)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS grammar_rules (
            id          SERIAL PRIMARY KEY,
            language    VARCHAR(10)  NOT NULL,
            cefr_level  VARCHAR(2)   NOT NULL
                            CHECK (cefr_level IN ('A1','A2','B1','B2','C1','C2')),
            category    VARCHAR(80)  NOT NULL,
            name        TEXT         NOT NULL,
            description TEXT         NOT NULL,
            examples    JSONB        NOT NULL DEFAULT '[]',
            source      VARCHAR(80)  NOT NULL,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_grammar_lang_level_name UNIQUE (language, cefr_level, name)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_grammar_lang_level ON grammar_rules(language, cefr_level)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_grammar_lang_cat   ON grammar_rules(language, category)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS grammar_rules")
    op.execute("DROP TABLE IF EXISTS vocabulary_entries")
