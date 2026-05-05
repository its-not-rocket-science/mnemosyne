"""Language capability metadata.

``LanguageCapabilities`` is the single authoritative description of what a
language plugin can do.  It is declared on the plugin as a class attribute,
read by the registry, and exposed through GET /languages so the frontend can
adapt its rendering and the lesson builder can choose the right template.

Plugin Interface versioning
───────────────────────────
v1 fields (all required, set at launch):
    code, display_name, direction, script_family,
    tokenization_mode, morphology_depth, lesson_modes_supported

v2 fields (all optional / defaulted — existing plugins compile unchanged):
    analysis_depth, segmentation_quality, tokenization_quality,
    morphology_quality, syntax_support, idiom_detection,
    tts_lang_tag, transliteration_scheme,
    tense_pool, mood_pool

v3 fields (all optional / defaulted):
    nuance_capabilities — NuanceCapabilities sub-model with 11 per-dimension
    coverage ratings.  None means the plugin has not declared coverage yet;
    the frontend treats it the same as all-"none".

The backward-compatibility rule is strict: adding a field to this class
requires a default value so plugins that declare ``LanguageCapabilities(...)``
with only the v1 fields continue to load without error.

────────────────────────────────────────────────────────────────────────────

v1 field reference
──────────────────
direction
    "ltr" or "rtl".  Applied as ``dir=`` on sentence-card text in the frontend.

script_family
    Broad script category for font selection and rendering decisions:
    "latin" | "arabic" | "hebrew" | "cjk" | "devanagari" | "cyrillic" | "other"

tokenization_mode
    whitespace  — spaces/punctuation delimit tokens (Latin, Arabic, Hebrew, …).
                  ``text.split()`` gives a meaningful word count.
    segmented   — no inter-word spaces; an NLP model must segment (CJK, Thai, …).
                  ``text.split()`` is meaningless.
    character   — each character is independently meaningful (classical CJK
                  annotation mode, some historic scripts).

morphology_depth
    none     — vocabulary lookup only; no POS or inflection analysis.
    shallow  — lemmatisation + POS tagging; no full paradigm extraction.
    rich     — full morpheme analysis (tense, mood, person, number, case, …).

lesson_modes_supported
    Richest-first list of lesson modes the plugin's extractions can drive:
    morphology  — full conjugation/agreement/tense drills.
    vocabulary  — lemma + POS drills; no morphological breakdown.
    dictionary  — word + gloss only.

────────────────────────────────────────────────────────────────────────────

v2 field reference (Plugin Interface 2.0)
─────────────────────────────────────────
analysis_depth
    Overall pipeline depth — what the plugin attempts:

    full              — full NLP: segmentation + tokenization + POS +
                        morphology + dependency parse + optional idioms.
                        Typical for spaCy-backed plugins (Spanish).
    morphology_light  — segmentation + tokenization + POS + basic morphology;
                        no syntax tree, no idiom detection.
    dictionary        — segmentation + tokenization + lemma lookup; no
                        morphological inference from context.
    segmentation_only — segmentation + tokenization only; no linguistic
                        analysis (returns vocabulary candidates with just the
                        surface/canonical form and no lesson_data).

segmentation_quality, tokenization_quality, morphology_quality
    Quality indicator for each analysis stage:
    high    — accurate, reliable across most inputs.
    medium  — mostly reliable; known gaps for OOV words, edge cases.
    low     — heuristic / regex-based; significant error rate.
    none    — this stage is not performed.

syntax_support
    True when the plugin provides syntactic role information (dependency
    parse, subject/object identification, etc.).  Used to enable syntactic
    learning objects in future types.

idiom_detection
    True when the plugin can extract multi-word idiomatic expressions as
    "idiom" type objects.

tts_lang_tag
    BCP-47 language tag to use for TTS (Web Speech API / SpeechSynthesis).
    None means "use the plugin's own code field".  Provide a value when the
    analysis code and the TTS locale differ (e.g. zh-CN vs zh-TW) or when
    a specific regional accent is preferred.

transliteration_scheme
    Name of the transliteration scheme this plugin uses when emitting
    "transliteration" type objects:
    None                — no transliteration support.
    "hepburn_romaji"    — standard Hepburn romanization for Japanese.
    "pinyin_tone_marks" — Mandarin pinyin with diacritical tone marks.
    "pinyin_tone_nums"  — Mandarin pinyin with numeric tone suffix.
    "ipa"               — International Phonetic Alphabet.
    Any other string is accepted; these are communicative labels, not
    controlled vocabulary at the protocol level.

────────────────────────────────────────────────────────────────────────────

v3 field reference (Plugin Interface 3.0)
─────────────────────────────────────────
nuance_capabilities
    A NuanceCapabilities object rating 11 semantic dimensions on a
    five-level scale: "none" | "stub" | "partial" | "strong" | "gold".

    none    — feature is not implemented at all.
    stub    — present in code but coverage is superficial or very narrow.
    partial — meaningful coverage with known gaps.
    strong  — reliable across typical inputs; only edge cases missing.
    gold    — production-quality; near-comprehensive coverage.

    Dimensions:
        idioms                        — multi-word idiomatic expressions.
        phrase_families               — collocations and related phrase groups.
        literary_references           — allusions to named literary works.
        cultural_references           — culture-specific concepts and references.
        etymology                     — word origin and historical form info.
        formality_register            — formal / informal / honorific awareness.
        grammar_nuance                — subtle grammatical distinctions (aspect,
                                        mood, case agreement, etc.).
        pronunciation_tts             — text-to-speech pronunciation quality.
        transliteration               — romanization / script-conversion support.
        proverb_tradition             — proverbs and traditional sayings.
        classical_or_scriptural_allusion — allusions to classical or scriptural
                                        texts (Bible, Quran, Homer, etc.).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── v1 types ──────────────────────────────────────────────────────────────────

TokenizationMode = Literal["whitespace", "segmented", "character"]
MorphologyDepth  = Literal["none", "shallow", "rich"]
ScriptFamily     = Literal["latin", "arabic", "hebrew", "cjk", "devanagari", "cyrillic", "greek", "other"]
LessonMode       = Literal["morphology", "vocabulary", "dictionary"]

# ── v2 types ──────────────────────────────────────────────────────────────────

AnalysisDepth = Literal[
    "full",              # full NLP pipeline (spaCy-class)
    "morphology_light",  # POS + basic morphology, no syntax
    "dictionary",        # lemma lookup only
    "segmentation_only", # segmentation + tokenization only
]

QualityLevel = Literal[
    "high",    # accurate and reliable
    "medium",  # mostly reliable; known gaps
    "low",     # heuristic; significant error rate
    "none",    # this stage is not performed
]

# ── v3 types ──────────────────────────────────────────────────────────────────

NuanceCoverageLevel = Literal["none", "stub", "partial", "strong", "gold"]


class NuanceCapabilities(BaseModel):
    """Per-dimension nuance coverage ratings for a language plugin.

    Each field rates one semantic capability on a five-level scale.
    The default for all fields is ``"none"`` so that a plugin that
    does not yet declare nuance capabilities degrades gracefully.
    """

    idioms:                          NuanceCoverageLevel = "none"
    phrase_families:                 NuanceCoverageLevel = "none"
    literary_references:             NuanceCoverageLevel = "none"
    cultural_references:             NuanceCoverageLevel = "none"
    etymology:                       NuanceCoverageLevel = "none"
    formality_register:              NuanceCoverageLevel = "none"
    grammar_nuance:                  NuanceCoverageLevel = "none"
    pronunciation_tts:               NuanceCoverageLevel = "none"
    transliteration:                 NuanceCoverageLevel = "none"
    proverb_tradition:               NuanceCoverageLevel = "none"
    classical_or_scriptural_allusion: NuanceCoverageLevel = "none"
    notes: str | None = None


# ── Lesson-mode ranking ───────────────────────────────────────────────────────

_LESSON_MODE_RANK: dict[LessonMode, int] = {
    "morphology": 2,
    "vocabulary": 1,
    "dictionary": 0,
}


# ── Capabilities model ────────────────────────────────────────────────────────

class LanguageCapabilities(BaseModel):
    """All frontend-visible and lesson-builder-visible properties of a plugin.

    Backward compatibility guarantee: all v2 fields carry defaults.  A plugin
    that constructs ``LanguageCapabilities`` with only v1 positional / keyword
    arguments will continue to load without modification.  The defaults are
    deliberately conservative (``analysis_depth="dictionary"``, all quality
    indicators at ``"none"`` or ``False``) so unknown plugins degrade to the
    safest lesson template rather than claiming capabilities they may lack.
    """

    # ── v1 fields (required) ──────────────────────────────────────────────────

    code: str = Field(description="BCP-47 language tag, e.g. 'es'")
    display_name: str
    direction: Literal["ltr", "rtl"]
    script_family: ScriptFamily
    tokenization_mode: TokenizationMode
    morphology_depth: MorphologyDepth
    lesson_modes_supported: list[LessonMode] = Field(
        description="Richest-first list of lesson modes this plugin supports.",
        min_length=1,
    )

    # ── v2 fields (defaulted — backward-compatible) ───────────────────────────

    analysis_depth: AnalysisDepth = "dictionary"
    """Overall pipeline depth the plugin implements.  See module docstring."""

    segmentation_quality: QualityLevel = "medium"
    """Reliability of sentence boundary detection."""

    tokenization_quality: QualityLevel = "medium"
    """Reliability of word / morpheme tokenization."""

    morphology_quality: QualityLevel = "none"
    """Reliability of morphological analysis (tense, mood, person, …)."""

    syntax_support: bool = False
    """True when the plugin provides syntactic role / dependency information."""

    idiom_detection: bool = False
    """True when the plugin can extract multi-word idiomatic expressions."""

    tts_lang_tag: str | None = None
    """BCP-47 tag for TTS.  None means use ``code``.  See module docstring."""

    transliteration_scheme: str | None = None
    """Transliteration scheme name, or None if not supported.
    E.g. "hepburn_romaji", "pinyin_tone_marks", "ipa"."""

    tense_pool: list[str] | None = None
    """Language-specific tense labels used as multiple-choice drill options.

    When set, the lesson builder uses this pool instead of the global English
    default so wrong-answer options are grammatically appropriate for the
    language.  Should include all tense values the plugin emits (from its
    ``_TENSE_DISPLAY`` dict) plus a few plausible distractors.
    Set to ``None`` to fall back to the built-in pool."""

    mood_pool: list[str] | None = None
    """Language-specific mood labels used as multiple-choice drill options.

    Same semantics as ``tense_pool``.  Set to ``None`` to fall back to the
    built-in pool."""

    # ── v3 fields (defaulted — backward-compatible) ───────────────────────────

    nuance_capabilities: NuanceCapabilities | None = None
    """Per-dimension nuance coverage.  None means the plugin has not yet
    declared coverage; the frontend treats it as all-"none"."""


# ── Helpers ───────────────────────────────────────────────────────────────────

def best_lesson_mode(supported: list[LessonMode]) -> LessonMode:
    """Return the richest lesson mode from a plugin's supported list.

    Falls back to ``"dictionary"`` if the list is empty or contains
    unrecognised values.
    """
    if not supported:
        return "dictionary"
    return max(supported, key=lambda m: _LESSON_MODE_RANK.get(m, -1))


def tts_tag_for(caps: LanguageCapabilities) -> str:
    """Return the BCP-47 tag to use for TTS for this language.

    If ``tts_lang_tag`` is set on the capabilities object that value is
    used; otherwise the plugin's own ``code`` field is the fallback.
    """
    return caps.tts_lang_tag if caps.tts_lang_tag is not None else caps.code
