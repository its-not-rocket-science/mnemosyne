"""Stub English plugin.

Splits text into sentences on terminal punctuation and tags every
alphabetic token as a vocabulary word.  No real NLP — suitable for
integration tests and as a template for real plugins.
"""
from __future__ import annotations

import re

from backend.parsing.plugin_interface import Token
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")
_WORD_RE = re.compile(r"[A-Za-z']+")


class EnglishStubPlugin:
    language_code = "en"
    display_name = "English (stub)"
    direction = "ltr"

    def __init__(self) -> None:
        self.lesson_store: dict[str, CandidateObject] = {}

    # ------------------------------------------------------------------
    # LanguagePlugin protocol
    # ------------------------------------------------------------------

    def analyze_text(self, text: str) -> list[CandidateSentenceResult]:
        return [self.analyze_sentence(s) for s in self.split_sentences(text)]

    def split_sentences(self, text: str) -> list[str]:
        return [m.group(0).strip() for m in _SENTENCE_RE.finditer(text) if m.group(0).strip()]

    def analyze_sentence(self, sentence: str) -> CandidateSentenceResult:
        tokens = self._tokenize(sentence)
        candidates = self._extract_vocabulary(tokens)
        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _tokenize(self, sentence: str) -> list[Token]:
        return [
            Token(text=w, lemma=w.lower(), pos="WORD", morph={})
            for w in _WORD_RE.findall(sentence)
        ]

    def _extract_vocabulary(self, tokens: list[Token]) -> list[CandidateObject]:
        seen: set[str] = set()
        candidates: list[CandidateObject] = []
        for token in tokens:
            if token.lemma in seen:
                continue
            seen.add(token.lemma)
            candidates.append(
                CandidateObject(
                    canonical_form=token.lemma,
                    surface_form=token.text,
                    type="vocabulary",
                    label=token.text,
                    lesson_data={"lemma": token.lemma},
                    confidence=None,  # stub — no real confidence
                )
            )
        return candidates


def create_plugin() -> EnglishStubPlugin:
    return EnglishStubPlugin()
