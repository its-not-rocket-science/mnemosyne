from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.schemas.language import LanguageCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult


@dataclass(slots=True)
class Token:
    text: str
    lemma: str
    pos: str
    morph: dict[str, str]


class LanguagePlugin(Protocol):
    language_code: str
    display_name: str
    direction: str  # kept for backward compatibility; mirrors capabilities.direction
    # Plugins with test_only=True are never registered when DEBUG=False.
    # Omitting the attribute is equivalent to False (getattr default in loader).
    test_only: bool

    # Rich capability metadata — replaces the bare ``direction`` string for
    # any code that needs to know how to render or score this language.
    capabilities: LanguageCapabilities

    # Populated by the parse route after UUID resolution; used by get_lesson()
    # as a fallback when the DB is unavailable.  Keyed by the canonical UUID
    # so the parse route can populate it without a separate lookup.
    lesson_store: dict[str, CandidateObject]

    def analyze_text(self, text: str) -> list[CandidateSentenceResult]:
        """Parse the full input text in one pass and return one result per sentence.

        Implementations should avoid calling the underlying NLP model more than
        once.  The parse route calls this method exclusively; ``split_sentences``
        and ``analyze_sentence`` are kept for direct use in tests and tooling.
        """
        ...  # pragma: no cover

    def split_sentences(self, text: str) -> list[str]:
        ...  # pragma: no cover

    def analyze_sentence(self, sentence: str) -> CandidateSentenceResult:
        ...  # pragma: no cover

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        ...  # pragma: no cover
