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
import backend.lesson.l10n as l10n
from backend.lesson.context import LessonContext
from backend.lesson.enrichment import LessonEnrichmentContext
from backend.lesson.nuance_pairs import (
    build_discrimination_drills,
    get_nuance_sets_for_pattern,
    get_nuance_sets_for_type,
)
from backend.lesson.practice import build_practice_activities
from backend.lesson.providers import LessonProviders
from backend.schemas.language import LessonMode
from backend.schemas.lesson import (
    ContrastNote,
    DiscriminationDrill,
    Drill,
    EquivalentConstruction,
    FillBlankDrill,
    LessonField,
    LessonResponse,
    LessonTemplate,
    MorphologyAxis,
    MorphologyParadigm,
    MultipleChoiceDrill,
    NuanceSet,
    ParadigmCell,
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
    "WORD":  "word",       # EnglishPlugin
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
    "Abl": "ablative",
    "Voc": "vocative",
    "Ins": "instrumental",
    "Loc": "locative",
}
_CASE_OPTIONS: list[str] = ["nominative", "accusative", "dative", "genitive"]

# Extended case pool for declension systems with more than 4 cases (Latin, Russian, Greek).
_CASE_OPTIONS_EXTENDED: list[str] = [
    "nominative", "accusative", "dative", "genitive",
    "ablative", "vocative", "instrumental", "locative",
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

_ASPECT_OPTIONS: list[str] = ["imperfective", "perfective"]

_GENDER_DISPLAY: dict[str, str] = {
    "Masc": "masculine",
    "Fem":  "feminine",
    "Neut": "neuter",
}


# ── Morphology data extractors ────────────────────────────────────────────────

def _morphology_axes_from_lesson_data(ld: dict) -> list[MorphologyAxis]:
    """Extract MorphologyAxis list from *ld*.

    Tries ``ld["morphology"]["axes"]`` first; falls back to reading the flat
    tense/mood/person/number/gender/case/aspect/voice/polarity keys.
    Returns an empty list when no morphological data is present.
    """
    morph = ld.get("morphology")
    if isinstance(morph, dict):
        raw_axes = morph.get("axes")
        if isinstance(raw_axes, list):
            result: list[MorphologyAxis] = []
            for a in raw_axes:
                if isinstance(a, dict) and a.get("axis") and a.get("value"):
                    result.append(MorphologyAxis(
                        axis=str(a["axis"]),
                        value=str(a["value"]),
                        label=a.get("label"),
                        gloss=a.get("gloss"),
                    ))
            if result:
                return result

    # Flat fallback — normalise spaCy-style tag strings to canonical values.
    _norm: dict[str, dict[str, str]] = {
        "person": _PERSON_LABELS,
        "number": _NUMBER_LABELS,
        "gender": _GENDER_DISPLAY,
        "case":   _CASE_DISPLAY,
        "aspect": {"Imp": "imperfective", "Perf": "perfective"},
    }
    axes: list[MorphologyAxis] = []
    for axis_key in ("tense", "aspect", "mood", "person", "number", "gender", "case", "voice", "polarity"):
        raw = ld.get(axis_key)
        if not raw or str(raw) == "unknown":
            continue
        val_str = str(raw)
        normalized = _norm.get(axis_key, {}).get(val_str, val_str.lower())
        axes.append(MorphologyAxis(axis=axis_key, value=normalized))
    # Russian past tense reports gender instead of person under "person_or_gender"
    if "person_or_gender" in ld and not any(ax.axis == "person" for ax in axes):
        pg = str(ld["person_or_gender"])
        norm_pg = {**_GENDER_DISPLAY, "1": "first", "2": "second", "3": "third"}.get(pg, pg.lower())
        axes.append(MorphologyAxis(axis="person", value=norm_pg))
    return axes


def _paradigms_from_lesson_data(ld: dict) -> list[MorphologyParadigm]:
    """Extract MorphologyParadigm list from *ld*.

    Tries ``ld["morphology"]["paradigms"]`` first; falls back to
    ``ld["paradigm"]`` (a flat list of cell dicts).
    """
    morph = ld.get("morphology")
    if isinstance(morph, dict):
        raw_paradigms = morph.get("paradigms")
        if isinstance(raw_paradigms, list):
            result: list[MorphologyParadigm] = []
            for p in raw_paradigms:
                if not isinstance(p, dict):
                    continue
                cells: list[ParadigmCell] = []
                for c in (p.get("cells") or []):
                    if isinstance(c, dict) and c.get("form"):
                        cells.append(ParadigmCell(
                            form=str(c["form"]),
                            axes={k: str(v) for k, v in c.get("axes", {}).items()},
                            is_highlighted=bool(c.get("is_highlighted", False)),
                            gloss=c.get("gloss"),
                        ))
                result.append(MorphologyParadigm(
                    title=p.get("title"),
                    row_axis=p.get("row_axis"),
                    col_axis=p.get("col_axis"),
                    cells=cells,
                ))
            if result:
                return result

    # Flat "paradigm" key (list of cell dicts with mixed keys)
    raw = ld.get("paradigm")
    if isinstance(raw, list):
        cells = []
        for c in raw:
            if isinstance(c, dict) and c.get("form"):
                axes_dict = {
                    k: str(v) for k, v in c.items()
                    if k not in ("form", "is_highlighted", "gloss") and isinstance(v, str)
                }
                cells.append(ParadigmCell(
                    form=str(c["form"]),
                    axes=axes_dict,
                    is_highlighted=bool(c.get("is_highlighted", False)),
                    gloss=c.get("gloss"),
                ))
        if cells:
            return [MorphologyParadigm(cells=cells)]
    return []


def _equivalents_from_lesson_data(ld: dict) -> list[EquivalentConstruction]:
    """Extract EquivalentConstruction list from *ld*.

    Tries ``ld["morphology"]["equivalents"]`` first; falls back to
    ``ld["equivalents"]`` (list of str or dict).
    """
    morph = ld.get("morphology")
    if isinstance(morph, dict):
        raw = morph.get("equivalents")
        if isinstance(raw, list):
            result: list[EquivalentConstruction] = []
            for e in raw:
                if isinstance(e, dict) and e.get("construction"):
                    result.append(EquivalentConstruction(
                        construction=str(e["construction"]),
                        language_code=e.get("language_code"),
                        note=e.get("note"),
                        register=e.get("register"),
                    ))
            if result:
                return result

    raw = ld.get("equivalents")
    if not isinstance(raw, list):
        return []
    result = []
    for e in raw:
        if isinstance(e, str) and e:
            result.append(EquivalentConstruction(construction=e))
        elif isinstance(e, dict) and e.get("construction"):
            result.append(EquivalentConstruction(
                construction=str(e["construction"]),
                language_code=e.get("language_code"),
                note=e.get("note"),
                register=e.get("register"),
            ))
    return result


def _contrast_notes_from_lesson_data(ld: dict) -> list[ContrastNote]:
    """Extract ContrastNote list from *ld*.

    Tries ``ld["morphology"]["contrasts"]`` first; falls back to
    ``ld["contrasts"]`` (list of dicts with form_a/form_b/note keys).
    """
    morph = ld.get("morphology")
    if isinstance(morph, dict):
        raw = morph.get("contrasts")
        if isinstance(raw, list):
            result: list[ContrastNote] = []
            for c in raw:
                if isinstance(c, dict) and c.get("form_a") and c.get("form_b") and c.get("note"):
                    result.append(ContrastNote(
                        form_a=str(c["form_a"]),
                        form_b=str(c["form_b"]),
                        note=str(c["note"]),
                        example_a=c.get("example_a"),
                        example_b=c.get("example_b"),
                    ))
            if result:
                return result

    raw = ld.get("contrasts")
    if not isinstance(raw, list):
        return []
    result = []
    for c in raw:
        if isinstance(c, dict) and c.get("form_a") and c.get("form_b") and c.get("note"):
            result.append(ContrastNote(
                form_a=str(c["form_a"]),
                form_b=str(c["form_b"]),
                note=str(c["note"]),
                example_a=c.get("example_a"),
                example_b=c.get("example_b"),
            ))
    return result


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
    enrichment: LessonEnrichmentContext | None = None,
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

    # Stamp the effective template, language context, and raw lesson_data onto the response.
    update: dict[str, Any] = {"lesson_mode": effective_mode, "lesson_data": b.lesson_data}
    if ctx.language_code is not None:
        update["language_code"] = ctx.language_code
    if ctx.direction and ctx.language_code is not None:
        update["script_direction"] = ctx.direction
    if enrichment is not None and enrichment.related_vocabulary:
        update["encountered_vocabulary"] = enrichment.related_vocabulary

    stamped = response.model_copy(update=update)

    # Build learner_progress dict for practice activity difficulty tuning.
    lp: dict[str, Any] | None = None
    if enrichment is not None:
        lp = {"exposure_count": enrichment.exposure_count}
        if enrichment.mastery_score is not None:
            lp["mastery_score"] = enrichment.mastery_score

    return stamped.model_copy(update={
        "practice_activities": build_practice_activities(stamped, learner_progress=lp),
    })


# ── Type-specific builders ────────────────────────────────────────────────────

def _build_vocabulary(b: _B) -> LessonResponse:
    lemma   = b.lesson_data.get("lemma") or b.canonical_form
    pos_raw = b.lesson_data.get("pos") or "WORD"
    pos     = _POS_DISPLAY.get(pos_raw, pos_raw.lower())
    seed    = b.canonical_form
    l1      = b.ctx.l1_language

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

    if cefr := b.lesson_data.get("cefr_level"):
        fields.append(LessonField(label="CEFR level", value=cefr))

    if note := b.lesson_data.get("confidence_note"):
        fields.append(LessonField(label="Note", value=note))

    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=b.display_label)]

    mc = _make_mc_drill(
        seed=seed,
        prompt=l10n.t("drill.pos_blank", l1, word=b.display_label),
        correct=pos,
        pool=_POS_OPTIONS,
    )
    if mc:
        drills.append(mc)

    if b.display_label.lower() != lemma.lower():
        drills.append(FillBlankDrill(
            type="fill_blank",
            prompt=l10n.t("drill.lemma_blank", l1, word=b.display_label),
            answer=lemma,
        ))

    sentence_examples = [
        e for e in (b.lesson_data.get("examples") or [])
        if e and e != b.display_label
    ]
    return LessonResponse(
        id=b.object_id,
        type="vocabulary",
        title=l10n.t("drill.vocab_title", l1, word=b.display_label),
        explanation=explanation,
        fields=fields,
        examples=[b.display_label] + sentence_examples,
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
    l1      = b.ctx.l1_language

    person_label = _PERSON_LABELS.get(str(person), str(person))
    number_label = _NUMBER_LABELS.get(str(number), str(number))

    # Localized display values for field cards and drill options.
    person_loc = l10n.gram_label("person", person_label, l1)
    number_loc = l10n.gram_label("number", number_label, l1)
    tense_loc  = l10n.gram_label("tense",  tense,        l1)
    mood_loc   = l10n.gram_label("mood",   mood,         l1)

    # \u2500\u2500 Morphology extension data \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    axes        = _morphology_axes_from_lesson_data(b.lesson_data)
    paradigms   = _paradigms_from_lesson_data(b.lesson_data)
    equivalents = _equivalents_from_lesson_data(b.lesson_data)
    contrasts   = _contrast_notes_from_lesson_data(b.lesson_data)

    explanation = fmt.conjugation_explanation(
        surface, person_label, number_label, tense, mood, lemma, b.ctx
    )

    fields: list[LessonField] = [
        LessonField(label="Lemma", value=lemma),
        LessonField(label="Surface form", value=surface),
    ]
    if tense != "unknown":
        fields.append(LessonField(label="Tense", value=tense_loc))
    if mood != "unknown":
        fields.append(LessonField(label="Mood", value=mood_loc))
    if person != "unknown":
        fields.append(LessonField(label="Person", value=person_loc))
    if number != "unknown":
        fields.append(LessonField(label="Number", value=number_loc))

    # Aspect (Russian/Slavic languages)
    aspect_raw = b.lesson_data.get("aspect")
    if aspect_raw and str(aspect_raw) != "unknown":
        aspect_en = {"Imp": "imperfective", "Perf": "perfective"}.get(
            str(aspect_raw), str(aspect_raw).lower()
        )
        aspect_loc = l10n.gram_label("aspect", aspect_en, l1)
        fields.append(LessonField(label="Aspect", value=aspect_loc))
    else:
        aspect_en = None
        aspect_loc = None

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

    # Lemma recall
    drills.append(FillBlankDrill(
        type="fill_blank",
        prompt=l10n.t("drill.verb_form_blank", l1, word=surface),
        answer=lemma,
    ))

    # Tense MC
    if tense != "unknown":
        tense_pool_en = list(b.ctx.tense_pool) if b.ctx.tense_pool else _TENSE_OPTIONS
        tense_pool_loc = [l10n.gram_label("tense", v, l1) for v in tense_pool_en]
        mc = _make_mc_drill(
            seed=seed,
            prompt=l10n.t("drill.what_tense", l1, word=surface),
            correct=tense_loc,
            pool=tense_pool_loc,
        )
        if mc:
            drills.append(mc)

    # Mood MC
    if mood != "unknown":
        mood_pool_en = list(b.ctx.mood_pool) if b.ctx.mood_pool else _MOOD_OPTIONS
        mood_pool_loc = [l10n.gram_label("mood", v, l1) for v in mood_pool_en]
        mc_mood = _make_mc_drill(
            seed=seed + "mood",
            prompt=l10n.t("drill.what_mood", l1, word=surface),
            correct=mood_loc,
            pool=mood_pool_loc,
        )
        if mc_mood:
            drills.append(mc_mood)

    # Reflexive recognition
    if b.lesson_data.get("is_reflexive") is not None:
        drills.append(RecognitionDrill(
            type="recognition",
            statement=l10n.t("drill.reflexive_stmt", l1, word=surface),
            correct=bool(b.lesson_data["is_reflexive"]),
        ))

    # \u2500\u2500 New morphology drills \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

    # Aspect MC (Russian/Slavic)
    if aspect_en:
        asp_pool_loc = [l10n.gram_label("aspect", v, l1) for v in _ASPECT_OPTIONS]
        mc_asp = _make_mc_drill(
            seed=seed + "aspect",
            prompt=l10n.t("drill.what_aspect", l1, word=surface),
            correct=aspect_loc,
            pool=asp_pool_loc,
            n_wrong=1,
        )
        if mc_asp:
            drills.append(mc_asp)

    # Form recall \u2014 learner produces the surface form given its feature description
    recall_parts: list[str] = []
    if person_label not in ("unknown", ""):
        recall_parts.append(person_loc)
    if number_label not in ("unknown", ""):
        recall_parts.append(number_loc)
    if tense not in ("unknown", ""):
        recall_parts.append(tense_loc)
    if mood not in ("unknown", ""):
        recall_parts.append(mood_loc)
    d_recall = _make_form_recall_drill(seed, surface, lemma, " ".join(recall_parts), l1)
    if d_recall:
        drills.append(d_recall)

    # Paradigm-cell drills (at most 2 non-highlighted cells)
    drills.extend(_make_paradigm_drills(seed, paradigms, lemma, l1, limit=2))

    # Equivalent construction choice
    eq_drill = _make_equivalent_drill(seed, equivalents, surface, l1)
    if eq_drill:
        drills.append(eq_drill)

    # Contrastive recognition (first contrast only)
    drills.extend(_make_contrast_drills(contrasts[:1]))

    return LessonResponse(
        id=b.object_id,
        type="conjugation",
        title=l10n.t("drill.conj_title", l1, word=surface),
        explanation=explanation,
        fields=fields,
        examples=[surface],
        drills=drills,
        morphology_axes=axes,
        paradigms=paradigms,
        equivalents=equivalents,
        contrasts=contrasts,
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
    l1             = b.ctx.l1_language

    gender_loc = l10n.gram_label("gender", gender_display, l1)
    number_loc = l10n.gram_label("number", number_display, l1)

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
        LessonField(label="Gender", value=gender_loc),
        LessonField(label="Number", value=number_loc),
    ]
    if gender_match is not None:
        fields.append(LessonField(label="Gender match", value="yes" if gender_match else "no"))
    if number_match is not None:
        fields.append(LessonField(label="Number match", value="yes" if number_match else "no"))

    axes = _morphology_axes_from_lesson_data(b.lesson_data)

    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=b.display_label)]

    if gender_match is True:
        drills.append(RecognitionDrill(
            type="recognition",
            statement=l10n.t("drill.agree_gender_stmt", l1, mod=modifier, noun=noun),
            correct=True,
        ))

    gender_options_en = ["masculine", "feminine", "neuter", "unknown"]
    gender_options_loc = [l10n.gram_label("gender", v, l1) for v in gender_options_en]
    mc = _make_mc_drill(
        seed=seed,
        prompt=l10n.t("drill.what_gender", l1, word=noun),
        correct=gender_loc,
        pool=gender_options_loc,
    )
    if mc:
        drills.append(mc)

    return LessonResponse(
        id=b.object_id,
        type="agreement",
        title=l10n.t("drill.agree_title", l1, word=b.display_label),
        explanation=explanation,
        fields=fields,
        examples=[b.display_label],
        drills=drills,
        morphology_axes=axes,
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


_MATCH_TYPE_LABELS: dict[str, str] = {
    "exact":                "Canonical form",
    "orthographic_variant": "Spelling variant",
    "modernized_variant":   "Modernised form",
    "inflectional_variant": "Inflectional variant",
    "misquotation":         "Common misquote",
    "blend":                "Blend / corruption",
    "allusion":             "Allusion",
    "confusable_not_same":  "Confusable \u2014 different meaning",
}


def _build_phrase_family(b: _B) -> LessonResponse:
    """Lesson for a phrase-family object.

    lesson_data keys (set by phrase_families.py):
      canonical_form, matched_variant, match_type, match_type_note (opt),
      meaning, register, origin (opt), source_text (opt), why_it_matters (opt),
      variants (list[dict] surface/match_type/note),
      confusable_forms (list[dict] surface/note, opt),
      confusables (list[str] family IDs, opt).
    """
    canonical        = b.lesson_data.get("canonical_form") or b.canonical_form
    matched          = b.lesson_data.get("matched_variant") or canonical
    match_type       = b.lesson_data.get("match_type") or "exact"
    match_type_note  = b.lesson_data.get("match_type_note") or ""
    meaning          = b.lesson_data.get("meaning") or ""
    register         = b.lesson_data.get("register") or ""
    origin           = b.lesson_data.get("origin") or ""
    source_text      = b.lesson_data.get("source_text") or ""
    why_it_matters   = b.lesson_data.get("why_it_matters") or ""
    raw_variants     = b.lesson_data.get("variants") or []
    confusables      = b.lesson_data.get("confusables") or []
    seed             = b.canonical_form

    # variants may be list[dict] (new) or list[str] (legacy)
    variant_surfaces: list[str] = [
        (v["surface"] if isinstance(v, dict) else v) for v in raw_variants
    ]

    is_exact = match_type == "exact"
    mt_label = _MATCH_TYPE_LABELS.get(match_type, match_type.replace("_", " ").title())
    title    = f"Phrase family: {canonical}"

    if meaning:
        explanation = f"\u201c{canonical}\u201d \u2014 {meaning}"
    else:
        explanation = f"\u201c{canonical}\u201d is an idiomatic phrase."

    fields: list[LessonField] = [
        LessonField(label="Canonical form", value=canonical),
    ]
    if not is_exact:
        fields.append(LessonField(label="Matched variant", value=matched))
        fields.append(LessonField(label="Match type",      value=mt_label))
        if match_type_note:
            fields.append(LessonField(label="Note", value=match_type_note))
    if meaning:
        fields.append(LessonField(label="Meaning", value=meaning))
    if register:
        fields.append(LessonField(label="Register", value=register))
    if source_text:
        fields.append(LessonField(label="Source", value=source_text))
    if origin:
        fields.append(LessonField(label="Origin", value=origin))
    if why_it_matters:
        fields.append(LessonField(label="Why it matters", value=why_it_matters))
    if variant_surfaces:
        fields.append(LessonField(label="Known variants", value=" / ".join(variant_surfaces)))
    if confusables:
        fields.append(LessonField(label="Confusable with", value=", ".join(confusables)))

    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=matched)]

    if meaning:
        drills.append(FillBlankDrill(
            type="fill_blank",
            prompt=f"What does \u201c{canonical}\u201d mean?",
            answer=meaning,
        ))

    if register:
        register_pool = ["neutral", "literary", "formal", "informal", "archaic"]
        mc = _make_mc_drill(
            seed=seed,
            prompt=f"What register is \u201c{canonical}\u201d?",
            correct=register,
            pool=register_pool,
        )
        if mc:
            drills.append(mc)

    if not is_exact:
        drills.append(RecognitionDrill(
            type="recognition",
            statement=f"\u201c{matched}\u201d is the most widely cited form of this expression.",
            correct=False,
        ))
    else:
        drills.append(RecognitionDrill(
            type="recognition",
            statement=f"\u201c{canonical}\u201d is the canonical form of this expression.",
            correct=True,
        ))

    return LessonResponse(
        id=b.object_id,
        type="phrase_family",  # type: ignore[arg-type]
        title=title,
        explanation=explanation,
        fields=fields,
        examples=[matched],
        drills=drills,
    )


def _build_grammar(b: _B) -> LessonResponse:
    """Lesson for a periphrastic / structural grammar pattern."""
    pattern_id   = b.lesson_data.get("pattern_id") or b.canonical_form
    pattern      = b.lesson_data.get("pattern") or b.display_label
    usage        = b.lesson_data.get("usage") or ""
    contrast     = b.lesson_data.get("contrast") or ""
    surface_verb = b.lesson_data.get("surface_verb") or b.display_label
    lang         = b.ctx.language_code or ""

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
            statement=f"The pattern “{pattern}” is used for: {usage[:80]}{'...' if len(usage) > 80 else ''}",
            correct=True,
        ))

    if contrast:
        drills.append(RecognitionDrill(
            type="recognition",
            statement=f"The pattern “{pattern}” can replace a related construction without any meaning difference.",
            correct=False,
        ))

    # Meaning-discrimination drills from curated minimal-pair data.
    if lang:
        drills.extend(build_discrimination_drills(lang, pattern_id=pattern_id))

    # Nuance sets for the UI "Nuance" tab.
    nuance_sets: list[NuanceSet] = get_nuance_sets_for_pattern(lang, pattern_id) if lang else []

    return LessonResponse(
        id=b.object_id,
        type="grammar",  # type: ignore[arg-type]  # "grammar" ∈ LearnableType; same mypy narrowing limitation
        title=f"Grammar: {pattern}",
        explanation=explanation,
        fields=fields,
        examples=[surface_verb],
        drills=drills,
        nuance_sets=nuance_sets,
    )

def _build_nuance(b: _B) -> LessonResponse:
    """Lesson for an aspect, mood, or verb-type nuance observation."""
    nuance_type    = b.lesson_data.get("nuance_type") or b.obj_type
    lemma          = b.lesson_data.get("lemma") or b.canonical_form
    surface        = b.lesson_data.get("surface") or b.display_label
    note           = b.lesson_data.get("note") or ""
    contrast_tense = b.lesson_data.get("contrast_tense") or ""
    lang           = b.ctx.language_code or ""

    _type_labels: dict[str, str] = {
        "imperfect_aspect":           "Imperfect aspect",
        "subjunctive_mood":           "Subjunctive mood",
        "reflexive_verb":             "Reflexive / pronominal verb",
        "russian_aspect":             "Aspect",
        "perfective_vs_imperfective": "Aspect",
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
            statement=f"“{surface}” ({type_label}) describes a completed, one-time past event.",
            correct=(nuance_type != "imperfect_aspect"),
        ))

    if contrast_tense:
        drills.append(FillBlankDrill(
            type="fill_blank",
            prompt=f"The tense that contrasts with the imperfect for a single completed event is the ———.",
            answer=contrast_tense,
        ))

    # Meaning-discrimination drills from curated minimal-pair data.
    if lang:
        drills.extend(build_discrimination_drills(lang, nuance_type=nuance_type))

    # Nuance sets for the UI "Nuance" tab.
    nuance_sets: list[NuanceSet] = get_nuance_sets_for_type(lang, nuance_type) if lang else []

    return LessonResponse(
        id=b.object_id,
        type="nuance",  # type: ignore[arg-type]  # "nuance" ∈ LearnableType; same mypy narrowing limitation
        title=f"{type_label}: {surface}",
        explanation=explanation,
        fields=fields,
        examples=[surface],
        drills=drills,
        nuance_sets=nuance_sets,
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
    l1             = b.ctx.l1_language

    case_loc   = l10n.gram_label("case",   case_display,   l1)
    gender_loc = l10n.gram_label("gender", gender_display, l1)
    number_loc = l10n.gram_label("number", number_display, l1)

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
        LessonField(label="Case",     value=case_loc),
        LessonField(label="Gender",   value=gender_loc),
        LessonField(label="Number",   value=number_loc),
    ]
    if case_match is not None:
        fields.append(LessonField(label="Case match",   value="yes" if case_match else "no"))
    if gender_match is not None:
        fields.append(LessonField(label="Gender match", value="yes" if gender_match else "no"))
    if number_match is not None:
        fields.append(LessonField(label="Number match", value="yes" if number_match else "no"))

    axes      = _morphology_axes_from_lesson_data(b.lesson_data)
    contrasts = _contrast_notes_from_lesson_data(b.lesson_data)

    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=b.display_label)]

    if case_display != "unknown":
        case_options_loc = [l10n.gram_label("case", v, l1) for v in _CASE_OPTIONS]
        mc = _make_mc_drill(
            seed=seed,
            prompt=l10n.t("drill.what_case", l1, mod=modifier, noun=noun),
            correct=case_loc,
            pool=case_options_loc,
        )
        if mc:
            drills.append(mc)

    gender_options_en = ["masculine", "feminine", "neuter"]
    if gender_display in gender_options_en:
        gender_options_loc = [l10n.gram_label("gender", v, l1) for v in gender_options_en]
        mc_g = _make_mc_drill(
            seed=seed + "gender",
            prompt=l10n.t("drill.what_gender", l1, word=noun),
            correct=gender_loc,
            pool=gender_options_loc,
        )
        if mc_g:
            drills.append(mc_g)

    drills.extend(_make_contrast_drills(contrasts[:1]))

    return LessonResponse(
        id=b.object_id,
        type="case_agreement",  # type: ignore[arg-type]  # "case_agreement" ∈ LearnableType; same mypy narrowing limitation
        title=l10n.t("drill.case_agree_title", l1, word=b.display_label),
        explanation=explanation,
        fields=fields,
        examples=[b.display_label],
        drills=drills,
        morphology_axes=axes,
        contrasts=contrasts,
    )


def _build_inflection(b: _B) -> LessonResponse:
    """Lesson for a declined nominal (noun/adjective/pronoun) form.

    Expected lesson_data keys:
      lemma (req), surface (req), case, gender, number, pos,
      declension_class (opt), translation (opt), voice (opt),
      tense (opt — for participles), confidence_note (opt).
      morphology (opt) — rich extension sub-object.
    """
    lemma   = b.lesson_data.get("lemma") or b.canonical_form
    surface = b.lesson_data.get("surface") or b.display_label
    case    = b.lesson_data.get("case") or "unknown"
    gender  = b.lesson_data.get("gender") or "unknown"
    number  = b.lesson_data.get("number") or "unknown"
    pos_raw = b.lesson_data.get("pos") or "NOUN"
    pos     = _POS_DISPLAY.get(pos_raw, pos_raw.lower())
    seed    = b.canonical_form
    l1      = b.ctx.l1_language

    case_display   = _CASE_DISPLAY.get(str(case),   str(case).lower())
    gender_display = _GENDER_DISPLAY.get(str(gender), str(gender).lower())
    number_display = _NUMBER_LABELS.get(str(number),  str(number).lower())

    case_loc   = l10n.gram_label("case",   case_display,   l1)
    gender_loc = l10n.gram_label("gender", gender_display, l1)
    number_loc = l10n.gram_label("number", number_display, l1)

    # ── Morphology extension data ─────────────────────────────────────────────
    axes        = _morphology_axes_from_lesson_data(b.lesson_data)
    paradigms   = _paradigms_from_lesson_data(b.lesson_data)
    equivalents = _equivalents_from_lesson_data(b.lesson_data)
    contrasts   = _contrast_notes_from_lesson_data(b.lesson_data)

    explanation = fmt.inflection_explanation(
        surface, pos, case_display, gender_display, number_display, lemma, b.ctx
    )

    fields: list[LessonField] = [
        LessonField(label="Lemma", value=lemma),
        LessonField(label="Surface form", value=surface),
        LessonField(label="Part of speech", value=pos),
    ]
    if case_display not in ("unknown", ""):
        fields.append(LessonField(label="Case", value=case_loc))
    if gender_display not in ("unknown", ""):
        fields.append(LessonField(label="Gender", value=gender_loc))
    if number_display not in ("unknown", ""):
        fields.append(LessonField(label="Number", value=number_loc))
    if decl := b.lesson_data.get("declension_class"):
        fields.append(LessonField(label="Declension", value=str(decl)))
    if translation := b.lesson_data.get("translation"):
        fields.append(LessonField(label="Translation", value=str(translation)))
    if note := b.lesson_data.get("confidence_note"):
        fields.append(LessonField(label="Note", value=note))

    drills: list[Drill] = [ShadowingDrill(type="shadowing", text=surface)]

    # Lemma recall
    if surface.lower() != lemma.lower():
        drills.append(FillBlankDrill(
            type="fill_blank",
            prompt=l10n.t("drill.lemma_blank", l1, word=surface),
            answer=lemma,
        ))

    # Case MC — use extended pool for rich declension systems (Latin, Russian, …)
    if case_display not in ("unknown", ""):
        case_pool_loc = [l10n.gram_label("case", v, l1) for v in _CASE_OPTIONS_EXTENDED]
        mc_case = _make_mc_drill(
            seed=seed,
            prompt=l10n.t("drill.what_case", l1, mod=surface, noun=lemma),
            correct=case_loc,
            pool=case_pool_loc,
        )
        if mc_case:
            drills.append(mc_case)

    # Gender MC
    if gender_display not in ("unknown", ""):
        g_options_en = ["masculine", "feminine", "neuter"] if gender_display == "neuter" \
                       else ["masculine", "feminine"]
        g_options_loc = [l10n.gram_label("gender", v, l1) for v in g_options_en]
        mc_g = _make_mc_drill(
            seed=seed + "gender",
            prompt=l10n.t("drill.what_gender", l1, word=lemma),
            correct=gender_loc,
            pool=g_options_loc,
        )
        if mc_g:
            drills.append(mc_g)

    # Form recall
    recall_parts: list[str] = []
    if case_display not in ("unknown", ""):
        recall_parts.append(case_loc)
    if number_display not in ("unknown", ""):
        recall_parts.append(number_loc)
    if gender_display not in ("unknown", ""):
        recall_parts.append(gender_loc)
    d_recall = _make_form_recall_drill(seed, surface, lemma, " ".join(recall_parts), l1)
    if d_recall:
        drills.append(d_recall)

    # Paradigm-cell drills (at most 2 non-highlighted cells)
    drills.extend(_make_paradigm_drills(seed, paradigms, lemma, l1, limit=2))

    # Contrastive recognition
    drills.extend(_make_contrast_drills(contrasts[:1]))

    return LessonResponse(
        id=b.object_id,
        type="inflection",  # type: ignore[arg-type]
        title=l10n.t("drill.inflection_title", l1, word=surface),
        explanation=explanation,
        fields=fields,
        examples=[surface],
        drills=drills,
        morphology_axes=axes,
        paradigms=paradigms,
        equivalents=equivalents,
        contrasts=contrasts,
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
    "phrase_family":   (_build_phrase_family,  "phrase_family"),
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
    "inflection":  _build_inflection,
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


# ── Morphology drill factories ────────────────────────────────────────────────

def _make_form_recall_drill(
    seed: str,
    surface: str,
    lemma: str,
    features_str: str,
    l1: str,
) -> FillBlankDrill | None:
    """Fill-blank asking the learner to produce *surface* given a features description.

    Returns None when *features_str* is empty (nothing meaningful to describe).
    """
    if not features_str:
        return None
    prompt = l10n.t(
        "drill.form_recall", l1,
        features=features_str,
        lemma=f"“{lemma}”",
    )
    if not prompt:
        return None
    return FillBlankDrill(type="fill_blank", prompt=prompt, answer=surface)


def _make_paradigm_drills(
    seed: str,
    paradigms: list[MorphologyParadigm],
    lemma: str,
    l1: str,
    *,
    limit: int = 2,
) -> list[Drill]:
    """Fill-blank drills for *limit* deterministically chosen non-highlighted cells."""
    result: list[Drill] = []
    for paradigm in paradigms:
        if len(result) >= limit:
            break
        non_highlighted = [c for c in paradigm.cells if not c.is_highlighted and c.form]
        sorted_cells = sorted(non_highlighted, key=lambda c: _hash_key(seed + "par", c.form))
        for cell in sorted_cells:
            if len(result) >= limit:
                break
            axes_desc = " ".join(
                f"{k} {v}"
                for k, v in sorted(cell.axes.items())
                if k in ("person", "number", "tense", "mood", "case", "gender")
            )
            if not axes_desc:
                continue
            prompt = l10n.t(
                "drill.paradigm_cell", l1,
                features=axes_desc,
                lemma=f"“{lemma}”",
            )
            if not prompt:
                prompt = f"Give the {axes_desc} form of “{lemma}”."
            result.append(FillBlankDrill(type="fill_blank", prompt=prompt, answer=cell.form))
    return result


def _make_equivalent_drill(
    seed: str,
    equivalents: list[EquivalentConstruction],
    surface: str,
    l1: str,
) -> MultipleChoiceDrill | None:
    """MC drill asking the learner to identify an equivalent construction.

    Returns None when the pool cannot support 3 distinct wrong options.
    """
    if not equivalents:
        return None
    correct = equivalents[0].construction
    # Pool: all equivalent constructions + the surface form itself (always wrong).
    pool = [e.construction for e in equivalents] + [surface]
    prompt = l10n.t("drill.choose_equivalent", l1, word=f"“{surface}”")
    if not prompt:
        return None
    return _make_mc_drill(seed=seed + "equiv", prompt=prompt, correct=correct, pool=pool)


def _make_contrast_drills(contrasts: list[ContrastNote]) -> list[RecognitionDrill]:
    """One RecognitionDrill (correct=False) per contrast pair.

    The statement claims the two forms are interchangeable; the correct answer
    is False because they differ — that is the pedagogical point.
    """
    return [
        RecognitionDrill(
            type="recognition",
            statement=(
                f"“{c.form_a}” and “{c.form_b}” "
                f"are interchangeable in all contexts."
            ),
            correct=False,
        )
        for c in contrasts
    ]
