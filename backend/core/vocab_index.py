"""In-memory CEFR vocabulary index.

Loaded once at startup from the vocabulary_entries table.  Provides O(1)
lemma → cefr_level lookup for all languages and all CEFR levels (A1-C2),
replacing the hardcoded A1-only frozensets in cefr_vocab.py for callers that
only need CEFR level (not membership in a specific set).

Usage in plugins
────────────────
  from backend.core.vocab_index import get_cefr_level

  level = get_cefr_level("es", lemma)   # "A1" | "B2" | None
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# (language, lemma_lower) → cefr_level
_INDEX: dict[tuple[str, str], str] = {}


def get_cefr_level(language: str, lemma: str) -> str | None:
    """Return the CEFR level for *lemma* in *language*, or None if unknown."""
    return _INDEX.get((language, lemma.lower()))


def index_size() -> int:
    return len(_INDEX)


async def load(session_factory) -> None:
    """Populate the index from the database.  Safe to call multiple times."""
    from sqlalchemy import text

    try:
        async with session_factory() as db:
            rows = await db.execute(
                text("SELECT language, lemma, cefr_level FROM vocabulary_entries")
            )
            new_index: dict[tuple[str, str], str] = {}
            for lang, lemma, level in rows:
                new_index[(lang, lemma.lower())] = level
        _INDEX.clear()
        _INDEX.update(new_index)
        logger.info("Vocabulary index loaded: %d entries", len(_INDEX))
    except Exception as exc:
        logger.warning("Vocabulary index load failed (CEFR lookup degraded): %s", exc)
