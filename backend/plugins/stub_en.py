"""Stub English plugin.

Splits text into sentences on terminal punctuation and tags every
alphabetic token as a vocabulary word.  No real NLP — suitable for
integration tests and as a template for real plugins.
"""
from __future__ import annotations

import re

from backend.dictionary.phrase_families import lookup_family_by_id, match_phrase_families
from backend.parsing.plugin_interface import Token
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")
_WORD_RE = re.compile(r"[A-Za-z']+")


class EnglishStubPlugin:
    language_code = "en"
    display_name  = "English"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="en",
        display_name="English",
        direction="ltr",
        script_family="latin",
        tokenization_mode="whitespace",
        morphology_depth="rich",
        lesson_modes_supported=["morphology", "vocabulary", "dictionary"],
        # v2 fields
        analysis_depth="full",
        segmentation_quality="high",
        tokenization_quality="medium",
        morphology_quality="medium",
        syntax_support=True,
        idiom_detection=True,
        tts_lang_tag="en",
        transliteration_scheme=None,
        nuance_capabilities=NuanceCapabilities(
            idioms="supported",
            phrase_families="partial",
            literary_references="none",
            cultural_references="none",
            etymology="partial",
            formality_register="partial",
            grammar_nuance="partial",
            pronunciation_tts="partial", # en TTS widely available and reliable
            transliteration="none",
            proverb_tradition="none",
            classical_or_scriptural_allusion="none",
        ),
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
        phrase_candidates = self._extract_phrase_families(tokens)
        # Collect token positions consumed by phrase matches so vocabulary
        # extraction skips those tokens (avoids double-tagging).
        phrase_surfaces: set[str] = set()
        for pc in phrase_candidates:
            if pc.surface_form:
                for w in pc.surface_form.lower().split():
                    phrase_surfaces.add(w)
        vocab_candidates = self._extract_vocabulary(tokens, skip_words=phrase_surfaces)
        return CandidateSentenceResult(
            text=sentence,
            candidates=phrase_candidates + vocab_candidates,
        )

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        lo = self.lesson_store.get(object_id)
        if lo is not None:
            return lo
        return lookup_family_by_id(object_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _tokenize(self, sentence: str) -> list[Token]:
        return [
            Token(text=w, lemma=w.lower(), pos="WORD", morph={})
            for w in _WORD_RE.findall(sentence)
        ]

    def _extract_phrase_families(self, tokens: list[Token]) -> list[CandidateObject]:
        surfaces = [t.text for t in tokens]
        return match_phrase_families(surfaces, language="en")

    def _extract_vocabulary(
        self,
        tokens: list[Token],
        skip_words: set[str] | None = None,
    ) -> list[CandidateObject]:
        seen: set[str] = set()
        candidates: list[CandidateObject] = []
        for token in tokens:
            if skip_words and token.lemma in skip_words:
                continue
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
