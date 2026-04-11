"""Language-aware explanation text for lesson builders.

Each function takes the data already assembled by a builder and a
``LessonContext``, and returns a single human-readable sentence that explains
what the learnable object is.

Rationale
─────────
Separating explanation text from the builder logic lets:
  1. Tests assert that explanations are grammatically natural in isolation.
  2. The language name is injected from ``LessonContext`` rather than
     hardcoded per builder (fixing the original "Spanish idiom" regression
     where the language name was hardcoded in the idiom builder).
  3. Future localisation of explanation prose is confined to this module.

All functions return plain-text strings with Unicode quotation marks
(\\u201c / \\u201d) for typographic consistency.  No HTML or markdown.

Graceful degradation
────────────────────
When ``context.language_name`` is ``None`` (unknown language), functions
fall back to language-neutral phrasings so the output is still grammatically
correct:
  - "is a Spanish idiom"  →  "is an idiomatic expression"
  - "is a German noun"    →  "is a noun"
"""
from __future__ import annotations

from backend.lesson.context import LessonContext

# ── Helpers ───────────────────────────────────────────────────────────────────

_L  = "\u201c"   # left double quotation mark
_R  = "\u201d"   # right double quotation mark
_EM = "\u2014"   # em dash


def _q(text: str) -> str:
    """Wrap *text* in typographic double quotes."""
    return f"{_L}{text}{_R}"


# ── Formatters ────────────────────────────────────────────────────────────────

def vocabulary_explanation(
    display_label: str,
    pos: str,
    lemma: str,
    context: LessonContext,
) -> str:
    """One-sentence explanation for a vocabulary / open-class word."""
    if display_label.lower() != lemma.lower():
        return (
            f"{_q(display_label)} is a {pos}. "
            f"Its base form (lemma) is {_q(lemma)}."
        )
    return f"{_q(display_label)} is a {pos}."


def conjugation_explanation(
    surface: str,
    person_label: str,
    number_label: str,
    tense: str,
    mood: str,
    lemma: str,
    context: LessonContext,
) -> str:
    """One-sentence explanation for a conjugated verb form."""
    if tense != "unknown" and mood != "unknown":
        return (
            f"{_q(surface)} is the {person_label}-person {number_label} "
            f"{tense} {mood} form of {_q(lemma)}."
        )
    return f"{_q(surface)} is a conjugated form of {_q(lemma)}."


def agreement_explanation(
    modifier: str,
    modifier_pos_display: str,
    noun: str,
    confirmed_features: list[str],
    gender_display: str,
    number_display: str,
    context: LessonContext,
) -> str:
    """One-sentence explanation for a gender/number agreement pair."""
    confirmed_str = (
        " and ".join(confirmed_features) if confirmed_features
        else "morphological features"
    )
    return (
        f"{_q(modifier)} ({modifier_pos_display}) and {_q(noun)} agree in "
        f"{confirmed_str}. The noun {_q(noun)} is {gender_display} {number_display}."
    )


def case_agreement_explanation(
    modifier: str,
    modifier_pos_display: str,
    noun: str,
    confirmed_features: list[str],
    gender_display: str,
    number_display: str,
    case_display: str,
    context: LessonContext,
) -> str:
    """One-sentence explanation for a case+gender+number agreement cluster."""
    confirmed_str = (
        " and ".join(confirmed_features) if confirmed_features
        else "morphological features"
    )
    return (
        f"{_q(modifier)} ({modifier_pos_display}) and {_q(noun)} agree in "
        f"{confirmed_str}. The noun {_q(noun)} is {gender_display} "
        f"{number_display} in the {case_display} case."
    )


def idiom_explanation(
    phrase: str,
    meaning: str,
    context: LessonContext,
) -> str:
    """One-sentence explanation for an idiomatic expression.

    Uses ``context.language_name`` when available so the explanation reads
    "a Spanish idiom" rather than the old hardcoded string.  Falls back to
    grammatically correct language-neutral phrasing when the language is
    unknown.
    """
    if context.language_name:
        lang = context.language_name
        if meaning:
            return f"{_q(phrase)} is a {lang} idiom meaning {_q(meaning)}."
        return f"{_q(phrase)} is a {lang} idiomatic expression."
    # Unknown language — omit the language name for grammatical correctness.
    if meaning:
        return f"{_q(phrase)} means {_q(meaning)}."
    return f"{_q(phrase)} is an idiomatic expression."


def grammar_explanation(
    pattern: str,
    usage: str,
    context: LessonContext,
) -> str:
    """One-sentence explanation for a structural grammar pattern."""
    if usage:
        return f"The pattern {_q(pattern)}: {usage}"
    return f"The grammatical pattern {_q(pattern)}."


def nuance_explanation(
    surface: str,
    type_label: str,
    note: str,
    context: LessonContext,
) -> str:
    """One-sentence explanation for an aspect/mood nuance observation."""
    if note:
        return note
    return f"{_q(surface)} exhibits {type_label.lower()}."


def script_explanation(
    character: str,
    meaning: str | None,
    context: LessonContext,
) -> str:
    """One-sentence explanation for a script character or sign."""
    if meaning:
        return f"{_q(character)} {_EM} {meaning}."
    return f"{_q(character)}"


def transliteration_explanation(
    native_form: str,
    romanized: str,
    scheme: str,
    meaning: str | None,
    context: LessonContext,
) -> str:
    """One-sentence explanation for a native ↔ romanization pair."""
    scheme_note = f" ({scheme})" if scheme else ""
    if meaning:
        return (
            f"{_q(native_form)} is romanized as {_q(romanized)}"
            f"{scheme_note} and means {_q(meaning)}."
        )
    return f"{_q(native_form)} is romanized as {_q(romanized)}{scheme_note}."
