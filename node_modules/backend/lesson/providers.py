"""Provider abstractions for external linguistic data sources.

A *provider* is a callable object that looks up data the lesson engine
cannot derive from morphological analysis alone — dictionary glosses,
IPA pronunciation, example sentences, etc.

All providers follow a Protocol so any object with the right method can be
used.  Null implementations are provided as safe defaults so the lesson
engine works offline with no configuration.

Extension points
────────────────
To add a real gloss source (e.g. Wiktionary, a local SQLite dictionary):

    class WiktionaryGlossProvider:
        def lookup(self, lemma: str, language_code: str | None, ...) -> str | None:
            ...  # fetch from local cache or remote API

    providers = LessonProviders(gloss=WiktionaryGlossProvider())
    build_lesson(..., providers=providers)

The lesson engine calls providers only when the plugin's ``lesson_data`` does
not already contain the field (gloss, pronunciation).  Providers supplement;
they never overwrite what the plugin has determined.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


# ── Provider protocols ────────────────────────────────────────────────────────

@runtime_checkable
class GlossProvider(Protocol):
    """Looks up a word's English gloss / dictionary meaning.

    ``pos`` is an optional UD POS tag (``"NOUN"``, ``"VERB"``, …) that
    implementations may use to disambiguate polysemous words.
    ``language_code`` is ``None`` when the language is unknown.
    """

    def lookup(
        self,
        lemma: str,
        language_code: str | None,
        pos: str | None = None,
    ) -> str | None:
        """Return an English gloss for *lemma*, or None if unavailable."""
        ...


@runtime_checkable
class PronunciationProvider(Protocol):
    """Returns phonetic / IPA representation of a surface form."""

    def pronunciation(
        self,
        surface: str,
        language_code: str | None,
    ) -> str | None:
        """Return a phonetic string for *surface*, or None if unavailable."""
        ...


# ── Null implementations ──────────────────────────────────────────────────────

class NullGlossProvider:
    """No-op gloss provider — always returns None."""

    def lookup(
        self,
        lemma: str,
        language_code: str | None,
        pos: str | None = None,
    ) -> str | None:
        return None


class VocabIndexGlossProvider:
    """Gloss provider backed by the in-memory vocabulary index.

    Returns the English definition stored in vocabulary_entries (populated by
    the harvest script from Wiktionary).  Returns None when the word is not in
    the index or has no definition.
    """

    def lookup(
        self,
        lemma: str,
        language_code: str | None,
        pos: str | None = None,
    ) -> str | None:
        if not language_code:
            return None
        from backend.core.vocab_index import get_definition
        return get_definition(language_code, lemma)


class NullPronunciationProvider:
    """No-op pronunciation provider — always returns None."""

    def pronunciation(
        self,
        surface: str,
        language_code: str | None,
    ) -> str | None:
        return None


# ── Container ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LessonProviders:
    """Bundle of providers injected into the lesson build pipeline.

    Construct with null implementations (the default) to get deterministic,
    offline lesson generation.  Swap individual providers to add external
    data sources without changing any builder code.

    Example::

        providers = LessonProviders(gloss=MyGlossProvider())
        lesson = build_lesson(..., providers=providers)
    """

    gloss: GlossProvider = field(default_factory=NullGlossProvider)
    pronunciation: PronunciationProvider = field(default_factory=NullPronunciationProvider)

    @classmethod
    def null(cls) -> "LessonProviders":
        """Return providers with all-null implementations.  Safe for tests."""
        return cls()
