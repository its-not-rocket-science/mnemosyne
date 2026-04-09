from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.schemas.parse import CandidateSentenceResult, LearnableObject


@dataclass(slots=True)
class Token:
    text: str
    lemma: str
    pos: str
    morph: dict[str, str]


class LanguagePlugin(Protocol):
    language_code: str
    display_name: str
    direction: str

    # Populated by the parse route after UUID resolution; used by get_lesson()
    # as a fallback when the DB is unavailable.
    lesson_store: dict[str, LearnableObject]

    def split_sentences(self, text: str) -> list[str]:
        ...

    def analyze_sentence(self, sentence: str) -> CandidateSentenceResult:
        ...

    def get_lesson(self, object_id: str) -> LearnableObject | None:
        ...
