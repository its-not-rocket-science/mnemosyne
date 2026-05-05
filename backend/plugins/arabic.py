"""Arabic starter plugin — dictionary mode.

BCP-47 code "ar", RTL direction, Arabic sentence punctuation.
This plugin provides NO morphological analysis — no CAMeL-Tools dependency.

What this plugin does reliably
──────────────────────────────
  - Sentence splitting on Arabic and standard terminal punctuation.
  - Whitespace tokenisation (Modern Standard Arabic is whitespace-delimited).
  - Tashkeel (diacritic / harakat) stripping for canonical forms, so
    "كَتَبَ" and "كتب" resolve to the same canonical object.
  - Correct RTL / arabic metadata for frontend rendering and font selection.
  - TTS tag "ar" (browser SpeechSynthesis covers MSA on major platforms).

What this plugin does NOT do
─────────────────────────────
  - Root extraction or pattern-based morphological analysis.
  - Part-of-speech tagging.
  - Lemmatisation beyond tashkeel normalisation.
  - Dialectal Arabic support (Egyptian, Gulf, Levantine, …).
  - Clitic segmentation (ال definite article, pronominal clitics, etc.).
  - Any claim about word meaning.

Upgrade path
────────────
  When CAMeL-Tools, Stanza-ar, or a comparable library is available as a
  dependency, this plugin can be promoted:
    tokenization_quality → high        (after adding clitic splitting)
    morphology_depth     → shallow     (after POS tagging)
    analysis_depth       → morphology_light
    lesson_modes_supported → ["vocabulary", "dictionary"]

Known limitations
─────────────────
  • Arabic proclitics (وَ "and-", بِ "in-", كَ "like-", لِ "for-") attach to
    the following word without a space in normal orthography.  Whitespace
    tokenisation will return the combined form as a single token; the clitic
    is not split off.
  • Tokenisation quality is rated "medium" for MSA prose.  Poetry, headlines,
    and dialectal text will have higher error rates.
  • Sentence splitting is a regex heuristic; Arabic discourse markers and
    run-on sentences may cause over- or under-splitting.
"""
from __future__ import annotations

import re

from backend.plugins.cefr_vocab import A1 as _CEFR_A1
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

_A1: frozenset[str] = _CEFR_A1.get("ar", frozenset())

# ── Sentence splitting ────────────────────────────────────────────────────────
# Split on standard terminal marks plus:
#   ؟  U+061F  Arabic question mark
#   ۔  U+06D4  Arabic full stop (used in Urdu/Pashto prose but also appears in
#               some Arabic texts)
# Newlines serve as an additional soft boundary.
_SENTENCE_RE = re.compile(r"[^.!?؟۔\n]+[.!?؟۔\n]?")

# ── Word tokenisation ─────────────────────────────────────────────────────────
# Match runs of Arabic *letters* and attached diacritical marks.  The broad
# U+0600–U+06FF block is NOT used wholesale because it contains Arabic
# punctuation (، U+060C, ؛ U+061B, ؟ U+061F), number signs, and Arabic-Indic
# digits (٠–٩, U+0660–U+0669) that must not be treated as word tokens.
#
# Ranges included:
#   U+0621–U+063A  Arabic consonants: ء through غ
#   U+0641–U+064A  Arabic consonants: ف through ي
#   U+064B–U+065F  Harakat (diacritical short-vowel marks)
#   U+0670         Arabic superscript alef (combining)
#   U+0671–U+06D3  Extended Arabic letters (alef wasla, special forms)
#   U+06D5         Arabic letter ae
#   U+0750–U+077F  Arabic Supplement (additional letters)
#   U+FB50–U+FDFF  Arabic Presentation Forms-A (ligatures)
#   U+FE70–U+FEFF  Arabic Presentation Forms-B (more ligatures)
_WORD_RE = re.compile(
    r"[\u0621-\u063A"
    r"\u0641-\u065F"
    r"\u0670-\u06D3"
    r"\u06D5"
    r"\u0750-\u077F"
    r"\uFB50-\uFDFF"
    r"\uFE70-\uFEFF]+"
)

# ── Tashkeel / harakat stripping ──────────────────────────────────────────────
# Arabic combining diacritical marks used to represent short vowels and
# other phonemic features (fathatan, dammatan, kasratan, fatha, damma,
# kasra, shadda, sukun, and a handful of rarer marks through U+065F).
# U+0670 (superscript alef / alef waslah) is also a combining mark.
# These marks are optional in normal prose — stripping them yields the
# undiacritised orthography used for canonicalisation.
_TASHKEEL_RE = re.compile(r"[\u064B-\u065F\u0670]")

# Confidence note shown in every lesson card — informs the learner honestly.
_CONFIDENCE_NOTE = (
    "Arabic dictionary mode: no morphological analysis. "
    "Canonical form is the undiacritised surface token. "
    "Clitic prefixes (ال, وَ, بِ…) are not split from their host word."
)


def _strip_tashkeel(text: str) -> str:
    """Remove Arabic diacritical marks for canonical normalisation."""
    return _TASHKEEL_RE.sub("", text)


class ArabicPlugin:
    """Arabic starter — dictionary-mode plugin.

    Provides sentence splitting and whitespace tokenisation with tashkeel
    normalisation.  Capabilities honestly declare the pipeline depth.
    """

    language_code = "ar"
    display_name  = "Arabic (starter — dictionary mode)"
    direction     = "rtl"
    capabilities  = LanguageCapabilities(
        code="ar",
        display_name="Arabic (starter — dictionary mode)",
        direction="rtl",
        script_family="arabic",
        tokenization_mode="whitespace",
        morphology_depth="none",
        lesson_modes_supported=["dictionary"],
        # v2 — honest quality declarations.
        analysis_depth="dictionary",
        segmentation_quality="low",    # regex heuristic; discourse markers and
                                       # run-on sentences may cause errors.
        tokenization_quality="medium", # whitespace works well for MSA prose;
                                       # clitics and dialectal contractions
                                       # are not split.
        morphology_quality="none",
        syntax_support=False,
        idiom_detection=False,
        tts_lang_tag="ar",             # browser TTS: MSA widely supported.
        transliteration_scheme=None,   # no romanisation in this iteration.
        nuance_capabilities=NuanceCapabilities(
            idioms="none",
            phrase_families="none",
            literary_references="none",
            cultural_references="none",
            etymology="none",
            formality_register="none",
            grammar_nuance="none",
            pronunciation_tts="stub",   # ar TTS coverage varies by browser
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
            canonical = _strip_tashkeel(word)
            if not canonical or canonical in seen:
                continue
            seen.add(canonical)

            # Surface form may carry tashkeel (e.g. "كَتَبَ"); canonical
            # form is the undiacritised version ("كتب").  The lesson builder
            # will display "Base form: كتب" when they differ.
            lesson_data: dict = {
                "lemma": canonical,
                "confidence_note": "Prefix/clitic segmentation is heuristic; attached prefixes may not always be separated correctly."
            }
            if canonical in _A1:
                lesson_data["cefr_level"] = "A1"
                confidence: float | None = 0.70
            else:
                lesson_data["confidence_note"] = _CONFIDENCE_NOTE
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


def create_plugin() -> ArabicPlugin:
    return ArabicPlugin()
