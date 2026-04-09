"""Stub French plugin.

Splits text into sentences on terminal punctuation and tags every
alphabetic token as a vocabulary word.  No real NLP — suitable for
integration tests and as a foundation for a full French plugin.

French-specific notes for a future real implementation:
- Use ``fr_core_news_md`` or ``fr_core_news_lg`` for morphology-rich parsing.
- French has grammatical gender and number agreement (adj-noun, det-noun).
- Verb conjugation is highly irregular; a separate lemmatiser may help.
- Elision contractions ("l'", "d'", "qu'") need special handling.
"""
from __future__ import annotations

import re

from backend.parsing.plugin_interface import Token
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

# French sentence endings include standard punctuation.
# «»  quotation marks are left to the sentence splitter to absorb;
# they rarely coincide with sentence boundaries so ignoring them is safe.
_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")

# Match alphabetic tokens including French diacritics and apostrophes.
# Split on apostrophes so "l'homme" → ["l", "homme"] (elision).
_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+")

# Common French function words to exclude from vocabulary extraction.
# A real plugin would use POS tagging; this is a conservative static list.
_STOP_WORDS = frozenset({
    "le", "la", "les", "un", "une", "des", "du", "de", "d",
    "et", "ou", "mais", "donc", "or", "ni", "car",
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles",
    "me", "te", "se", "y", "en",
    "que", "qui", "qu", "ce", "cet", "cette", "ces",
    "l", "j",  # elided forms
    "à", "au", "aux", "par", "pour", "sur", "sous", "dans", "avec",
    "est", "sont", "a", "ont",  # high-freq copula/avoir forms
})


class FrenchStubPlugin:
    language_code = "fr"
    display_name = "French (stub)"
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
            lemma = token.lemma
            if len(lemma) < 2 or lemma in seen or lemma in _STOP_WORDS:
                continue
            seen.add(lemma)
            candidates.append(
                CandidateObject(
                    canonical_form=lemma,
                    type="vocabulary",
                    label=token.text,
                    lesson_data={"lemma": lemma},
                    confidence=None,  # stub — no real confidence
                )
            )
        return candidates


def create_plugin() -> FrenchStubPlugin:
    return FrenchStubPlugin()
