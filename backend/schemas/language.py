"""Language capability metadata.

``LanguageCapabilities`` is the single authoritative description of what a
language plugin can do.  It is declared on the plugin as a class attribute,
read by the registry, and exposed through GET /languages so the frontend can
adapt its rendering and the lesson builder can choose the right template.

Capability fields
─────────────────
direction
    "ltr" or "rtl".  Applied to sentence-card text and pill containers in the
    frontend via ``dir`` attributes.

script_family
    Broad script category.  Used by the frontend to choose an appropriate font
    stack and by the lesson builder when deciding label strings.  Not a
    complete Unicode script classification — just enough to drive the two main
    rendering decisions (font choice, character orientation).

tokenization_mode
    How the language's text is broken into tokens before NLP analysis:

    whitespace  — spaces or punctuation delimit words.  Standard for Latin,
                  Cyrillic, Arabic, Hebrew, etc.  ``text.split()`` gives a
                  meaningful word count.
    segmented   — no inter-word spaces; an NLP model segments the stream into
                  words (Mandarin, Japanese, Thai, Burmese, Khmer).
                  ``text.split()`` is meaningless; difficulty scoring should
                  use object count or NLP-derived token count instead.
    character   — each character is independently meaningful (classical CJK
                  annotation mode, some historic scripts).

morphology_depth
    The depth of morphological analysis the plugin provides:

    none     — vocabulary lookup only; no POS or inflection analysis.
    shallow  — lemmatisation + POS tagging; no full paradigm extraction.
    rich     — full morpheme analysis (tense, mood, person, number, case, etc.)

lesson_modes_supported
    Ordered list (best first) of lesson modes the plugin's extractions support.
    The lesson builder picks the first mode that matches the available data.

    morphology  — full conjugation/agreement/tense drills (requires rich or
                  shallow morphology_depth).
    vocabulary  — lemma + POS drills; no morphological breakdown.
    dictionary  — word + gloss only; used when the plugin cannot provide POS.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TokenizationMode = Literal["whitespace", "segmented", "character"]
MorphologyDepth  = Literal["none", "shallow", "rich"]
ScriptFamily     = Literal["latin", "arabic", "hebrew", "cjk", "devanagari", "cyrillic", "other"]
LessonMode       = Literal["morphology", "vocabulary", "dictionary"]

_LESSON_MODE_RANK: dict[LessonMode, int] = {
    "morphology": 2,
    "vocabulary": 1,
    "dictionary": 0,
}


class LanguageCapabilities(BaseModel):
    """All frontend-visible and lesson-builder-visible properties of a plugin."""

    code: str = Field(description="BCP-47 language tag, e.g. 'es'")
    display_name: str
    direction: Literal["ltr", "rtl"]
    script_family: ScriptFamily
    tokenization_mode: TokenizationMode
    morphology_depth: MorphologyDepth
    lesson_modes_supported: list[LessonMode] = Field(
        description="Ordered best-first list of lesson modes this plugin supports.",
        min_length=1,
    )


def best_lesson_mode(supported: list[LessonMode]) -> LessonMode:
    """Return the richest lesson mode from a plugin's supported list.

    Falls back to 'dictionary' if the list is empty or contains unknown values.
    """
    if not supported:
        return "dictionary"
    return max(supported, key=lambda m: _LESSON_MODE_RANK.get(m, -1))
