"""Persian (Farsi) plugin -- dictionary mode, RTL, Perso-Arabic script.

BCP-47 code "fa", RTL direction, whitespace tokenisation.

What this plugin does reliably
-------------------------------
  - Sentence splitting on standard and Arabic-block terminal punctuation.
  - Whitespace tokenisation; Persian prose is space-delimited.
  - Tashkeel (short-vowel diacritics) stripping for canonical forms.
  - Correct RTL / Perso-Arabic metadata for frontend rendering.
  - TTS tag "fa" (browser SpeechSynthesis; coverage varies by platform).

Perso-Arabic script notes
--------------------------
  All core Persian letters (U+067E peh/pe, U+0686 cheh/che, U+0698 jeh/zhe,
  U+06AF gaf, U+06A9 keheh/kaf, U+06CC ye) fall within the U+0670-U+06D3
  range already present in the Arabic Unicode block -- no additional codepoint
  ranges needed.
  ZWNJ (U+200C) appears in compound verbal forms such as mi-konam
  (U+0645 U+06CC U+200C U+06A9 U+0646 U+0645). ZWNJ is not whitespace, so
  compound forms survive whitespace splitting as single tokens; _WORD_RE
  splits them at the ZWNJ boundary. The nuance extractor detects mi- / nami-
  preverbs via raw-sentence regex.

Known limitations
------------------
  - No morphological analyser: no POS, lemmatisation, or inflection data.
  - Ezafe (izafe) linking particle is silent in standard orthography.
  - Clitic pronouns (-am, -at, etc.) remain unsplit.
  - Sentence splitting is a regex heuristic; complex prose may mis-split.
"""
from __future__ import annotations

import re

from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

# Sentence splitting: standard terminal marks plus U+061F Arabic question mark
# and U+06D4 Arabic full stop. Newlines as additional soft boundary.
_SENTENCE_RE = re.compile(r"[^.!?؟۔\n]+[.!?؟۔\n]?")

# Word tokenisation: match runs of Perso-Arabic letters and diacritical marks.
# Ranges identical to the Arabic plugin -- Persian letters all within Arabic block:
#   U+0621-U+063A  Arabic consonants alef through ghayn
#   U+0641-U+065F  Arabic consonants fa through ya + diacritical marks
#   U+0670-U+06D3  Extended Arabic letters (all unique Persian letters here)
#   U+06D5         Arabic letter ae
#   U+0750-U+077F  Arabic Supplement
#   U+FB50-U+FDFF  Arabic Presentation Forms-A
#   U+FE70-U+FEFF  Arabic Presentation Forms-B
# ZWNJ (U+200C) is excluded so mi-konam splits at the ZWNJ boundary;
# the preverb mi- is detected via sentence-level regex in the nuance extractor.
_WORD_RE = re.compile(
    r"[ء-غ"
    r"ف-ٟ"
    r"ٰ-ۓ"
    r"ە"
    r"ݐ-ݿ"
    r"ﭐ-﷿"
    r"ﹰ-﻿]+"
)

# Tashkeel (short-vowel diacriticals) stripping for canonical normalisation.
# U+064B-U+065F: fathatan through U+065F (all harakat, explicitly skipping
# Arabic-Indic digits at U+0660-U+0669). U+0670: superscript alef.
_TASHKEEL_RE = re.compile(r"[ً-ٰٟ]")


def _strip_tashkeel(text: str) -> str:
    return _TASHKEEL_RE.sub("", text)


class PersianPlugin:
    """Persian (Farsi) starter -- dictionary mode plugin.

    Provides sentence splitting, whitespace tokenisation, tashkeel
    normalisation, and grammar nuance detection via the Farsi nuance extractor.
    Capabilities are declared honestly for dictionary-depth analysis.
    """

    language_code = "fa"
    display_name  = "Persian (Farsi)"
    direction     = "rtl"
    capabilities  = LanguageCapabilities(
        code="fa",
        display_name="Persian (Farsi)",
        direction="rtl",
        script_family="arabic",
        tokenization_mode="whitespace",
        morphology_depth="none",
        lesson_modes_supported=["vocabulary", "dictionary"],
        analysis_depth="dictionary",
        segmentation_quality="low",
        tokenization_quality="medium",
        morphology_quality="low",
        syntax_support=False,
        idiom_detection=False,
        tts_lang_tag="fa",
        transliteration_scheme=None,
        nuance_capabilities=NuanceCapabilities(
            idioms="none",
            phrase_families="none",
            literary_references="partial",
            cultural_references="partial",
            etymology="none",
            formality_register="partial",
            grammar_nuance="partial",
            pronunciation_tts="stub",
            transliteration="none",
            proverb_tradition="none",
            classical_or_scriptural_allusion="partial",
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
        return [
            m.group(0).strip()
            for m in _SENTENCE_RE.finditer(text)
            if m.group(0).strip()
        ]

    def analyze_sentence(self, sentence: str) -> CandidateSentenceResult:
        candidates: list[CandidateObject] = []
        seen: set[str] = set()

        raw_tokens = _WORD_RE.findall(sentence)

        for tok in raw_tokens:
            canonical = _strip_tashkeel(tok)
            if not canonical or canonical in seen:
                continue
            seen.add(canonical)

            candidates.append(
                CandidateObject(
                    canonical_form=canonical,
                    surface_form=tok,
                    type="vocabulary",
                    label=tok,
                    lesson_data={"lemma": canonical},
                    confidence=None,
                )
            )

        candidates.extend(self._extract_nuance(sentence, raw_tokens, candidates, seen))
        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def _extract_nuance(
        self,
        sentence: str,
        tokens: list[str],
        candidates: list[CandidateObject],
        seen: set[str],
    ) -> list[CandidateObject]:
        from backend.nuance.fa import FarsiNuanceExtractor  # noqa: PLC0415

        nuance_candidates = FarsiNuanceExtractor().extract_nuance(
            sentence, tokens, candidates, self.language_code
        )
        out: list[CandidateObject] = []
        for cand in nuance_candidates:
            if cand.canonical_form in seen:
                continue
            seen.add(cand.canonical_form)
            out.append(cand)
        return out

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)


def create_plugin() -> PersianPlugin:
    return PersianPlugin()
