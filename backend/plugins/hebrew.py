"""Hebrew starter plugin — dictionary mode.

BCP-47 code "he", RTL direction, standard sentence punctuation.
This plugin provides NO morphological analysis.

What this plugin does reliably
──────────────────────────────
  - Sentence splitting on standard terminal punctuation and newlines.
  - Whitespace tokenisation (modern Hebrew prose is whitespace-delimited).
  - Nikud (vowel-point) stripping for canonical forms, so
    "סֵפֶר" and "ספר" resolve to the same canonical object.
  - Correct RTL / hebrew metadata for frontend rendering and font selection.
  - TTS tag "he" (browser SpeechSynthesis covers modern Hebrew).

What this plugin does NOT do
─────────────────────────────
  - Root (shoresh) extraction or pattern-based morphological analysis.
  - Part-of-speech tagging.
  - Lemmatisation beyond nikud normalisation.
  - Prefix segmentation (ו-, ב-, ה-, ל-, כ-, מ-, ש-…).
  - Any claim about word meaning.

Upgrade path
────────────
  When spacy-he, stanza-he, or a comparable library is available as a
  dependency, this plugin can be promoted:
    tokenization_quality → high        (after adding prefix splitting)
    morphology_depth     → shallow     (after POS tagging)
    analysis_depth       → morphology_light
    lesson_modes_supported → ["vocabulary", "dictionary"]

Known limitations
─────────────────
  • Hebrew inseparable prepositions and the definite article (ה-) attach
    directly to their host word.  וְהַסֵּפֶר ("and the book") is one token
    in normal orthography; the prefixes are not split off here.
  • Tokenisation quality is rated "medium" for standard prose.  Poetry,
    abbreviations (ראשי תיבות), and informal text will have higher error rates.
  • Biblical Hebrew (with cantillation marks) is handled by the nikud
    stripper at the canonicalisation level; segmentation is not adapted for
    it beyond that.
"""
from __future__ import annotations

import re

from backend.plugins.cefr_vocab import A1 as _CEFR_A1
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

_A1: frozenset[str] = _CEFR_A1.get("he", frozenset())

# ── Sentence splitting ────────────────────────────────────────────────────────
_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?\n]?")

# ── Word tokenisation ─────────────────────────────────────────────────────────
# Match runs of Hebrew letters together with any attached nikud / cantillation
# marks so that a vowel-pointed word like "שַׁבָּת" is captured as one token
# rather than being split by the combining characters into "ש", "ב", "ת".
# After matching, _strip_nikud removes all combining marks to give the clean
# canonical form.
#
# Ranges included:
#   U+05D0–U+05EA  Hebrew core letters (alef through tav)
#   U+05F0–U+05F4  Yiddish digraphs and Hebrew punctuation (geresh, gershayim)
#   U+FB1D–U+FB4E  Hebrew Presentation Forms (alternative letter forms)
#   U+0591–U+05AF  Cantillation marks (te'amim — Biblical Hebrew)
#   U+05B0–U+05BD  Vowel points (shva, patah, qamats, hiriq, …)
#   U+05BF         Rafe (softening mark)
#   U+05C1–U+05C2  Shin dot / sin dot
#   U+05C4–U+05C5  Upper / lower dots
#   U+05C7         Qamats qatan
_WORD_RE = re.compile(
    r"[\u05D0-\u05EA\u05F0-\u05F4\uFB1D-\uFB4E"
    r"\u0591-\u05AF\u05B0-\u05BD\u05BF\u05C1\u05C2\u05C4\u05C5\u05C7]+"
)

# ── Nikud (vowel points) stripping ────────────────────────────────────────────
# Hebrew combining diacritical marks:
#   U+05B0–U+05BD  Vowel points (shva, hataf segol, hiriq, tsere, segol, …)
#   U+05BF         Rafe (softening mark)
#   U+05C1–U+05C2  Shin/sin dots
#   U+05C4–U+05C5  Upper/lower dots
#   U+05C7         Qamats qatan
# U+0591–U+05AF: Cantillation marks (te'amim) — included for Biblical texts.
_NIKUD_RE = re.compile(r"[\u0591-\u05AF\u05B0-\u05BD\u05BF\u05C1\u05C2\u05C4\u05C5\u05C7]")

# Confidence note — honest disclosure on every lesson card.
_CONFIDENCE_NOTE = (
    "Hebrew dictionary mode: no morphological analysis. "
    "Canonical form is the undiacritised surface token. "
    "Inseparable prefixes (ו-, ב-, ה-, ל-…) are not split from their host word."
)


def _strip_nikud(text: str) -> str:
    """Remove Hebrew nikud and cantillation marks for canonical normalisation."""
    return _NIKUD_RE.sub("", text)


class HebrewPlugin:
    """Hebrew starter — dictionary-mode plugin.

    Provides sentence splitting and whitespace tokenisation with nikud
    normalisation.  Capabilities honestly declare the pipeline depth.
    """

    language_code = "he"
    display_name  = "Hebrew (starter — dictionary mode)"
    direction     = "rtl"
    capabilities  = LanguageCapabilities(
        code="he",
        display_name="Hebrew (starter — dictionary mode)",
        direction="rtl",
        script_family="hebrew",
        tokenization_mode="whitespace",
        morphology_depth="none",
        lesson_modes_supported=["dictionary"],
        # v2 — honest quality declarations.
        analysis_depth="dictionary",
        segmentation_quality="low",    # regex heuristic; may mis-split on
                                       # abbreviations and ellipses.
        tokenization_quality="medium", # whitespace works for modern prose;
                                       # inseparable prefixes are not split.
        morphology_quality="none",
        syntax_support=False,
        idiom_detection=False,
        tts_lang_tag="he",             # browser TTS: modern Hebrew supported.
        transliteration_scheme=None,   # no romanisation in this iteration.
        nuance_capabilities=NuanceCapabilities(
            idioms="none",
            phrase_families="none",
            literary_references="none",
            cultural_references="none",
            etymology="none",
            formality_register="none",
            grammar_nuance="none",
            pronunciation_tts="stub",   # he TTS coverage varies by browser
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
        return [
            m.group(0).strip()
            for m in _SENTENCE_RE.finditer(text)
            if m.group(0).strip()
        ]

    def analyze_sentence(self, sentence: str) -> CandidateSentenceResult:
        candidates: list[CandidateObject] = []
        seen: set[str] = set()

        for word in _WORD_RE.findall(sentence):
            canonical = _strip_nikud(word)
            if not canonical or canonical in seen:
                continue
            seen.add(canonical)

            # Surface form may carry nikud (e.g. "סֵפֶר"); canonical form is
            # the undiacritised version ("ספר").  The lesson builder will
            # display "Base form: ספר" when they differ.
            lesson_data = {
                "lemma": canonical,
                "pos": "WORD",
                "confidence_note": _CONFIDENCE_NOTE,
            }

            if canonical in _A1:
                lesson_data["cefr_level"] = "A1"
                confidence: float | None = 0.70
            else:
                confidence = None

            candidates.append(
                CandidateObject(
                    canonical_form=canonical,
                    surface_form=word,
                    type="vocabulary",
                    label=word,
                    lesson_data=lesson_data,
                    confidence=confidence,
                )
            )

        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)


def create_plugin() -> HebrewPlugin:
    return HebrewPlugin()
