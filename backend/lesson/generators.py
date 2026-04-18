"""Deterministic lesson and drill generators — multilingual lesson engine.

Architecture
────────────
The lesson engine is organised in three layers:

  1. **Shared primitives** (this file) — ``build_lesson()`` entry point,
     ``_B`` build-bundle, drill helpers, constants.

  2. **Language-aware formatters** (``lesson/formatters.py``) — pure functions
     that generate human-readable explanation text given a ``LessonContext``.
     Extracted here so the language name is injected (not hardcoded) and
     future prose localisation is confined to one file.

  3. **Provider abstraction** (``lesson/providers.py``) — ``GlossProvider``,
     ``PronunciationProvider`` protocols with null default implementations.
     Builders call providers to supplement ``lesson_data`` with external
     lookups (e.g. dictionary gloss) without hard-coding any data source.

Determinism
───────────
Multiple-choice option order and wrong-option selection are derived from
SHA-256(seed + option).  ``seed`` is the ``canonical_form``, which is stable
across server restarts.

Lesson templates
────────────────
``build_lesson()`` accepts an optional ``lesson_mode`` (the *richness* level
the plugin supports) and an optional ``context`` (language metadata).

The *effective template* reported on ``LessonResponse.lesson_mode`` may differ
from the requested ``lesson_mode``:

  - Idiom, script, and transliteration objects always use their dedicated
    builders regardless of ``lesson_mode``.  Their response reports
    ``"idiom"`` / ``"script"`` / ``"transliteration"`` respectively.

  - Grammar, nuance, and case-agreement objects also use dedicated builders
    (always) but report ``"morphology"`` on the response because they are
    derived from morphological analysis.

  - Vocabulary, conjugation, and agreement objects respect ``lesson_mode``.

Adding new languages or lesson types
─────────────────────────────────────
Register the type in ``_DEDICATED_BUILDERS`` (if it bypasses lesson_mode) or
in the morphology ``_MORPHOLOGY_BUILDERS`` dict (if it respects it).  Pass
any new lesson_data fields through ``_B``; the builder receives them via
``b.lesson_data``.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Callable, Literal

import backend.lesson.formatters as fmt
from backend.lesson.context import LessonContext
from backend.lesson.providers import LessonProviders
from backend.schemas.language import LessonMode
from backend.schemas.lesson import (
    Drill,
    FillBlankDrill,
    LessonField,
    LessonResponse,
    LessonTemplate,
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

# Global tense pool — used only when a plugin does not declare its own
# ``tense_pool`` via ``LanguageCapabilities``.  Covers the broadest set of
# plausible options across all supported languages.
_TENSE_OPTIONS: list[str] = [
    "present", "preterite", "imperfect", "future", "conditional", "past",
]

# Case labels and MC options — used by _build_case_agreement (German).
_CASE_DISPLAY: dict[str, str] = {
    "Nom": "nominative",
    "Acc": "accusative",
    "Dat": "dative",
    "Gen": "genitive",
}
_CASE_OPTIONS: list[str] = ["nominative", "accusative", "dative", "genitive"]

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


# ── Build bundle ──────────────────────────────────────────────────────────────

@dataclass(slots=True)
class _B:
    """Internal bundle threaded through every builder.

    Wraps all inputs to a builder so the argument list stays stable as new
    cross-cutting concerns (context, providers) are added.  The bundle is
    created once in ``build_lesson()`` and passed through unchanged.
    """
    object_id:      str
    obj_type:       str
    canonical_form: str
    display_label:  str
    lesson_data:    dict[str, Any]
    ctx:            LessonContext
    prov:           LessonProviders


# ── Public entry point ────────────────────────────────────────────────────────

def build_lesson(
    *,
    object_id: str,
    obj_type: str,
    canonical_form: str,
    display_label: str,
    lesson_data: dict[str, Any],
    lesson_mode: LessonMode = "morphology",
    context: LessonContext | None = None,
    providers: LessonProviders | None = None,
) -> LessonResponse:
    """Build a structured lesson for any canonical object type.

    Parameters
    ──────────
    lesson_mode
        Richness level the plugin supports — controls the template used for
        vocabulary, conjugation, and agreement objects:

        - ``"morphology"`` (default) — full morphological drills.
        - ``"vocabulary"`` — lemma + POS fields only.
        - ``"dictionary"`` — word + gloss only.

        Idiom, script, transliteration, grammar, nuance, and case_agreement
        objects use their dedicated builders regardless of ``lesson_mode``.

    context
        Language-level metadata (language code, name, script family,
        direction).  Injected into formatters to produce language-aware
        explanation prose (e.g. "a Spanish idiom").  Defaults to
        ``LessonContext.unknown()`` when not provided — all builders
        continue to work with degraded but grammatically correct prose.

    providers
        Injectable providers for supplemental data (gloss, pronunciation).
        Defaults to ``LessonProviders.null()`` (all null implementations).
        Pass a custom ``LessonProviders`` to enrich vocabulary lessons with
        dictionary definitions without changing any builder code.
    """
    ctx  = context   or LessonContext.unknown()
    prov = providers or LessonProviders.null()
    b = _B(
        object_id=object_id,
        obj_type=obj_type,
        canonical_form=canonical_form,
        display_label=display_label,
        lesson_data=lesson_data,
        ctx=ctx,
        prov=prov,
    )

    # ── Dispatch ──────────────────────────────────────────────────────────────
    #
    # Tier 1: dedicated builders that bypass lesson_mode entirely.
    #   - Idiom / script / transliteration → report their own template name.
    #   - Grammar / nuance / case_agreement → always morphological; report
    #     "morphology" (they are derived from morphological analysis).
    #
    # Tier 2: richness-level builders (vocabulary, conjugation, agreement)
    #   respect lesson_mode.

    effective_mode: LessonTemplate

    if obj_type in _DEDICATED_BUILDERS:
        builder, effective_mode = _DEDICATED_BUILDERS[obj_type]
        response = builder(b)
    elif lesson_mode == "dictionary":
        response = _build_dictionary(b)
        effective_mode = "dictionary"
    elif lesson_mode == "vocabulary":
        response = _build_vocabulary(b)
        effective_mode = "vocabulary"
    else:
        # lesson_mode == "morphology" — dispatch by object type.
        builder = _MORPHOLOGY_BUILDERS.get(obj_type, _build_generic)
        response = builder(b)
        effective_mode = "morphology"

    # Stamp the effective template and language context onto the response.
    update: dict[str, Any] = {"lesson_mode": effective_mode}
    if ctx.language_code is not None:
        update["language_code"] = ctx.language_code
    if ctx.direction and ctx.language_code is not None:
        update["script_direction"] = ctx.direction

    return response.model_copy(update=update)


# ── Type-specific builders ────────────────────────────────────────────────────

def _build_vocabulary(b: _B) -> LessonResponse:
    lemma   = b.lesson_data.get("lemma") or b.canonical_form
    pos_raw = b.lesson_data.get("pos") or "WORD"
    pos     = _POS_DISPLAY.get(pos_raw, pos_raw.lower())
    seed    = b.canonical_form

    explanation = fmt.vocabulary_explanation(b.display_label, pos, lemma, b.ctx)

    fields: list[LessonField] = [
        LessonField(label="Lemma", value=lemma),
        LessonField(label="Part of speech", value=pos),
    ]
    if pinyin := b.lesson_data.get("pinyin"):
        # CJK romanization — tagged "Romanized" so the script-view toggle can
        # hide/show it.  The modal's ROMANIZED_LABELS set matches on "romanized".
        fields.append(LessonField(label="Romanized", value=pinyin))
    if verb_form := b.lesson_data.get("verb_form"):
        fields.append(LessonField(label="Form", value=verb_form.lower()))

    # Stored translation (from background enrichment or on-demand /translate).
    if translation := b.lesson_data.get("translation"):
        fields.append(LessonField(label="Translation", value=str(translation)))

    # Provider-supplied gloss — only added when lesson_data has no gloss key.
    if not b.lesson_data.get("gloss"):
        if auto_gloss := b.prov.gloss.lookup(lemma, b.ctx.language_code, pos_raw):
            fields.append(LessonField(label="Gloss", value=auto_gloss))

    if note := b.lesson_data.get("confidence_note"):
        fields.append(LessonField(label="Note", value=note))

    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=b.display_label)]

    mc = _make_mc_drill(
        seed=seed,
        prompt=f"\u201c{b.display_label}\u201d is a \u2014\u2014\u2014",
        correct=pos,
        pool=_POS_OPTIONS,
    )
    if mc:
        drills.append(mc)

    if b.display_label.lower() != lemma.lower():
        drills.append(FillBlankDrill(
            type="fill_blank",
            prompt=f"The base form (lemma) of \u201c{b.display_label}\u201d is \u2014\u2014\u2014.",
            answer=lemma,
        ))

    return LessonResponse(
        id=b.object_id,
        type="vocabulary",
        title=f"Vocabulary: {b.display_label}",
        explanation=explanation,
        fields=fields,
        examples=[b.display_label],
        drills=drills,
    )


def _build_conjugation(b: _B) -> LessonResponse:
    lemma   = b.lesson_data.get("lemma") or b.canonical_form
    surface = b.lesson_data.get("surface") or b.display_label
    tense   = b.lesson_data.get("tense") or "unknown"
    mood    = b.lesson_data.get("mood") or "unknown"
    person  = b.lesson_data.get("person") or "unknown"
    number  = b.lesson_data.get("number") or "unknown"
    seed    = b.canonical_form

    person_label = _PERSON_LABELS.get(str(person), str(person))
    number_label = _NUMBER_LABELS.get(str(number), str(number))

    explanation = fmt.conjugation_explanation(
        surface, person_label, number_label, tense, mood, lemma, b.ctx
    )

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
    if construction := b.lesson_data.get("construction"):
        fields.append(LessonField(label="Construction", value=construction))
    if b.lesson_data.get("is_reflexive"):
        fields.append(LessonField(label="Reflexive", value="yes"))
    if verb_class := b.lesson_data.get("verb_class"):
        fields.append(LessonField(label="Verb class", value=verb_class))
    if b.lesson_data.get("is_separable"):
        particle = b.lesson_data.get("particle") or ""
        sep_label = f"yes \u2014 particle: {particle}" if particle else "yes"
        fields.append(LessonField(label="Separable verb", value=sep_label))
    if note := b.lesson_data.get("confidence_note"):
        fields.append(LessonField(label="Note", value=note))

    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=surface)]

    drills.append(FillBlankDrill(
        type="fill_blank",
        prompt=f"\u201c{surface}\u201d is a form of the verb \u2014\u2014\u2014.",
        answer=lemma,
    ))

    if tense != "unknown":
        tense_pool = list(b.ctx.tense_pool) if b.ctx.tense_pool else _TENSE_OPTIONS
        mc = _make_mc_drill(
            seed=seed,
            prompt=f"What tense is \u201c{surface}\u201d?",
            correct=tense,
            pool=tense_pool,
        )
        if mc:
            drills.append(mc)

    if mood != "unknown":
        mood_pool = list(b.ctx.mood_pool) if b.ctx.mood_pool else _MOOD_OPTIONS
        mc_mood = _make_mc_drill(
            seed=seed + "mood",
            prompt=f"What mood is \u201c{surface}\u201d?",
            correct=mood,
            pool=mood_pool,
        )
        if mc_mood:
            drills.append(mc_mood)

    if b.lesson_data.get("is_reflexive") is not None:
        drills.append(RecognitionDrill(
            type="recognition",
            statement=f"\u201c{surface}\u201d uses a reflexive pronoun.",
            correct=bool(b.lesson_data["is_reflexive"]),
        ))

    return LessonResponse(
        id=b.object_id,
        type="conjugation",
        title=f"Conjugation: {surface}",
        explanation=explanation,
        fields=fields,
        examples=[surface],
        drills=drills,
    )


def _build_agreement(b: _B) -> LessonResponse:
    modifier     = b.lesson_data.get("modifier") or b.display_label
    noun         = b.lesson_data.get("noun") or b.display_label
    modifier_pos = b.lesson_data.get("modifier_pos") or ""
    gender       = b.lesson_data.get("gender") or "unknown"
    number       = b.lesson_data.get("number") or "unknown"
    gender_match = b.lesson_data.get("gender_match")
    number_match = b.lesson_data.get("number_match")
    seed         = b.canonical_form

    gender_display = {"Masc": "masculine", "Fem": "feminine"}.get(gender, gender.lower())
    number_display = {"Sing": "singular", "Plur": "plural"}.get(number, number.lower())
    pos_display    = _POS_DISPLAY.get(modifier_pos, modifier_pos.lower())

    confirmed: list[str] = []
    if gender_match is True:
        confirmed.append("gender")
    if number_match is True:
        confirmed.append("number")

    explanation = fmt.agreement_explanation(
        modifier, pos_display, noun, confirmed, gender_display, number_display, b.ctx
    )

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

    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=b.display_label)]

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
        id=b.object_id,
        type="agreement",
        title=f"Agreement: {b.display_label}",
        explanation=explanation,
        fields=fields,
        examples=[b.display_label],
        drills=drills,
    )


def _build_script(b: _B) -> LessonResponse:
    """Lesson for a script character or sign."""
    character    = b.lesson_data.get("character") or b.display_label
    readings_raw = b.lesson_data.get("readings") or []
    readings: list[str] = (
        readings_raw if isinstance(readings_raw, list) else [str(readings_raw)]
    )
    meaning      = b.lesson_data.get("meaning") or b.lesson_data.get("gloss")
    stroke_count = b.lesson_data.get("stroke_count")
    notes        = b.lesson_data.get("notes")

    explanation = fmt.script_explanation(character, meaning, b.ctx)

    fields: list[LessonField] = [LessonField(label="Character", value=character)]
    if readings:
        fields.append(LessonField(label="Reading(s)", value=",  ".join(readings)))
    if meaning:
        fields.append(LessonField(label="Meaning", value=str(meaning)))
    if stroke_count is not None:
        fields.append(LessonField(label="Strokes", value=str(stroke_count)))
    if notes:
        fields.append(LessonField(label="Notes", value=str(notes)))

    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=character)]

    if readings:
        primary_reading = readings[0]
        drills.append(FillBlankDrill(
            type="fill_blank",
            prompt=f"How is \u201c{character}\u201d read?",
            answer=primary_reading,
            hint=f"(first reading)" if len(readings) > 1 else None,
        ))

    if meaning:
        drills.append(FillBlankDrill(
            type="fill_blank",
            prompt=f"What does \u201c{character}\u201d mean?",
            answer=str(meaning),
        ))

    return LessonResponse(
        id=b.object_id,
        type="script",  # type: ignore[arg-type]  # "script" ∈ LearnableType; mypy can't narrow str literals to a Literal type alias
        title=f"Script: {character}",
        explanation=explanation,
        fields=fields,
        examples=[character] + readings[:2],
        drills=drills,
    )


def _build_transliteration(b: _B) -> LessonResponse:
    """Lesson for a native-form ↔ romanization mapping."""
    native_form = b.lesson_data.get("native_form") or b.display_label
    romanized   = b.lesson_data.get("romanized") or b.canonical_form
    scheme      = b.lesson_data.get("scheme") or ""
    meaning     = b.lesson_data.get("meaning") or b.lesson_data.get("gloss")
    seed        = b.canonical_form

    explanation = fmt.transliteration_explanation(
        native_form, romanized, scheme, meaning, b.ctx
    )

    fields: list[LessonField] = [
        LessonField(label="Native form",  value=native_form),
        LessonField(label="Romanization", value=romanized),
    ]
    if scheme:
        fields.append(LessonField(label="Scheme", value=scheme))
    if meaning:
        fields.append(LessonField(label="Meaning", value=str(meaning)))

    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=native_form)]

    drills.append(FillBlankDrill(
        type="fill_blank",
        prompt=f"Romanize \u201c{native_form}\u201d.",
        answer=romanized,
    ))

    drills.append(FillBlankDrill(
        type="fill_blank",
        prompt=f"Write the native form for \u201c{romanized}\u201d.",
        answer=native_form,
    ))

    return LessonResponse(
        id=b.object_id,
        type="transliteration",  # type: ignore[arg-type]  # "transliteration" ∈ LearnableType; same mypy narrowing limitation
        title=f"Transliteration: {native_form}",
        explanation=explanation,
        fields=fields,
        examples=[native_form, romanized],
        drills=drills,
    )


def _build_dictionary(b: _B) -> LessonResponse:
    """Dictionary-mode lesson for plugins without full morphological analysis.

    Emits whatever the plugin reliably knows — gloss, romanization, citation
    form, grammar note — without asserting unverified morphological structure.
    Suitable for dead languages, under-resourced languages, or any plugin that
    declares ``analysis_depth="dictionary"``.

    Fields emitted (when present in lesson_data):
      - Gloss         — English meaning (or provider-supplied fallback).
      - Romanized     — Transliteration / phonetic reading (from
                        ``lesson_data["romanized"]`` or ``["pinyin"]``).
      - Citation form — Dictionary headword (e.g. ``"amor, amōris m."``).
      - Grammar       — Free-text grammar note (e.g. ``"3rd decl. masc."``).
      - Base form     — Shown when ``lemma`` differs from ``display_label``.
      - Note          — Confidence / provenance note.

    Drills:
      1. Shadowing (always).
      2. Fill-blank "What does X mean?" — only when a gloss is available.
    """
    gloss = b.lesson_data.get("gloss")

    # Provider-supplied gloss fallback — only when plugin has no gloss.
    if not gloss:
        gloss = b.prov.gloss.lookup(b.canonical_form, b.ctx.language_code)

    gloss_str: str | None = str(gloss) if gloss else None

    # Romanization: prefer the generic key; fall back to Mandarin-specific "pinyin".
    romanized = b.lesson_data.get("romanized") or b.lesson_data.get("pinyin")

    fields: list[LessonField] = []

    # Stored translation shown before gloss for quick comprehension.
    if translation := b.lesson_data.get("translation"):
        fields.append(LessonField(label="Translation", value=str(translation)))
    if gloss_str:
        fields.append(LessonField(label="Gloss", value=gloss_str))
    if romanized:
        fields.append(LessonField(label="Romanized", value=str(romanized)))
    if citation := b.lesson_data.get("citation_form"):
        fields.append(LessonField(label="Citation form", value=str(citation)))
    if grammar := b.lesson_data.get("grammar_note"):
        fields.append(LessonField(label="Grammar", value=str(grammar)))
    if lemma := b.lesson_data.get("lemma"):
        if str(lemma).lower() != b.display_label.lower():
            fields.append(LessonField(label="Base form", value=str(lemma)))
    if note := b.lesson_data.get("confidence_note"):
        fields.append(LessonField(label="Note", value=str(note)))

    explanation = fmt.dictionary_explanation(b.display_label, gloss_str, b.ctx)

    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=b.display_label)]

    if gloss_str:
        drills.append(FillBlankDrill(
            type="fill_blank",
            prompt=f"What does \u201c{b.display_label}\u201d mean?",
            answer=gloss_str,
        ))

    return LessonResponse(
        id=b.object_id,
        type=b.obj_type,  # type: ignore[arg-type]  # obj_type is str, not narrowed to LearnableType; Pydantic validates at runtime
        title=b.display_label,
        explanation=explanation,
        fields=fields,
        examples=[b.display_label],
        drills=drills,
    )


def _build_idiom(b: _B) -> LessonResponse:
    """Lesson for a multi-word idiomatic expression."""
    phrase   = b.lesson_data.get("phrase") or b.display_label
    meaning  = b.lesson_data.get("meaning") or ""
    register = b.lesson_data.get("register") or ""
    seed     = b.canonical_form

    explanation = fmt.idiom_explanation(phrase, meaning, b.ctx)

    fields: list[LessonField] = [LessonField(label="Phrase", value=phrase)]
    if meaning:
        fields.append(LessonField(label="Meaning", value=meaning))
    if register:
        fields.append(LessonField(label="Register", value=register))

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
        id=b.object_id,
        type="idiom",  # type: ignore[arg-type]  # "idiom" ∈ LearnableType; same mypy narrowing limitation
        title=f"Idiom: {phrase}",
        explanation=explanation,
        fields=fields,
        examples=[phrase],
        drills=drills,
    )


def _build_grammar(b: _B) -> LessonResponse:
    """Lesson for a periphrastic / structural grammar pattern."""
    pattern_id   = b.lesson_data.get("pattern_id") or b.canonical_form
    pattern      = b.lesson_data.get("pattern") or b.display_label
    usage        = b.lesson_data.get("usage") or ""
    contrast     = b.lesson_data.get("contrast") or ""
    surface_verb = b.lesson_data.get("surface_verb") or b.display_label

    explanation = fmt.grammar_explanation(pattern, usage, b.ctx)

    fields: list[LessonField] = [LessonField(label="Pattern", value=pattern)]
    if usage:
        fields.append(LessonField(label="Usage", value=usage))
    if contrast:
        fields.append(LessonField(label="Contrast", value=contrast))

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
        id=b.object_id,
        type="grammar",  # type: ignore[arg-type]  # "grammar" ∈ LearnableType; same mypy narrowing limitation
        title=f"Grammar: {pattern}",
        explanation=explanation,
        fields=fields,
        examples=[surface_verb],
        drills=drills,
    )


def _build_nuance(b: _B) -> LessonResponse:
    """Lesson for an aspect, mood, or verb-type nuance observation."""
    nuance_type    = b.lesson_data.get("nuance_type") or b.obj_type
    lemma          = b.lesson_data.get("lemma") or b.canonical_form
    surface        = b.lesson_data.get("surface") or b.display_label
    note           = b.lesson_data.get("note") or ""
    contrast_tense = b.lesson_data.get("contrast_tense") or ""

    _type_labels: dict[str, str] = {
        "imperfect_aspect": "Imperfect aspect",
        "subjunctive_mood": "Subjunctive mood",
        "reflexive_verb":   "Reflexive / pronominal verb",
    }
    type_label = _type_labels.get(nuance_type, nuance_type.replace("_", " ").title())

    explanation = fmt.nuance_explanation(surface, type_label, note, b.ctx)

    fields: list[LessonField] = [
        LessonField(label="Type", value=type_label),
        LessonField(label="Verb", value=lemma),
        LessonField(label="Surface form", value=surface),
    ]
    if note:
        fields.append(LessonField(label="Note", value=note))
    if contrast_tense:
        fields.append(LessonField(label="Contrast tense", value=contrast_tense))

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
        id=b.object_id,
        type="nuance",  # type: ignore[arg-type]  # "nuance" ∈ LearnableType; same mypy narrowing limitation
        title=f"{type_label}: {surface}",
        explanation=explanation,
        fields=fields,
        examples=[surface],
        drills=drills,
    )


def _build_case_agreement(b: _B) -> LessonResponse:
    """Lesson for a German-style case+gender+number agreement cluster."""
    modifier     = b.lesson_data.get("modifier") or b.display_label
    noun         = b.lesson_data.get("noun") or b.display_label
    modifier_pos = b.lesson_data.get("modifier_pos") or ""
    case         = b.lesson_data.get("case") or "unknown"
    gender       = b.lesson_data.get("gender") or "unknown"
    number       = b.lesson_data.get("number") or "unknown"
    case_match   = b.lesson_data.get("case_match")
    gender_match = b.lesson_data.get("gender_match")
    number_match = b.lesson_data.get("number_match")
    seed         = b.canonical_form

    case_display   = _CASE_DISPLAY.get(case, case.lower())
    gender_display = {"Masc": "masculine", "Fem": "feminine", "Neut": "neuter"}.get(
        gender, gender.lower()
    )
    number_display = {"Sing": "singular", "Plur": "plural"}.get(number, number.lower())
    pos_display    = _POS_DISPLAY.get(modifier_pos, modifier_pos.lower())

    confirmed: list[str] = []
    if case_match is True:
        confirmed.append("case")
    if gender_match is True:
        confirmed.append("gender")
    if number_match is True:
        confirmed.append("number")

    explanation = fmt.case_agreement_explanation(
        modifier, pos_display, noun, confirmed,
        gender_display, number_display, case_display, b.ctx
    )

    fields: list[LessonField] = [
        LessonField(label="Modifier", value=f"{modifier} ({pos_display})"),
        LessonField(label="Noun",     value=noun),
        LessonField(label="Case",     value=case_display),
        LessonField(label="Gender",   value=gender_display),
        LessonField(label="Number",   value=number_display),
    ]
    if case_match is not None:
        fields.append(LessonField(label="Case match",   value="yes" if case_match else "no"))
    if gender_match is not None:
        fields.append(LessonField(label="Gender match", value="yes" if gender_match else "no"))
    if number_match is not None:
        fields.append(LessonField(label="Number match", value="yes" if number_match else "no"))

    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=b.display_label)]

    if case_display != "unknown":
        mc = _make_mc_drill(
            seed=seed,
            prompt=f"What case is \u201c{modifier}\u201d \u2026 \u201c{noun}\u201d in?",
            correct=case_display,
            pool=_CASE_OPTIONS,
        )
        if mc:
            drills.append(mc)

    gender_options = ["masculine", "feminine", "neuter"]
    if gender_display in gender_options:
        mc_g = _make_mc_drill(
            seed=seed + "gender",
            prompt=f"What gender is \u201c{noun}\u201d?",
            correct=gender_display,
            pool=gender_options,
        )
        if mc_g:
            drills.append(mc_g)

    return LessonResponse(
        id=b.object_id,
        type="case_agreement",  # type: ignore[arg-type]  # "case_agreement" ∈ LearnableType; same mypy narrowing limitation
        title=f"Case agreement: {b.display_label}",
        explanation=explanation,
        fields=fields,
        examples=[b.display_label],
        drills=drills,
    )


def _build_generic(b: _B) -> LessonResponse:
    """Fallback for object types without a dedicated builder."""
    fields = [
        LessonField(label=k.replace("_", " ").title(), value=str(v))
        for k, v in b.lesson_data.items()
        if k not in ("confidence_note",) and v not in (None, "")
    ]
    return LessonResponse(
        id=b.object_id,
        type=b.obj_type,  # type: ignore[arg-type]  # obj_type is str, not narrowed to LearnableType; Pydantic validates at runtime
        title=f"{b.obj_type.replace('_', ' ').title()}: {b.display_label}",
        explanation=f"\u201c{b.display_label}\u201d \u2014 {b.obj_type.replace('_', ' ')}.",
        fields=fields,
        examples=[b.display_label],
        drills=[ShadowingDrill(type="shadowing", text=b.display_label)],
    )


# ── Dispatch tables ───────────────────────────────────────────────────────────
#
# _DEDICATED_BUILDERS: bypass lesson_mode entirely.
#   Tuple is (builder_fn, effective_LessonTemplate).
#   - "idiom" / "script" / "transliteration" → their own template name.
#   - "grammar" / "nuance" / "case_agreement" → report "morphology" since
#     they are derived from morphological analysis and their lesson content
#     belongs conceptually to the morphology tier.
#
# _MORPHOLOGY_BUILDERS: used when lesson_mode == "morphology".
#   Unknown types fall through to _build_generic.

_BuilderEntry = tuple[Callable[[_B], LessonResponse], LessonTemplate]

_DEDICATED_BUILDERS: dict[str, _BuilderEntry] = {
    "idiom":           (_build_idiom,          "idiom"),
    "script":          (_build_script,         "script"),
    "transliteration": (_build_transliteration,"transliteration"),
    "grammar":         (_build_grammar,        "morphology"),
    "nuance":          (_build_nuance,         "morphology"),
    "case_agreement":  (_build_case_agreement, "morphology"),
}

_MORPHOLOGY_BUILDERS: dict[str, Callable[[_B], LessonResponse]] = {
    "vocabulary":  _build_vocabulary,
    "conjugation": _build_conjugation,
    "agreement":   _build_agreement,
}


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
    wrong.sort(key=lambda x: _hash_key(seed + "wrong", x))
    chosen_wrong = wrong[:n_wrong]

    all_options = chosen_wrong + [correct]
    all_options.sort(key=lambda x: _hash_key(seed + "order", x))

    return MultipleChoiceDrill(
        type="multiple_choice",
        prompt=prompt,
        options=all_options,
        answer_index=all_options.index(correct),
    )
