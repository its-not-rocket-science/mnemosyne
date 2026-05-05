"""Fake RTL plugin — UI test only.

NOT a real language implementation.  This plugin exists solely to drive the
RTL rendering path (dir="rtl", script_family="arabic") in the frontend without
implementing a real Arabic, Hebrew, Urdu, or Persian parser.

Every whitespace-separated token is tagged as a vocabulary item.  All lesson
data contains a "test_plugin" marker so UI tests can verify the origin.

Language code:  x-rtl-test  (BCP-47 private-use prefix — x-* tags are
                               explicitly reserved for private use by RFC 5646.)

DO NOT ship this plugin in production or expose it to learners.  It makes no
linguistic claims and produces no useful lesson content.
"""
from __future__ import annotations

import re

from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

# Split on standard and Arabic terminal punctuation.
_SENTENCE_RE = re.compile(r"[^.!?؟]+[.!?؟]?")
_WORD_RE = re.compile(r"\S+")


class FakeRTLPlugin:
    """Minimal RTL test plugin.

    Treats every whitespace-separated token as a vocabulary candidate.
    No real linguistic processing is performed.
    """

    language_code = "x-rtl-test"
    display_name  = "RTL Test (fake — UI only)"
    direction     = "rtl"
    capabilities  = LanguageCapabilities(
        code="x-rtl-test",
        display_name="RTL Test (fake — UI only)",
        direction="rtl",
        script_family="arabic",
        tokenization_mode="whitespace",
        morphology_depth="none",
        lesson_modes_supported=["vocabulary"],
        # v2 fields — all conservative; this plugin does no real analysis.
        analysis_depth="dictionary",
        segmentation_quality="low",
        tokenization_quality="low",
        morphology_quality="none",
        syntax_support=False,
        idiom_detection=False,
        tts_lang_tag=None,          # no TTS for a fake plugin
        transliteration_scheme=None,
        nuance_capabilities=NuanceCapabilities(),  # all-none: fake plugin, no coverage
    )

    def __init__(self) -> None:
        self.lesson_store: dict[str, CandidateObject] = {}

    # ------------------------------------------------------------------
    # LanguagePlugin protocol
    # ------------------------------------------------------------------

    def analyze_text(self, text: str) -> list[CandidateSentenceResult]:
        return [self.analyze_sentence(s) for s in self.split_sentences(text)]

    def split_sentences(self, text: str) -> list[str]:
        return [
            m.group(0).strip()
            for m in _SENTENCE_RE.finditer(text)
            if m.group(0).strip()
        ]

    def analyze_sentence(self, sentence: str) -> CandidateSentenceResult:
        candidates: list[CandidateObject] = []
        seen: set[str] = set()
        for word in _WORD_RE.findall(sentence):
            lemma = word.lower()
            if lemma in seen:
                continue
            seen.add(lemma)
            candidates.append(
                CandidateObject(
                    canonical_form=lemma,
                    surface_form=word,
                    type="vocabulary",
                    label=word,
                    lesson_data={"lemma": lemma, "test_plugin": "x-rtl-test"},
                    confidence=None,
                )
            )
        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)


def create_plugin() -> FakeRTLPlugin:
    return FakeRTLPlugin()
