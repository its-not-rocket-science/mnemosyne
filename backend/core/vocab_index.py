"""In-memory CEFR vocabulary index.

Loaded once at startup from the vocabulary_entries table.  Provides O(1)
lemma → cefr_level and lemma → definition lookup for all languages (A1-C2).

Usage in plugins
────────────────
  from backend.core.vocab_index import get_cefr_level, get_definition

  level = get_cefr_level("es", lemma)   # "A1" | "B2" | None
  defn  = get_definition("es", lemma)   # "a dwelling place" | None
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# (language, lemma_lower) → cefr_level
_INDEX: dict[tuple[str, str], str] = {}
# (language, lemma_lower) → definition (English gloss from Wiktionary)
_DEFS: dict[tuple[str, str], str] = {}


def get_cefr_level(language: str, lemma: str) -> str | None:
    """Return the CEFR level for *lemma* in *language*, or None if unknown."""
    return _INDEX.get((language, lemma.lower()))


def get_definition(language: str, lemma: str) -> str | None:
    """Return the stored English definition for *lemma*, or None."""
    return _DEFS.get((language, lemma.lower()))


def index_size() -> int:
    return len(_INDEX)


async def load(session_factory) -> None:
    """Populate the index from the database.  Safe to call multiple times."""
    from sqlalchemy import text

    try:
        async with session_factory() as db:
            rows = await db.execute(
                text("SELECT language, lemma, cefr_level, definition FROM vocabulary_entries")
            )
            new_index: dict[tuple[str, str], str] = {}
            new_defs: dict[tuple[str, str], str] = {}
            for lang, lemma, level, defn in rows:
                key = (lang, lemma.lower())
                new_index[key] = level
                if defn:
                    new_defs[key] = defn
        _INDEX.clear()
        _INDEX.update(new_index)
        _DEFS.clear()
        _DEFS.update(new_defs)
        logger.info(
            "Vocabulary index loaded: %d entries, %d definitions",
            len(_INDEX), len(_DEFS),
        )
    except Exception as exc:
        logger.warning("Vocabulary index load failed (CEFR lookup degraded): %s", exc)
