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

Lesson modes
────────────
``build_lesson()`` accepts an optional ``lesson_mode`` that controls which
template is used regardless of object type:

  morphology  — full conjugation/agreement/tense drills (default).
  vocabulary  — lemma + POS fields and shadowing drill only.  Use for
                plugins that provide POS but not full morphology (e.g. stubs).
  dictionary  — word + gloss fields only.  Use for languages where the
                plugin cannot provide POS or inflection analysis.

The lesson route picks the mode from the plugin's ``capabilities.lesson_modes_supported``
list so plugins do not need to know which template they will use.
"""
from __future__ import annotations

import hashlib
from typing import Any

from backend.schemas.language import LessonMode
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

# ARCH (multilingual gap): "preterite" is a Spanish-specific term.
# French, Italian, Portuguese, and other Romance languages use different
# past-tense vocabulary in pedagogical contexts.  "past" is added here so
# French verbs tagged Tense=Past (literary passé simple) produce a valid
# MC drill, but "preterite" remains as a wrong-option distractor which is
# misleading for French learners.
# Future fix: make this pool pluggable via lesson_data["tense_options"] or
# a per-language registry so each plugin can supply the appropriate terms.
_TENSE_OPTIONS: list[str] = [
    "present", "preterite", "imperfect", "future", "conditional", "past",
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
    lesson_mode: LessonMode = "morphology",
) -> LessonResponse:
    """Build a structured lesson for any canonical object type.

    ``lesson_mode`` controls the template used:

    - ``"morphology"`` (default) — dispatches by object type to the richest
      available builder (conjugation/agreement/vocabulary).  Use for plugins
      with full morphological analysis.
    - ``"vocabulary"`` — always uses the vocabulary builder regardless of
      object type.  Suitable for plugins that provide POS but not full
      paradigms (e.g. stub plugins).
    - ``"dictionary"`` — uses the minimal dictionary builder: word + gloss
      only.  Use when the plugin cannot reliably provide POS or morphology.
    """
    # "script" and "transliteration" always use their dedicated builders.
    # They have no tense/POS equivalent so lesson_mode does not apply.
    if obj_type in ("script", "transliteration"):
        _type_builders = {
            "script":          _build_script,
            "transliteration": _build_transliteration,
        }
        response = _type_builders[obj_type](
            object_id=object_id,
            obj_type=obj_type,
            canonical_form=canonical_form,
            display_label=display_label,
            lesson_data=lesson_data,
        )
    elif lesson_mode == "dictionary":
        response = _build_dictionary(
            object_id=object_id,
            obj_type=obj_type,
            canonical_form=canonical_form,
            display_label=display_label,
            lesson_data=lesson_data,
        )
    elif lesson_mode == "vocabulary":
        response = _build_vocabulary(
            object_id=object_id,
            obj_type=obj_type,
            canonical_form=canonical_form,
            display_label=display_label,
            lesson_data=lesson_data,
        )
    else:
        # lesson_mode == "morphology" — dispatch by type.
        # "script" and "transliteration" always use their dedicated builders
        # regardless of lesson_mode because their structure is intrinsic to the
        # object type, not a choice of lesson depth.
        builders = {
            "vocabulary":       _build_vocabulary,
            "conjugation":      _build_conjugation,
            "agreement":        _build_agreement,
            "script":           _build_script,
            "transliteration":  _build_transliteration,
            "idiom":            _build_idiom,
            "grammar":          _build_grammar,
            "nuance":           _build_nuance,
        }
        builder = builders.get(obj_type, _build_generic)
        response = builder(
            object_id=object_id,
            obj_type=obj_type,
            canonical_form=canonical_form,
            display_label=display_label,
            lesson_data=lesson_data,
        )

    # Stamp the lesson_mode onto the response regardless of which builder ran.
    return response.model_copy(update={"lesson_mode": lesson_mode})


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


def _build_script(
    *,
    object_id: str,
    obj_type: str,
    canonical_form: str,
    display_label: str,
    lesson_data: dict[str, Any],
) -> LessonResponse:
    """Lesson for a script / character / sign learning object.

    Used for CJK kanji/hanzi, Arabic letters, Devanagari akṣaras, and any
    other writing-system unit that warrants its own drill.

    Expected ``lesson_data`` keys (all optional — the builder degrades
    gracefully when any are absent):

    character     — the character or sign to learn (defaults to display_label).
    readings      — list[str] of pronunciations / readings.
    meaning       — English gloss or short definition.
    stroke_count  — integer stroke count (informational).
    notes         — free-text notes from the plugin.
    """
    character    = lesson_data.get("character") or display_label
    readings_raw = lesson_data.get("readings") or []
    readings: list[str] = (
        readings_raw if isinstance(readings_raw, list) else [str(readings_raw)]
    )
    meaning      = lesson_data.get("meaning") or lesson_data.get("gloss")
    stroke_count = lesson_data.get("stroke_count")
    notes        = lesson_data.get("notes")

    # Explanation
    if meaning:
        explanation = f"\u201c{character}\u201d — {meaning}."
    else:
        explanation = f"\u201c{character}\u201d"

    # Fields
    fields: list[LessonField] = [LessonField(label="Character", value=character)]
    if readings:
        fields.append(LessonField(label="Reading(s)", value=",  ".join(readings)))
    if meaning:
        fields.append(LessonField(label="Meaning", value=str(meaning)))
    if stroke_count is not None:
        fields.append(LessonField(label="Strokes", value=str(stroke_count)))
    if notes:
        fields.append(LessonField(label="Notes", value=str(notes)))

    # Drills
    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=character)]

    if readings:
        # Fill-blank: write the reading from memory.
        primary_reading = readings[0]
        drills.append(FillBlankDrill(
            type="fill_blank",
            prompt=f"How is \u201c{character}\u201d read?",
            answer=primary_reading,
            hint=f"(first reading)" if len(readings) > 1 else None,
        ))

    if meaning:
        # Fill-blank: recall the meaning.
        drills.append(FillBlankDrill(
            type="fill_blank",
            prompt=f"What does \u201c{character}\u201d mean?",
            answer=str(meaning),
        ))

    return LessonResponse(
        id=object_id,
        type="script",  # type: ignore[arg-type]
        title=f"Script: {character}",
        explanation=explanation,
        fields=fields,
        examples=[character] + readings[:2],  # show up to 2 readings as spoken examples
        drills=drills,
    )


def _build_transliteration(
    *,
    object_id: str,
    obj_type: str,
    canonical_form: str,
    display_label: str,
    lesson_data: dict[str, Any],
) -> LessonResponse:
    """Lesson for a native-form ↔ romanization / phonetic mapping.

    Used when a plugin emits a "transliteration" object — for example a
    Japanese word with its Hepburn romaji, or a Mandarin word with pinyin.

    Expected ``lesson_data`` keys (all optional):

    native_form   — the original-script form (defaults to display_label).
    romanized     — romanized / phonetic representation (defaults to canonical_form).
    scheme        — name of the transliteration scheme (e.g. "hepburn_romaji").
    meaning       — optional English gloss.
    """
    native_form = lesson_data.get("native_form") or display_label
    romanized   = lesson_data.get("romanized") or canonical_form
    scheme      = lesson_data.get("scheme") or ""
    meaning     = lesson_data.get("meaning") or lesson_data.get("gloss")
    seed        = canonical_form

    # Explanation
    scheme_note = f" ({scheme})" if scheme else ""
    if meaning:
        explanation = (
            f"\u201c{native_form}\u201d is romanized as \u201c{romanized}\u201d"
            f"{scheme_note} and means \u201c{meaning}\u201d."
        )
    else:
        explanation = (
            f"\u201c{native_form}\u201d is romanized as \u201c{romanized}\u201d{scheme_note}."
        )

    # Fields
    fields: list[LessonField] = [
        LessonField(label="Native form",    value=native_form),
        LessonField(label="Romanization",   value=romanized),
    ]
    if scheme:
        fields.append(LessonField(label="Scheme", value=scheme))
    if meaning:
        fields.append(LessonField(label="Meaning", value=str(meaning)))

    # Drills
    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=native_form)]

    # Fill-blank: produce the romanization from the native form.
    drills.append(FillBlankDrill(
        type="fill_blank",
        prompt=f"Romanize \u201c{native_form}\u201d.",
        answer=romanized,
    ))

    # Fill-blank: produce the native form from the romanization.
    drills.append(FillBlankDrill(
        type="fill_blank",
        prompt=f"Write the native form for \u201c{romanized}\u201d.",
        answer=native_form,
    ))

    return LessonResponse(
        id=object_id,
        type="transliteration",  # type: ignore[arg-type]
        title=f"Transliteration: {native_form}",
        explanation=explanation,
        fields=fields,
        examples=[native_form, romanized],
        drills=drills,
    )


def _build_dictionary(
    *,
    object_id: str,
    obj_type: str,
    canonical_form: str,
    display_label: str,
    lesson_data: dict[str, Any],
) -> LessonResponse:
    """Minimal lesson for dictionary-mode plugins.

    Used when the plugin cannot reliably provide POS or morphological
    analysis (e.g. a vocabulary stub or a language with limited NLP support).
    Shows the word, any available gloss, and a single shadowing drill.
    No POS labels, no tense/mood drills — only what the plugin reliably knows.
    """
    fields: list[LessonField] = []

    # Show any gloss the plugin provides; never fabricate one.
    if gloss := lesson_data.get("gloss"):
        fields.append(LessonField(label="Gloss", value=str(gloss)))
    # Show lemma only when it differs from the display form.
    if lemma := lesson_data.get("lemma"):
        if str(lemma).lower() != display_label.lower():
            fields.append(LessonField(label="Base form", value=str(lemma)))
    if note := lesson_data.get("confidence_note"):
        fields.append(LessonField(label="Note", value=str(note)))

    return LessonResponse(
        id=object_id,
        type=obj_type,  # type: ignore[arg-type]
        title=f"{display_label}",
        explanation=f"\u201c{display_label}\u201d",
        fields=fields,
        examples=[display_label],
        drills=[ShadowingDrill(type="shadowing", text=display_label)],
    )


def _build_idiom(
    *,
    object_id: str,
    obj_type: str,
    canonical_form: str,
    display_label: str,
    lesson_data: dict[str, Any],
) -> LessonResponse:
    """Lesson for a multi-word idiomatic expression.

    Expected ``lesson_data`` keys:

    phrase    — the canonical fixed-form phrase (defaults to display_label).
    meaning   — English translation / gloss.
    register  — "neutral" | "formal" | "informal" (optional).
    """
    phrase   = lesson_data.get("phrase") or display_label
    meaning  = lesson_data.get("meaning") or ""
    register = lesson_data.get("register") or ""
    seed     = canonical_form

    # Explanation
    if meaning:
        explanation = f"\u201c{phrase}\u201d is a Spanish idiom meaning \u201c{meaning}\u201d."
    else:
        explanation = f"\u201c{phrase}\u201d is a Spanish idiomatic expression."

    # Fields
    fields: list[LessonField] = [LessonField(label="Phrase", value=phrase)]
    if meaning:
        fields.append(LessonField(label="Meaning", value=meaning))
    if register:
        fields.append(LessonField(label="Register", value=register))

    # Drills
    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=phrase)]

    if meaning:
        drills.append(FillBlankDrill(
            type="fill_blank",
            prompt=f"What does \u201c{phrase}\u201d mean?",
            answer=meaning,
        ))

    if register:
        register_options = ["neutral", "formal", "informal"]
        mc = _make_mc_drill(
            seed=seed,
            prompt=f"What register is \u201c{phrase}\u201d?",
            correct=register,
            pool=register_options,
        )
        if mc:
            drills.append(mc)

    return LessonResponse(
        id=object_id,
        type="idiom",  # type: ignore[arg-type]
        title=f"Idiom: {phrase}",
        explanation=explanation,
        fields=fields,
        examples=[phrase],
        drills=drills,
    )


def _build_grammar(
    *,
    object_id: str,
    obj_type: str,
    canonical_form: str,
    display_label: str,
    lesson_data: dict[str, Any],
) -> LessonResponse:
    """Lesson for a periphrastic / structural grammar pattern.

    Expected ``lesson_data`` keys:

    pattern_id   — stable identifier (e.g. "ser_copula").
    pattern      — human-readable pattern label (e.g. "ser + [adjective / noun]").
    usage        — when and why this construction is used.
    contrast     — how it differs from a related construction.
    verb_lemma   — the triggering verb lemma (optional).
    surface_verb — the specific surface form found in the text (optional).
    """
    pattern_id   = lesson_data.get("pattern_id") or canonical_form
    pattern      = lesson_data.get("pattern") or display_label
    usage        = lesson_data.get("usage") or ""
    contrast     = lesson_data.get("contrast") or ""
    surface_verb = lesson_data.get("surface_verb") or display_label

    # Explanation
    if usage:
        explanation = f"The pattern \u201c{pattern}\u201d: {usage}"
    else:
        explanation = f"The grammatical pattern \u201c{pattern}\u201d."

    # Fields
    fields: list[LessonField] = [LessonField(label="Pattern", value=pattern)]
    if usage:
        fields.append(LessonField(label="Usage", value=usage))
    if contrast:
        fields.append(LessonField(label="Contrast", value=contrast))

    # Drills
    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=surface_verb)]

    if usage:
        drills.append(RecognitionDrill(
            type="recognition",
            statement=f"The pattern \u201c{pattern}\u201d is used for: {usage[:80]}{'...' if len(usage) > 80 else ''}",
            correct=True,
        ))

    if contrast:
        drills.append(RecognitionDrill(
            type="recognition",
            statement=f"The pattern \u201c{pattern}\u201d can replace a related construction without any meaning difference.",
            correct=False,
        ))

    return LessonResponse(
        id=object_id,
        type="grammar",  # type: ignore[arg-type]
        title=f"Grammar: {pattern}",
        explanation=explanation,
        fields=fields,
        examples=[surface_verb],
        drills=drills,
    )


def _build_nuance(
    *,
    object_id: str,
    obj_type: str,
    canonical_form: str,
    display_label: str,
    lesson_data: dict[str, Any],
) -> LessonResponse:
    """Lesson for an aspect, mood, or verb-type nuance observation.

    Expected ``lesson_data`` keys:

    nuance_type    — "imperfect_aspect" | "subjunctive_mood" | "reflexive_verb".
    lemma          — the verb lemma this nuance was derived from.
    surface        — the surface form found in the text.
    note           — human-readable explanation of the nuance.
    contrast_tense — for aspect nuances, the contrasting tense (optional).
    """
    nuance_type    = lesson_data.get("nuance_type") or obj_type
    lemma          = lesson_data.get("lemma") or canonical_form
    surface        = lesson_data.get("surface") or display_label
    note           = lesson_data.get("note") or ""
    contrast_tense = lesson_data.get("contrast_tense") or ""

    # Human-readable type label
    _type_labels: dict[str, str] = {
        "imperfect_aspect": "Imperfect aspect",
        "subjunctive_mood": "Subjunctive mood",
        "reflexive_verb":   "Reflexive / pronominal verb",
    }
    type_label = _type_labels.get(nuance_type, nuance_type.replace("_", " ").title())

    # Explanation
    if note:
        explanation = note
    else:
        explanation = f"\u201c{surface}\u201d exhibits {type_label.lower()}."

    # Fields
    fields: list[LessonField] = [
        LessonField(label="Type", value=type_label),
        LessonField(label="Verb", value=lemma),
        LessonField(label="Surface form", value=surface),
    ]
    if note:
        fields.append(LessonField(label="Note", value=note))
    if contrast_tense:
        fields.append(LessonField(label="Contrast tense", value=contrast_tense))

    # Drills
    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=surface)]

    if note:
        drills.append(RecognitionDrill(
            type="recognition",
            statement=f"\u201c{surface}\u201d ({type_label}) describes a completed, one-time past event.",
            correct=(nuance_type != "imperfect_aspect"),
        ))

    if contrast_tense:
        drills.append(FillBlankDrill(
            type="fill_blank",
            prompt=f"The tense that contrasts with the imperfect for a single completed event is the \u2014\u2014\u2014.",
            answer=contrast_tense,
        ))

    return LessonResponse(
        id=object_id,
        type="nuance",  # type: ignore[arg-type]
        title=f"{type_label}: {surface}",
        explanation=explanation,
        fields=fields,
        examples=[surface],
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
