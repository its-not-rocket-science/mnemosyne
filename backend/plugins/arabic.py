"""Arabic plugin — dictionary mode with optional CAMeL Tools morphology.

BCP-47 code "ar", RTL direction, Arabic sentence punctuation.

What this plugin does reliably
──────────────────────────────
  - Sentence splitting on Arabic and standard terminal punctuation.
  - Whitespace tokenisation (Modern Standard Arabic is whitespace-delimited).
  - Tashkeel (diacritic / harakat) stripping for canonical forms, so
    "كَتَبَ" and "كتب" resolve to the same canonical object.
  - Correct RTL / arabic metadata for frontend rendering and font selection.
  - TTS tag "ar" (browser SpeechSynthesis covers MSA on major platforms).

When camel-tools is installed (optional)
─────────────────────────────────────────
  Rich vocabulary candidates gain: POS, root, pattern, gloss, voice, aspect,
  mood, and proclitic fields (prc0/1/2).  The nuance extractor (ar.py) uses
  these to fire root_pattern, verb_form, and proclitic signals.

  Installation:
    pip install camel-tools
    camel_data -i morphology-db-msa-r13

Without camel-tools
───────────────────
  Vocabulary candidates carry only lemma (= undiacritised surface form).
  The nuance extractor still fires definite_article and negation signals.

Known limitations
─────────────────
  • Arabic proclitics (وَ "and-", بِ "in-", كَ "like-", لِ "for-") attach to
    the following word without a space in normal orthography.  Without CAMeL
    Tools, the combined form is returned as a single token.
  • Tokenisation quality is rated "medium" for MSA prose.
  • Sentence splitting is a regex heuristic; discourse markers and run-on
    sentences may cause over- or under-splitting.
"""
from __future__ import annotations

import re

from backend.morphology import ar_adapter as _ar_adapter
from backend.plugins.cefr_vocab import A1 as _CEFR_A1, A2 as _CEFR_A2, B1 as _CEFR_B1
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

_A1: frozenset[str] = _CEFR_A1.get("ar", frozenset())
_A2: frozenset[str] = _CEFR_A2.get("ar", frozenset())
_B1: frozenset[str] = _CEFR_B1.get("ar", frozenset())

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
    display_name  = "Arabic (dictionary foundations)"
    direction     = "rtl"
    capabilities  = LanguageCapabilities(
        code="ar",
        display_name="Arabic (dictionary foundations)",
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
            phrase_families="partial",  # 10-family curated catalog; extractor wired
            literary_references="none",
            cultural_references="none",
            etymology="none",
            formality_register="none",
            grammar_nuance="partial",   # definite_article + 5 negation particles always; root/verb/proclitic with CAMeL
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

        raw_tokens = _WORD_RE.findall(sentence)
        morph_tokens = _ar_adapter.analyze_tokens(raw_tokens)

        for mt in morph_tokens:
            # canonical = undiacritised surface form (same logic as before)
            canonical = _strip_tashkeel(mt.text)
            if not canonical or canonical in seen:
                continue
            seen.add(canonical)

            lesson_data: dict = {
                # Strip tashkeel from CAMeL lemma too for consistency
                "lemma": _strip_tashkeel(mt.lemma),
            }

            if mt.source == "camel_tools":
                lesson_data["pos"] = mt.pos
                if mt.root:
                    lesson_data["root"] = mt.root
                if mt.pattern:
                    lesson_data["pattern"] = mt.pattern
                if mt.gloss:
                    lesson_data["gloss"] = mt.gloss
                if mt.voice:
                    lesson_data["voice"] = mt.voice
                if mt.aspect:
                    lesson_data["aspect"] = mt.aspect
                if mt.mood:
                    lesson_data["mood"] = mt.mood
                if mt.prc0:
                    lesson_data["prc0"] = mt.prc0
                if mt.prc1:
                    lesson_data["prc1"] = mt.prc1
                if mt.prc2:
                    lesson_data["prc2"] = mt.prc2
            else:
                lesson_data["confidence_note"] = _CONFIDENCE_NOTE

            if canonical in _A1:
                lesson_data["cefr_level"] = "A1"
                confidence: float | None = 0.70
            elif canonical in _A2:
                lesson_data["cefr_level"] = "A2"
                confidence = 0.70
            elif canonical in _B1:
                lesson_data["cefr_level"] = "B1"
                confidence = 0.70
            else:
                confidence = None

            candidates.append(
                CandidateObject(
                    canonical_form=canonical,
                    surface_form=mt.text,
                    type="vocabulary",
                    label=mt.text,
                    lesson_data=lesson_data,
                    confidence=confidence,
                )
            )

        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)


def create_plugin() -> ArabicPlugin:
    return ArabicPlugin()
