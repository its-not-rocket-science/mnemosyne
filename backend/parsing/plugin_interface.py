from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.schemas.parse import LearnableObject, SentenceResult


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

    def split_sentences(self, text: str) -> list[str]:
        ...

    def analyze_sentence(self, sentence: str) -> SentenceResult:
        ...

    def get_lesson(self, object_id: str) -> LearnableObject | None:
        ...
