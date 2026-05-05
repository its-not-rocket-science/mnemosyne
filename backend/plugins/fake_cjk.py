"""Fake CJK plugin — UI test only.

NOT a real language implementation.  This plugin exists solely to drive the
character-segmented rendering path (tokenization_mode="character",
word-break:break-all) and the script-view toggle (transliteration_scheme set)
in the frontend without implementing a real CJK NLP pipeline.

Each non-whitespace character in the input becomes a separate "script" type
candidate, mimicking the output shape of a real CJK tokeniser.  A fake romaji
placeholder (U+XXXX hex) is stored as lesson_data["romaji"] so the lesson
renderer has a transliteration value to display.

Language code:  x-cjk-test  (BCP-47 private-use prefix — x-* tags are
                               explicitly reserved for private use by RFC 5646.)

DO NOT ship this plugin in production or expose it to learners.  It makes no
linguistic claims and produces no useful lesson content.
"""
from __future__ import annotations

import re

from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

# Split on ASCII and CJK full-width terminal punctuation.
_SENTENCE_RE = re.compile(r"[^.!?。！？]+[.!?。！？]?")
# Each non-whitespace character is a candidate segmentation unit.
_CHAR_RE = re.compile(r"\S")


class FakeCJKPlugin:
    """Minimal CJK-style test plugin with character-level segmentation.

    Each non-space character in the input becomes a separate "script" candidate,
    mimicking the output shape of a real CJK tokeniser.  Transliteration
    placeholders (U+XXXX hex strings) are included so the script-view toggle
    in the frontend has something to display.
    """

    language_code = "x-cjk-test"
    display_name  = "CJK Test (fake — UI only)"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="x-cjk-test",
        display_name="CJK Test (fake — UI only)",
        direction="ltr",
        script_family="cjk",
        tokenization_mode="character",
        morphology_depth="none",
        lesson_modes_supported=["vocabulary"],
        # v2 fields — all conservative; this plugin does no real analysis.
        analysis_depth="segmentation_only",
        segmentation_quality="low",
        tokenization_quality="low",
        morphology_quality="none",
        syntax_support=False,
        idiom_detection=False,
        tts_lang_tag=None,
        # Declare a scheme so the frontend shows the script-view toggle.
        transliteration_scheme="fake_romaji",
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
        for char in _CHAR_RE.findall(sentence):
            if char in seen:
                continue
            seen.add(char)
            # Fake romaji: Unicode code point in standard U+XXXX notation.
            romaji = f"U+{ord(char):04X}"
            candidates.append(
                CandidateObject(
                    canonical_form=char,
                    surface_form=char,
                    type="script",
                    label=char,
                    lesson_data={
                        "character": char,
                        "romaji": romaji,
                        "test_plugin": "x-cjk-test",
                    },
                    confidence=None,
                )
            )
        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)


def create_plugin() -> FakeCJKPlugin:
    return FakeCJKPlugin()
