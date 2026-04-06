"""Stub English plugin.

Splits text into sentences on terminal punctuation and tags every
alphabetic token as a vocabulary word.  No real NLP — suitable for
integration tests and as a template for real plugins.
"""
from __future__ import annotations

import re

from backend.parsing.plugin_interface import Token
from backend.schemas.parse import LearnableObject, SentenceResult

_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")
_WORD_RE = re.compile(r"[A-Za-z']+")


class EnglishStubPlugin:
    language_code = "en"
    display_name = "English (stub)"
    direction = "ltr"

    def __init__(self) -> None:
        self._lesson_store: dict[str, LearnableObject] = {}

    # ------------------------------------------------------------------
    # LanguagePlugin protocol
    # ------------------------------------------------------------------

    def split_sentences(self, text: str) -> list[str]:
        return [m.group(0).strip() for m in _SENTENCE_RE.finditer(text) if m.group(0).strip()]

    def analyze_sentence(self, sentence: str) -> SentenceResult:
        tokens = self._tokenize(sentence)
        objects = self._extract_vocabulary(tokens)
        for obj in objects:
            self._lesson_store[obj.id] = obj
        return SentenceResult(text=sentence, learnable_objects=objects)

    def get_lesson(self, object_id: str) -> LearnableObject | None:
        return self._lesson_store.get(object_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _tokenize(self, sentence: str) -> list[Token]:
        return [
            Token(text=w, lemma=w.lower(), pos="WORD", morph={})
            for w in _WORD_RE.findall(sentence)
        ]

    def _extract_vocabulary(self, tokens: list[Token]) -> list[LearnableObject]:
        seen: set[str] = set()
        objects: list[LearnableObject] = []
        for token in tokens:
            if token.lemma in seen:
                continue
            seen.add(token.lemma)
            object_id = f"en:vocab:{token.lemma}"
            objects.append(
                LearnableObject(
                    id=object_id,
                    type="vocabulary",
                    label=token.text,
                    lesson_data={"lemma": token.lemma},
                    confidence=None,  # stub — no real confidence
                )
            )
        return objects


def create_plugin() -> EnglishStubPlugin:
    return EnglishStubPlugin()
