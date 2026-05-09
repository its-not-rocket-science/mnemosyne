"""Legacy French stub plugin — kept for reference and protocol-compliance tests.

This stub is no longer registered by the plugin loader (``create_plugin`` has
been removed).  The real implementation is in ``backend/plugins/french.py``.

The stub uses regex-based sentence splitting and a static stop-word list for
vocabulary extraction.  It demonstrates the minimal surface area required by
the ``LanguagePlugin`` protocol for languages without NLP model support.
"""
from __future__ import annotations

import re

from backend.parsing.plugin_interface import Token
from backend.schemas.language import LanguageCapabilities
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
    display_name  = "French (stub)"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="fr",
        display_name="French (stub)",
        direction="ltr",
        script_family="latin",
        tokenization_mode="whitespace",
        morphology_depth="none",
        lesson_modes_supported=["vocabulary"],
        # v2 fields
        analysis_depth="dictionary",
        segmentation_quality="medium",
        tokenization_quality="low",      # regex + static stop-word list
        morphology_quality="none",
        syntax_support=False,
        idiom_detection=False,
        tts_lang_tag="fr",
        transliteration_scheme=None,
    )

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
                    surface_form=token.text,
                    type="vocabulary",
                    label=token.text,
                    lesson_data={"lemma": lemma},
                    confidence=None,  # stub — no real confidence
                )
            )
        return candidates


# create_plugin() intentionally absent — the real French plugin
# (backend/plugins/french.py) is now registered instead.
