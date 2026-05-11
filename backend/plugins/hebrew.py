"""Hebrew plugin — dictionary mode with optional HebSpaCy morphology.

BCP-47 code "he", RTL direction, standard sentence punctuation.

What this plugin does reliably
──────────────────────────────
  - Sentence splitting on standard terminal punctuation and newlines.
  - Whitespace tokenisation (modern Hebrew prose is whitespace-delimited).
  - Nikud (vowel-point) stripping for canonical forms, so
    "סֵפֶר" and "ספר" resolve to the same canonical object.
  - Inseparable-prefix heuristic: ב-, ל-, מ-, כ-, ו-, ה-, ש- (and two-char
    combinations) are stripped to set lesson_data["prefix"] on each token.
    This fires the prefix_decomposition nuance signal without HebSpaCy.
  - Correct RTL / hebrew metadata for frontend rendering and font selection.
  - TTS tag "he" (browser SpeechSynthesis covers modern Hebrew).

When he_dep_ud_hybrid spaCy model is installed (optional)
──────────────────────────────────────────────────────────
  Rich vocabulary candidates gain: POS, binyan, tense, person, number,
  gender, verb_form, and construct state.  The nuance extractor (he.py)
  uses binyan + tense to fire the verb_template signal.

  Install the he_dep_ud_hybrid model via whatever channel the Hebrew NLP
  community provides; the adapter gates on spacy.load() succeeding.
    python -m spacy download he_dep_ud_hybrid

Known limitations
─────────────────
  • Heuristic prefix stripping has false positives for short words and some
    complete words that begin with a prefix letter (e.g. שלום, כי).
    HebSpaCy removes these.
  • Tokenisation quality is rated "medium" for standard prose.
"""
from __future__ import annotations

import re

from backend.morphology import he_adapter as _he_adapter
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
    display_name  = "Hebrew (dictionary foundations)"
    direction     = "rtl"
    capabilities  = LanguageCapabilities(
        code="he",
        display_name="Hebrew (dictionary foundations)",
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
            phrase_families="partial",  # 10-family curated catalog; extractor wired
            literary_references="none",
            cultural_references="none",
            etymology="none",
            formality_register="none",
            grammar_nuance="partial",   # definite_prefix + waw_conjunction + prefix_decomposition + biblical_register always; binyan/verb with HebSpaCy
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

        raw_tokens = _WORD_RE.findall(sentence)
        morph_tokens = _he_adapter.analyze_tokens(raw_tokens)

        for mt in morph_tokens:
            canonical = _strip_nikud(mt.text)
            if not canonical or canonical in seen:
                continue
            seen.add(canonical)

            lesson_data: dict = {
                "lemma": _strip_nikud(mt.lemma),
                "pos": mt.pos,
                "prefix": mt.prefix,
            }

            if mt.source == "heb_spacy":
                if mt.binyan:
                    lesson_data["binyan"] = mt.binyan
                if mt.tense:
                    lesson_data["tense"] = mt.tense
                if mt.person:
                    lesson_data["person"] = mt.person
                if mt.number:
                    lesson_data["number"] = mt.number
                if mt.gender:
                    lesson_data["gender"] = mt.gender
                if mt.verb_form:
                    lesson_data["verb_form"] = mt.verb_form
                if mt.construct:
                    lesson_data["construct"] = mt.construct
            else:
                lesson_data["confidence_note"] = _CONFIDENCE_NOTE

            if canonical in _A1:
                lesson_data["cefr_level"] = "A1"
                confidence: float | None = 0.70
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


def create_plugin() -> HebrewPlugin:
    return HebrewPlugin()
