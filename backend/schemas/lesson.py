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

Morphology extensions (backwards-compatible — all default to empty list)
─────────────────────────────────────────────────────────────────────────
  morphology_axes          One entry per active morphological dimension.
  paradigms                Partial or full paradigm tables.
  equivalents              Alternative constructions / paraphrases.
  contrasts                Notes distinguishing similar forms.
  encountered_vocabulary   Vocabulary items present in context sentence(s).
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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


class DiscriminationDrill(BaseModel):
    """A meaning-discrimination drill: learner identifies the semantic or pragmatic
    difference between two forms, sentences, or structures.

    Designed to teach *why* native speakers choose one form instead of another —
    not just which form is grammatically correct.
    """
    type: Literal["discrimination"]
    concept: str
    """Machine-readable concept ID (e.g. ``"preterite_vs_imperfect"``)."""
    dimension: str
    """Discriminating axis: ``"temporal"``, ``"aspect"``, ``"register"``,
    ``"certainty"``, ``"implication"``, ``"formality"``, ``"information_structure"``."""
    sentence_a: str
    """First candidate sentence or form."""
    sentence_b: str
    """Second candidate sentence or form."""
    question: str
    """What the learner should identify (e.g. ``"Which describes a completed action?"``).
    Phrased as an interpretive question, not a grammar label."""
    answer: Literal["a", "b"]
    """Which sentence best illustrates the stated dimension."""
    label_a: str | None = None
    """Brief semantic label for sentence A (e.g. ``"completed event"``)."""
    label_b: str | None = None
    """Brief semantic label for sentence B (e.g. ``"habitual past"``)."""
    explanation: str = ""
    """Full prose explanation revealed after the learner responds."""
    cefr_level: str | None = None


# Pydantic v2 discriminated union — serialises/deserialises via "type" field.
Drill = Annotated[
    MultipleChoiceDrill | FillBlankDrill | RecognitionDrill | ShadowingDrill | DiscriminationDrill,
    Field(discriminator="type"),
]




# ── Morphology extension models ───────────────────────────────────────────────
# All fields are optional / defaulted so existing lesson payloads remain valid.


class MorphologyAxis(BaseModel):
    """A single morphological dimension and its value for the item under study.

    Examples::

        MorphologyAxis(axis="tense",  value="present",     label="Present")
        MorphologyAxis(axis="mood",   value="indicative",  label="Indicative")
        MorphologyAxis(axis="person", value="1",           label="First person")
    """
    axis: str
    """Morphological axis name (e.g. ``"tense"``, ``"mood"``, ``"case"``)."""
    value: str
    """Axis value (e.g. ``"present"``, ``"indicative"``, ``"nominative"``)."""
    label: str | None = None
    """Display label for the value, suitable for a key-value row."""
    gloss: str | None = None
    """Brief human-readable explanation of what this value means."""


class ParadigmCell(BaseModel):
    """One cell in a morphological paradigm table."""
    form: str
    """Inflected surface form for this cell."""
    axes: dict[str, str] = Field(default_factory=dict)
    """Axis → value mapping that locates this cell in the table.
    Example: ``{"person": "1", "number": "singular"}``."""
    is_highlighted: bool = False
    """``True`` when this cell represents the form currently being studied."""
    gloss: str | None = None
    """Brief translation or meaning hint for this cell."""


class MorphologyParadigm(BaseModel):
    """A partial or full paradigm table for the item under study.

    Plugins emit one paradigm per relevant inflectional dimension group
    (e.g. one table for present active, another for aorist passive).
    """
    title: str | None = None
    """Human-readable title, e.g. ``"Present Indicative Active"``."""
    row_axis: str | None = None
    """Axis name used as table rows (e.g. ``"person"``)."""
    col_axis: str | None = None
    """Axis name used as table columns (e.g. ``"number"``)."""
    cells: list[ParadigmCell] = Field(default_factory=list)
    """All cells in row-major order."""


class EquivalentConstruction(BaseModel):
    """An equivalent way to express the same meaning or grammatical function.

    Used to show learners that multiple valid forms exist — e.g. the
    Spanish *estar* + gerund alongside the simple present for ongoing
    actions, or the Latin periphrastic future alongside the synthetic form.
    """
    model_config = ConfigDict(populate_by_name=True)

    construction: str
    """The equivalent form or construction string."""
    language_code: str | None = None
    """BCP-47 code when the equivalent is drawn from another language;
    ``None`` = same language as the lesson."""
    note: str | None = None
    """When or why to use this construction."""
    usage_register: str | None = Field(None, alias="register")
    """Stylistic register: ``"formal"``, ``"informal"``, ``"colloquial"``, …"""


class ContrastNote(BaseModel):
    """A note contrasting two similar forms to prevent common confusions."""
    form_a: str
    """First form — typically the item under study."""
    form_b: str
    """Second form — the one commonly confused with *form_a*."""
    note: str
    """What distinguishes *form_a* from *form_b*."""
    example_a: str | None = None
    """Example sentence using *form_a*."""
    example_b: str | None = None
    """Example sentence using *form_b*."""


class EncounteredVocabularySummary(BaseModel):
    """A vocabulary item that appeared in the context sentence(s) for this lesson.

    Populated when the lesson generator has access to the surrounding text
    and the vocabulary layer is enabled.  Deliberately lightweight: just
    enough for a hover-card or margin gloss, not a full lesson.
    """
    form: str
    """Surface form as it appeared in context."""
    lemma: str | None = None
    """Dictionary / citation form."""
    gloss: str | None = None
    """Brief meaning in the UI language."""
    pos: str | None = None
    """Part of speech tag (e.g. ``"NOUN"``, ``"VERB"``)."""
    is_high_frequency: bool = False
    """``True`` when the word is in the top-1 000 most frequent for this language."""


# ── Nuance discrimination models ─────────────────────────────────────────────


class NuancePair(BaseModel):
    """One minimal pair for meaning discrimination.

    Two sentences that differ by a single grammatical choice, accompanied by
    a question, labels, and an explanation that reveals the semantic stake.
    """
    sentence_a: str
    sentence_b: str
    label_a: str | None = None
    """Brief semantic label for sentence A (e.g. ``"completed event"``)."""
    label_b: str | None = None
    """Brief semantic label for sentence B (e.g. ``"habitual past"``)."""
    question: str
    """Interpretive prompt: what to observe, not a grammar label."""
    answer: Literal["a", "b"]
    """Which sentence best illustrates the stated dimension."""
    dimension: str
    """Discriminating axis (``"temporal"``, ``"aspect"``, ``"certainty"``, …)."""
    explanation: str
    """Full prose explanation revealed after the learner responds."""
    cefr_level: str | None = None


class NuanceSet(BaseModel):
    """A curated cluster of minimal pairs teaching one grammatical distinction.

    Groups two or more ``NuancePair`` instances around a single concept
    (e.g. *preterite vs imperfect*).  Rendered as an exploratory, non-quiz
    section in the lesson UI so learners can compare sentences and develop
    intuition about *why* native speakers choose one form instead of another.
    """
    concept: str
    """Machine-readable concept ID (e.g. ``"preterite_vs_imperfect"``)."""
    title: str
    """Display title (e.g. ``"Preterite vs Imperfect"``)."""
    dimension: str
    """Primary discriminating axis for this set."""
    description: str
    """One sentence that explains the distinction for the learner."""
    cefr_level: str = "B1"
    grammar_concept: str | None = None
    """Optional link to a ``GrammarRule.name`` for cross-referencing."""
    pairs: list[NuancePair] = Field(default_factory=list)


# ── Practice activities ───────────────────────────────────────────────────────


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
        "chunk_recall",
        "grammar_discrimination",
        "constrained_free_production",
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
    """Raw lesson_data dict from the canonical object row.

    Passed through so the frontend can access fields that are not
    promoted to top-level schema fields (e.g. ``matched_variant``,
    ``canonical_form``, ``lemma``, ``origin``, ``variants``).
    """
    practice_activities: list[PracticeActivity] = Field(default_factory=list)

    # ── Morphology extensions — all optional, default to empty list ───────────
    morphology_axes: list[MorphologyAxis] = Field(default_factory=list)
    """Active morphological dimensions for the item under study."""

    paradigms: list[MorphologyParadigm] = Field(default_factory=list)
    """Partial or full paradigm tables."""

    equivalents: list[EquivalentConstruction] = Field(default_factory=list)
    """Alternative constructions or paraphrases expressing the same meaning."""

    contrasts: list[ContrastNote] = Field(default_factory=list)
    """Notes distinguishing this form from commonly confused forms."""

    encountered_vocabulary: list[EncounteredVocabularySummary] = Field(default_factory=list)
    """Vocabulary items present in the lesson's context sentence(s)."""

    nuance_sets: list[NuanceSet] = Field(default_factory=list)
    """Curated minimal-pair clusters for meaning discrimination.

    Each set targets one grammatical distinction (e.g. preterite vs imperfect)
    and contains two or more sentence pairs that let the learner observe how
    the same structural choice changes implication, tone, or temporal reading.
    """
