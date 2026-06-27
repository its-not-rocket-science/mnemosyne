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
(“ / ”) for typographic consistency.  No HTML or markdown.

Graceful degradation
────────────────────
When ``context.language_name`` is ``None`` (unknown language), functions
fall back to language-neutral phrasings so the output is still grammatically
correct:
  - "is a Spanish idiom"  →  "is an idiomatic expression"
  - "is a German noun"    →  "is a noun"
"""
from __future__ import annotations

import backend.lesson.l10n as l10n
from backend.lesson.context import LessonContext

# ── Helpers ───────────────────────────────────────────────────────────────────

_L  = "“"   # left double quotation mark
_R  = "”"   # right double quotation mark
_EM = "—"   # em dash


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
    l1 = context.l1_language
    pos_phrase = l10n.pos_label(pos, l1)
    if display_label.lower() != lemma.lower():
        return l10n.t(
            "vocab.with_lemma", l1,
            word=_q(display_label), pos=pos_phrase, lemma=_q(lemma),
        )
    return l10n.t("vocab.simple", l1, word=_q(display_label), pos=pos_phrase)


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
    l1 = context.l1_language
    if tense != "unknown" and mood != "unknown":
        if person_label != "unknown" and number_label != "unknown":
            return l10n.t(
                "conj.full", l1,
                word=_q(surface),
                person=l10n.gram_label("person", person_label, l1),
                number=l10n.gram_label("number", number_label, l1),
                tense=l10n.gram_label("tense", tense, l1),
                mood=l10n.gram_label("mood", mood, l1),
                lemma=_q(lemma),
            )
        return l10n.t(
            "conj.tense_only", l1,
            word=_q(surface),
            tense=l10n.gram_label("tense", tense, l1),
            mood=l10n.gram_label("mood", mood, l1),
            lemma=_q(lemma),
        )
    return l10n.t("conj.simple", l1, word=_q(surface), lemma=_q(lemma))


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
    l1 = context.l1_language
    return l10n.t(
        "agree.main", l1,
        mod=_q(modifier), mod_pos=modifier_pos_display, noun=_q(noun),
        features=l10n.localize_features(confirmed_features, l1),
        gender=l10n.gram_label("gender", gender_display, l1),
        number=l10n.gram_label("number", number_display, l1),
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
    l1 = context.l1_language
    return l10n.t(
        "case.main", l1,
        mod=_q(modifier), mod_pos=modifier_pos_display, noun=_q(noun),
        features=l10n.localize_features(confirmed_features, l1),
        gender=l10n.gram_label("gender", gender_display, l1),
        number=l10n.gram_label("number", number_display, l1),
        case=l10n.gram_label("case", case_display, l1),
    )


def idiom_explanation(
    phrase: str,
    meaning: str,
    context: LessonContext,
) -> str:
    """One-sentence explanation for an idiomatic expression."""
    l1 = context.l1_language
    lang_loc = l10n.lang_name(context.language_name, l1)
    if lang_loc and meaning:
        return l10n.t(
            "idiom.with_lang_and_meaning", l1,
            word=_q(phrase), lang=lang_loc, meaning=_q(meaning),
        )
    if lang_loc:
        return l10n.t("idiom.with_lang", l1, word=_q(phrase), lang=lang_loc)
    if meaning:
        return l10n.t("idiom.meaning_only", l1, word=_q(phrase), meaning=_q(meaning))
    return l10n.t("idiom.plain", l1, word=_q(phrase))


def grammar_explanation(
    pattern: str,
    usage: str,
    context: LessonContext,
) -> str:
    """One-sentence explanation for a structural grammar pattern."""
    l1 = context.l1_language
    if usage:
        return l10n.t("grammar.with_usage", l1, pattern=_q(pattern), usage=usage)
    return l10n.t("grammar.plain", l1, pattern=_q(pattern))


def nuance_explanation(
    surface: str,
    type_label: str,
    note: str,
    context: LessonContext,
) -> str:
    """One-sentence explanation for an aspect/mood nuance observation."""
    if note:
        return note
    l1 = context.l1_language
    return l10n.t("nuance.exhibits", l1, word=_q(surface), type_label=type_label.lower())


def script_explanation(
    character: str,
    meaning: str | None,
    context: LessonContext,
) -> str:
    """One-sentence explanation for a script character or sign."""
    l1 = context.l1_language
    if meaning:
        return l10n.t("script.with_meaning", l1, char=_q(character), meaning=meaning)
    return l10n.t("script.plain", l1, char=_q(character))


def dictionary_explanation(
    token: str,
    gloss: str | None,
    context: LessonContext,
) -> str:
    """One-sentence explanation for a dictionary-mode token.

    Priorities:
      1. When gloss is known: ``"amor" — love, desire.``
      2. When language is known but no gloss: ``"amor" — Latin vocabulary.``
      3. Fallback: ``"amor"``

    Deliberately terse — the lesson fields carry the structural detail.
    Does not claim grammatical completeness.
    """
    l1 = context.l1_language
    if gloss:
        return l10n.t("dict.with_gloss", l1, word=_q(token), gloss=gloss)
    lang_loc = l10n.lang_name(context.language_name, l1)
    if lang_loc:
        return l10n.t("dict.with_lang", l1, word=_q(token), lang=lang_loc)
    return l10n.t("dict.plain", l1, word=_q(token))


def inflection_explanation(
    surface: str,
    pos: str,
    case: str,
    gender: str,
    number: str,
    lemma: str,
    context: LessonContext,
) -> str:
    """One-sentence explanation for a declined nominal form."""
    l1 = context.l1_language
    if case != "unknown" and number != "unknown":
        return l10n.t(
            "inflect.case_number", l1,
            word=_q(surface),
            case=l10n.gram_label("case", case, l1),
            number=l10n.gram_label("number", number, l1),
            lemma=_q(lemma),
        )
    return l10n.t("inflect.simple", l1, word=_q(surface), lemma=_q(lemma))


def transliteration_explanation(
    native_form: str,
    romanized: str,
    scheme: str,
    meaning: str | None,
    context: LessonContext,
) -> str:
    """One-sentence explanation for a native ↔ romanization pair."""
    l1 = context.l1_language
    scheme_note = f" ({scheme})" if scheme else ""
    if meaning:
        return l10n.t(
            "translit.with_meaning", l1,
            native=_q(native_form), roman=_q(romanized),
            scheme=scheme_note, meaning=_q(meaning),
        )
    return l10n.t(
        "translit.plain", l1,
        native=_q(native_form), roman=_q(romanized), scheme=scheme_note,
    )
