"""Structured lesson and drill schemas.

Lessons are typed, structured objects — not markdown strings — so the
frontend can render each drill type with the appropriate interactive
widget.

Drill types
───────────
  multiple_choice  Prompt + shuffled options.  ``answer_index`` is the
                   index of the correct option in ``options``.
  fill_blank       A sentence with a blank (___).  ``answer`` is the
                   expected response (compared case-insensitively).
  recognition      A claim about the item.  ``correct`` is the ground
                   truth (True = the claim is accurate).
  shadowing        Text for the learner to read aloud; no graded
                   response.

NOTE: ``answer_index``, ``answer``, and ``correct`` are sent to the
client.  This is intentional for a self-study tool — the learner
reveals answers to check their own recall.  A future server-graded mode
would omit these fields from the response.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from backend.schemas.language import LessonMode
from backend.schemas.parse import LearnableType

# ── Lesson template type ──────────────────────────────────────────────────────

LessonTemplate = Literal[
    # Richness-level templates — also used in LanguageCapabilities.lesson_modes_supported
    "morphology",      # full morphological drills (conjugation, agreement, tense)
    "vocabulary",      # lemma + POS; no morphological breakdown
    "dictionary",      # word + gloss only

    # Object-type-specific templates — used only in LessonResponse.lesson_mode;
    # never appear in lesson_modes_supported on LanguageCapabilities.
    "idiom",           # fixed-form idiomatic expression
    "phrase_family",   # variant-aware phrase family with confusables
    "script",          # character / sign lesson (CJK kanji, Arabic letter, …)
    "transliteration", # native-form ↔ romanization / phonetic mapping
]
"""Lesson template type.

Reported in ``LessonResponse.lesson_mode`` to tell the frontend which kind of
lesson was generated.  A superset of ``LessonMode`` — the extra values
(``"idiom"``, ``"script"``, ``"transliteration"``) identify object-type-specific
templates that bypass the richness-level selection entirely.

``LessonMode`` (the input to ``build_lesson``) governs *richness*;
``LessonTemplate`` (the output on ``LessonResponse``) describes the *actual
template used*, which may differ when a dedicated builder was invoked.
"""


class LessonField(BaseModel):
    """One fact about a learnable object, rendered as a key-value row."""
    label: str
    value: str


class MultipleChoiceDrill(BaseModel):
    type: Literal["multiple_choice"]
    prompt: str
    options: list[str]          # deterministically shuffled
    answer_index: int           # index into options


class FillBlankDrill(BaseModel):
    type: Literal["fill_blank"]
    prompt: str                 # contains ___ where the blank is
    answer: str                 # expected response (case-insensitive match)
    hint: str | None = None


class RecognitionDrill(BaseModel):
    type: Literal["recognition"]
    statement: str              # claim to evaluate
    correct: bool               # True = statement is accurate


class ShadowingDrill(BaseModel):
    type: Literal["shadowing"]
    text: str                   # text to read aloud


# Pydantic v2 discriminated union — serialises/deserialises via "type" field.
Drill = Annotated[
    MultipleChoiceDrill | FillBlankDrill | RecognitionDrill | ShadowingDrill,
    Field(discriminator="type"),
]




class PracticeActivity(BaseModel):
    type: Literal[
        "comprehension_questions",
        "sentence_level_vocabulary_recall",
        "cloze_completion",
        "term_to_meaning_matching",
        "sentence_recombination",
        "transformation_drills",
        "short_retell_prompts",
        "notice_the_pattern",
    ]
    language: str
    difficulty: str
    target_term_or_pattern: str
    prompt: str
    expected_answer: str
    acceptable_alternatives: list[str] = Field(default_factory=list)
    feedback_text: str
class LessonResponse(BaseModel):
    """Structured lesson returned by GET /lesson/{object_id}.

    Replaces the old ``content_markdown`` string.  All fields are
    deterministically derived from the canonical object's stored
    ``lesson_data``; no LLM or external call is needed.

    ``lesson_mode`` reflects the *template* used to generate this lesson.
    For most objects this matches the richness level requested (morphology /
    vocabulary / dictionary).  For idiom, script, and transliteration objects
    the dedicated builder always runs regardless of the requested mode, and
    ``lesson_mode`` reports the actual template.

    The frontend can use ``lesson_mode`` to select drill widgets:
    - ``"morphology"``      — morphological drills (MC for tense/mood, fill-blank)
    - ``"vocabulary"``      — POS recognition + shadowing
    - ``"dictionary"``      — shadowing only
    - ``"idiom"``           — meaning fill-blank + register MC
    - ``"phrase_family"``   — canonical form, variants, confusables, origin + recognition drills
    - ``"script"``          — reading fill-blank + meaning fill-blank
    - ``"transliteration"`` — bidirectional romanization fill-blank

    New optional fields (``language_code``, ``script_direction``) are set
    when a ``LessonContext`` is provided to ``build_lesson()``.  They are
    ``None`` for lessons built without language context (e.g. in tests that
    do not pass a context).
    """
    id: str
    type: LearnableType
    lesson_mode: LessonTemplate = "morphology"
    title: str
    explanation: str                    # one human-readable sentence
    fields: list[LessonField]           # key-value fact rows
    examples: list[str]                 # surface forms for TTS / display
    drills: list[Drill]                 # ordered practice items

    # ── Language context — optional, populated when context is provided ───────
    language_code: str | None = None
    """BCP-47 language code for this lesson (e.g. ``"es"``).
    ``None`` when built without a ``LessonContext``."""

    script_direction: Literal["ltr", "rtl"] | None = None
    """Text direction for the target language.  ``None`` when unknown."""

    lesson_data: dict[str, Any] | None = None
    practice_activities: list[PracticeActivity] = Field(default_factory=list)
    """Raw lesson_data dict from the canonical object row.

    Passed through so the frontend can access fields that are not
    promoted to top-level schema fields (e.g. ``matched_variant``,
    ``canonical_form``, ``lemma``, ``origin``, ``variants``).
    """
