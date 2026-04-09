"""Deterministic lesson and drill generators.

Each generator takes the canonical object's stored fields and produces a
``LessonResponse`` with explanation text, key-value facts, and 2–3
practice drills.  All output is deterministic: the same inputs always
produce the same lesson so Redis-cached parse results remain coherent
with later lesson fetches.

Determinism mechanism
─────────────────────
Multiple-choice option order and wrong-option selection are derived from
SHA-256(seed + option).  ``seed`` is the canonical_form, which is stable
across server restarts (it is the same string used to compute the UUID).

Adding new languages or lesson types
─────────────────────────────────────
Register the type in ``build_lesson()``'s dispatch table.  Each builder
receives the full ``lesson_data`` dict, so new fields added by a plugin
are automatically available without changes here.
"""
from __future__ import annotations

import hashlib
from typing import Any

from backend.schemas.lesson import (
    Drill,
    FillBlankDrill,
    LessonField,
    LessonResponse,
    MultipleChoiceDrill,
    RecognitionDrill,
    ShadowingDrill,
)

# ── POS display ───────────────────────────────────────────────────────────────

_POS_DISPLAY: dict[str, str] = {
    "NOUN":  "noun",
    "VERB":  "verb",
    "AUX":   "auxiliary verb",
    "ADJ":   "adjective",
    "ADV":   "adverb",
    "PROPN": "proper noun",
    "WORD":  "word",       # EnglishStubPlugin
}

_POS_OPTIONS: list[str] = [
    "noun", "verb", "adjective", "adverb", "auxiliary verb", "proper noun",
]

# ── Conjugation display ───────────────────────────────────────────────────────

_TENSE_OPTIONS: list[str] = [
    "present", "preterite", "imperfect", "future", "conditional",
]

_MOOD_OPTIONS: list[str] = [
    "indicative", "subjunctive", "imperative",
]

_PERSON_LABELS: dict[str, str] = {
    "1": "first",
    "2": "second",
    "3": "third",
}

_NUMBER_LABELS: dict[str, str] = {
    "Sing": "singular",
    "Plur": "plural",
}


# ── Public entry point ────────────────────────────────────────────────────────

def build_lesson(
    *,
    object_id: str,
    obj_type: str,
    canonical_form: str,
    display_label: str,
    lesson_data: dict[str, Any],
) -> LessonResponse:
    """Build a structured lesson for any canonical object type.

    Dispatches to a type-specific builder; falls back to a generic
    builder for types without a dedicated generator.
    """
    builders = {
        "vocabulary":  _build_vocabulary,
        "conjugation": _build_conjugation,
        "agreement":   _build_agreement,
    }
    builder = builders.get(obj_type, _build_generic)
    return builder(
        object_id=object_id,
        obj_type=obj_type,
        canonical_form=canonical_form,
        display_label=display_label,
        lesson_data=lesson_data,
    )


# ── Type-specific builders ────────────────────────────────────────────────────

def _build_vocabulary(
    *,
    object_id: str,
    obj_type: str,
    canonical_form: str,
    display_label: str,
    lesson_data: dict[str, Any],
) -> LessonResponse:
    lemma    = lesson_data.get("lemma") or canonical_form
    pos_raw  = lesson_data.get("pos") or "WORD"
    pos      = _POS_DISPLAY.get(pos_raw, pos_raw.lower())
    seed     = canonical_form

    # Explanation
    if display_label.lower() != lemma.lower():
        explanation = (
            f"\u201c{display_label}\u201d is a {pos}. "
            f"Its base form (lemma) is \u201c{lemma}\u201d."
        )
    else:
        explanation = f"\u201c{display_label}\u201d is a {pos}."

    # Fields
    fields: list[LessonField] = [
        LessonField(label="Lemma", value=lemma),
        LessonField(label="Part of speech", value=pos),
    ]
    if verb_form := lesson_data.get("verb_form"):
        fields.append(LessonField(label="Form", value=verb_form.lower()))
    if note := lesson_data.get("confidence_note"):
        fields.append(LessonField(label="Note", value=note))

    # Drills
    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=display_label)]

    mc = _make_mc_drill(
        seed=seed,
        prompt=f"\u201c{display_label}\u201d is a \u2014\u2014\u2014",
        correct=pos,
        pool=_POS_OPTIONS,
    )
    if mc:
        drills.append(mc)

    if display_label.lower() != lemma.lower():
        drills.append(FillBlankDrill(
            type="fill_blank",
            prompt=f"The base form (lemma) of \u201c{display_label}\u201d is \u2014\u2014\u2014.",
            answer=lemma,
        ))

    return LessonResponse(
        id=object_id,
        type="vocabulary",
        title=f"Vocabulary: {display_label}",
        explanation=explanation,
        fields=fields,
        examples=[display_label],
        drills=drills,
    )


def _build_conjugation(
    *,
    object_id: str,
    obj_type: str,
    canonical_form: str,
    display_label: str,
    lesson_data: dict[str, Any],
) -> LessonResponse:
    lemma   = lesson_data.get("lemma") or canonical_form
    surface = lesson_data.get("surface") or display_label
    tense   = lesson_data.get("tense") or "unknown"
    mood    = lesson_data.get("mood") or "unknown"
    person  = lesson_data.get("person") or "unknown"
    number  = lesson_data.get("number") or "unknown"
    seed    = canonical_form

    person_label = _PERSON_LABELS.get(str(person), str(person))
    number_label = _NUMBER_LABELS.get(str(number), str(number))

    # Explanation
    if tense != "unknown" and mood != "unknown":
        explanation = (
            f"\u201c{surface}\u201d is the {person_label}-person {number_label} "
            f"{tense} {mood} form of \u201c{lemma}\u201d."
        )
    else:
        explanation = f"\u201c{surface}\u201d is a conjugated form of \u201c{lemma}\u201d."

    # Fields
    fields: list[LessonField] = [
        LessonField(label="Lemma", value=lemma),
        LessonField(label="Surface form", value=surface),
    ]
    if tense != "unknown":
        fields.append(LessonField(label="Tense", value=tense))
    if mood != "unknown":
        fields.append(LessonField(label="Mood", value=mood))
    if person != "unknown":
        fields.append(LessonField(label="Person", value=person_label))
    if number != "unknown":
        fields.append(LessonField(label="Number", value=number_label))
    if construction := lesson_data.get("construction"):
        fields.append(LessonField(label="Construction", value=construction))
    if lesson_data.get("is_reflexive"):
        fields.append(LessonField(label="Reflexive", value="yes"))
    if note := lesson_data.get("confidence_note"):
        fields.append(LessonField(label="Note", value=note))

    # Drills
    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=surface)]

    drills.append(FillBlankDrill(
        type="fill_blank",
        prompt=f"\u201c{surface}\u201d is a form of the verb \u2014\u2014\u2014.",
        answer=lemma,
    ))

    if tense != "unknown":
        mc = _make_mc_drill(
            seed=seed,
            prompt=f"What tense is \u201c{surface}\u201d?",
            correct=tense,
            pool=_TENSE_OPTIONS,
        )
        if mc:
            drills.append(mc)

    if lesson_data.get("is_reflexive") is not None:
        drills.append(RecognitionDrill(
            type="recognition",
            statement=f"\u201c{surface}\u201d uses a reflexive pronoun.",
            correct=bool(lesson_data["is_reflexive"]),
        ))

    return LessonResponse(
        id=object_id,
        type="conjugation",
        title=f"Conjugation: {surface}",
        explanation=explanation,
        fields=fields,
        examples=[surface],
        drills=drills,
    )


def _build_agreement(
    *,
    object_id: str,
    obj_type: str,
    canonical_form: str,
    display_label: str,
    lesson_data: dict[str, Any],
) -> LessonResponse:
    modifier     = lesson_data.get("modifier") or display_label
    noun         = lesson_data.get("noun") or display_label
    modifier_pos = lesson_data.get("modifier_pos") or ""
    gender       = lesson_data.get("gender") or "unknown"
    number       = lesson_data.get("number") or "unknown"
    gender_match = lesson_data.get("gender_match")
    number_match = lesson_data.get("number_match")
    seed         = canonical_form

    gender_display = {"Masc": "masculine", "Fem": "feminine"}.get(gender, gender.lower())
    number_display = {"Sing": "singular", "Plur": "plural"}.get(number, number.lower())
    pos_display    = _POS_DISPLAY.get(modifier_pos, modifier_pos.lower())

    # Explanation
    confirmed = []
    if gender_match is True:
        confirmed.append("gender")
    if number_match is True:
        confirmed.append("number")
    confirmed_str = " and ".join(confirmed) if confirmed else "morphological features"
    explanation = (
        f"\u201c{modifier}\u201d ({pos_display}) and \u201c{noun}\u201d agree in "
        f"{confirmed_str}. The noun \u201c{noun}\u201d is {gender_display} {number_display}."
    )

    # Fields
    fields: list[LessonField] = [
        LessonField(label="Modifier", value=f"{modifier} ({pos_display})"),
        LessonField(label="Noun", value=noun),
        LessonField(label="Gender", value=gender_display),
        LessonField(label="Number", value=number_display),
    ]
    if gender_match is not None:
        fields.append(LessonField(label="Gender match", value="yes" if gender_match else "no"))
    if number_match is not None:
        fields.append(LessonField(label="Number match", value="yes" if number_match else "no"))

    # Drills
    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=display_label)]

    if gender_match is True:
        drills.append(RecognitionDrill(
            type="recognition",
            statement=f"\u201c{modifier}\u201d and \u201c{noun}\u201d agree in gender.",
            correct=True,
        ))

    gender_options = ["masculine", "feminine", "unknown"]
    mc = _make_mc_drill(
        seed=seed,
        prompt=f"What gender is \u201c{noun}\u201d?",
        correct=gender_display,
        pool=gender_options,
    )
    if mc:
        drills.append(mc)

    return LessonResponse(
        id=object_id,
        type="agreement",
        title=f"Agreement: {display_label}",
        explanation=explanation,
        fields=fields,
        examples=[display_label],
        drills=drills,
    )


def _build_generic(
    *,
    object_id: str,
    obj_type: str,
    canonical_form: str,
    display_label: str,
    lesson_data: dict[str, Any],
) -> LessonResponse:
    """Fallback for idiom / grammar / nuance types without a dedicated builder."""
    fields = [
        LessonField(label=k.replace("_", " ").title(), value=str(v))
        for k, v in lesson_data.items()
        if k not in ("confidence_note",) and v not in (None, "")
    ]
    return LessonResponse(
        id=object_id,
        type=obj_type,  # type: ignore[arg-type]
        title=f"{obj_type.replace('_', ' ').title()}: {display_label}",
        explanation=f"\u201c{display_label}\u201d \u2014 {obj_type.replace('_', ' ')}.",
        fields=fields,
        examples=[display_label],
        drills=[ShadowingDrill(type="shadowing", text=display_label)],
    )


# ── Drill helpers ─────────────────────────────────────────────────────────────

def _hash_key(seed: str, value: str) -> int:
    """Deterministic integer sort key derived from SHA-256(seed + value)."""
    digest = hashlib.sha256(f"{seed}\x00{value}".encode()).hexdigest()
    return int(digest[:8], 16)


def _make_mc_drill(
    seed: str,
    prompt: str,
    correct: str,
    pool: list[str],
    n_wrong: int = 3,
) -> MultipleChoiceDrill | None:
    """Build a multiple-choice drill with deterministically shuffled options.

    Returns None when the pool has fewer wrong options than requested —
    the caller should omit the drill rather than display a trivially easy one.
    """
    wrong = [x for x in pool if x.lower() != correct.lower()]
    if len(wrong) < n_wrong:
        return None
    # Pick n_wrong wrong options deterministically
    wrong.sort(key=lambda x: _hash_key(seed + "wrong", x))
    chosen_wrong = wrong[:n_wrong]

    # Shuffle all options (correct + chosen_wrong)
    all_options = chosen_wrong + [correct]
    all_options.sort(key=lambda x: _hash_key(seed + "order", x))

    return MultipleChoiceDrill(
        type="multiple_choice",
        prompt=prompt,
        options=all_options,
        answer_index=all_options.index(correct),
    )
