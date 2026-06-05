"""Tests for the morphology-extended lesson generators.

Covers:
  1. Extractor functions (_morphology_axes_from_lesson_data etc.)
  2. _build_conjugation enriched drills and fields for Romance/Slavic verbs
  3. _build_case_agreement with German/Russian case data
  4. _build_inflection for Latin declension
  5. Morphology-light paths: Arabic/Hebrew Semitic hints, CJK dictionary mode
  6. Backwards compatibility — existing lesson_data produces identical core output

Run:
    pytest backend/tests/test_morphology_generators.py -v
"""
from __future__ import annotations

import pytest

from backend.lesson.generators import (
    _contrast_notes_from_lesson_data,
    _equivalents_from_lesson_data,
    _morphology_axes_from_lesson_data,
    _paradigms_from_lesson_data,
    build_lesson,
)
from backend.lesson.context import LessonContext
from backend.schemas.lesson import (
    FillBlankDrill,
    MultipleChoiceDrill,
    RecognitionDrill,
    ShadowingDrill,
)


# ── Shared lesson_data fixtures ────────────────────────────────────────────────

_ES_CONJ = {
    "lemma": "hablar", "surface": "hablo",
    "tense": "present", "mood": "indicative",
    "person": "1", "number": "Sing",
    "morph_complete": True, "construction": "standalone", "is_reflexive": False,
}

_FR_CONJ = {
    "lemma": "parler", "surface": "parle",
    "tense": "present", "mood": "indicative",
    "person": "1", "number": "Sing",
}

_PT_CONJ = {
    "lemma": "falar", "surface": "falo",
    "tense": "present", "mood": "indicative",
    "person": "1", "number": "Sing",
}

_IT_CONJ = {
    "lemma": "parlare", "surface": "parlo",
    "tense": "present", "mood": "indicative",
    "person": "1", "number": "Sing",
}

_RU_CONJ = {
    "lemma": "говорить", "surface": "говорю",
    "tense": "present", "mood": "indicative",
    "person": "1", "number": "Sing",
    "aspect": "Imp",
}

_DE_CASE = {
    "modifier": "des", "modifier_pos": "DET",
    "noun": "Mannes", "case": "Gen",
    "gender": "Masc", "number": "Sing",
    "case_match": True, "gender_match": True, "number_match": True,
}

_RU_CASE = {
    "modifier": "большого", "modifier_pos": "ADJ",
    "noun": "города", "case": "Gen",
    "gender": "Masc", "number": "Sing",
    "case_match": True, "gender_match": True, "number_match": True,
}

_LA_INFLECT = {
    "lemma": "rex", "surface": "regem",
    "case": "Acc", "gender": "Masc", "number": "Sing",
    "pos": "NOUN", "declension_class": "3rd", "translation": "king",
}

_LA_CONJ_FLAT = {
    "lemma": "amare", "surface": "amo",
    "tense": "present", "mood": "indicative",
    "person": "1", "number": "Sing",
}

_AR_DICT = {"gloss": "write", "romanized": "kataba", "translation": "he wrote"}
_HE_DICT = {"gloss": "house", "translation": "house"}
_ZH_DICT = {"gloss": "love", "pinyin": "ài", "translation": "love"}
_JA_DICT = {"gloss": "cat", "translation": "cat"}

_RICH_CONJ = {
    **_ES_CONJ,
    "morphology": {
        "axes": [
            {"axis": "tense", "value": "present"},
            {"axis": "mood", "value": "indicative"},
            {"axis": "person", "value": "first"},
            {"axis": "number", "value": "singular"},
        ],
        "paradigms": [{
            "title": "Present Indicative",
            "row_axis": "person",
            "col_axis": "number",
            "cells": [
                {"form": "hablo",    "axes": {"person": "1", "number": "Sing"}, "is_highlighted": True},
                {"form": "hablas",   "axes": {"person": "2", "number": "Sing"}},
                {"form": "habla",    "axes": {"person": "3", "number": "Sing"}},
                {"form": "hablamos", "axes": {"person": "1", "number": "Plur"}},
                {"form": "habláis",  "axes": {"person": "2", "number": "Plur"}},
                {"form": "hablan",   "axes": {"person": "3", "number": "Plur"}},
            ],
        }],
        "equivalents": [
            {"construction": "estoy hablando", "note": "progressive"},
            {"construction": "he hablado",     "note": "perfect"},
            {"construction": "voy a hablar",   "note": "near future"},
            {"construction": "suelo hablar",   "note": "habitual"},
        ],
        "contrasts": [
            {"form_a": "hablo", "form_b": "hablaría", "note": "indicative vs conditional"},
        ],
    },
}


def _build(obj_type, cf, label, ld, *, ctx=None):
    return build_lesson(
        object_id="test-id",
        obj_type=obj_type,
        canonical_form=cf,
        display_label=label,
        lesson_data=ld,
        context=ctx,
    )


# ── 1. Extractor functions ─────────────────────────────────────────────────────

class TestMorphologyAxesExtractor:
    def test_rich_morphology_axes_used(self):
        axes = _morphology_axes_from_lesson_data(_RICH_CONJ)
        assert len(axes) == 4
        assert axes[0].axis == "tense" and axes[0].value == "present"
        assert axes[1].axis == "mood" and axes[1].value == "indicative"
        assert axes[2].axis == "person" and axes[2].value == "first"
        assert axes[3].axis == "number" and axes[3].value == "singular"

    def test_flat_fallback_tense_mood(self):
        axes = _morphology_axes_from_lesson_data(_ES_CONJ)
        axis_names = {ax.axis for ax in axes}
        assert "tense" in axis_names
        assert "mood" in axis_names

    def test_flat_fallback_person_normalized(self):
        axes = _morphology_axes_from_lesson_data(_ES_CONJ)
        person_ax = next(ax for ax in axes if ax.axis == "person")
        assert person_ax.value == "first"

    def test_flat_fallback_number_normalized(self):
        axes = _morphology_axes_from_lesson_data(_ES_CONJ)
        num_ax = next(ax for ax in axes if ax.axis == "number")
        assert num_ax.value == "singular"

    def test_aspect_flat(self):
        axes = _morphology_axes_from_lesson_data(_RU_CONJ)
        asp = next((ax for ax in axes if ax.axis == "aspect"), None)
        assert asp is not None and asp.value == "imperfective"

    def test_empty_lesson_data_returns_empty(self):
        assert _morphology_axes_from_lesson_data({}) == []

    def test_case_normalized(self):
        ld = {"case": "Gen", "gender": "Masc", "number": "Sing"}
        axes = _morphology_axes_from_lesson_data(ld)
        case_ax = next(ax for ax in axes if ax.axis == "case")
        assert case_ax.value == "genitive"

    def test_case_ablative(self):
        ld = {"case": "Abl"}
        axes = _morphology_axes_from_lesson_data(ld)
        case_ax = next(ax for ax in axes if ax.axis == "case")
        assert case_ax.value == "ablative"


class TestParadigmsExtractor:
    def test_rich_paradigms_extracted(self):
        paradigms = _paradigms_from_lesson_data(_RICH_CONJ)
        assert len(paradigms) == 1
        assert paradigms[0].title == "Present Indicative"
        assert len(paradigms[0].cells) == 6

    def test_highlighted_cell_preserved(self):
        paradigms = _paradigms_from_lesson_data(_RICH_CONJ)
        highlighted = [c for c in paradigms[0].cells if c.is_highlighted]
        assert len(highlighted) == 1
        assert highlighted[0].form == "hablo"

    def test_flat_paradigm_key(self):
        ld = {"paradigm": [
            {"form": "rex",   "case": "Nom", "is_highlighted": True},
            {"form": "regis", "case": "Gen"},
        ]}
        paradigms = _paradigms_from_lesson_data(ld)
        assert len(paradigms) == 1
        assert len(paradigms[0].cells) == 2

    def test_no_paradigm_returns_empty(self):
        assert _paradigms_from_lesson_data({}) == []


class TestEquivalentsExtractor:
    def test_rich_equivalents(self):
        eq = _equivalents_from_lesson_data(_RICH_CONJ)
        assert len(eq) == 4
        assert eq[0].construction == "estoy hablando"

    def test_flat_string_list(self):
        ld = {"equivalents": ["estoy hablando", "he hablado"]}
        eq = _equivalents_from_lesson_data(ld)
        assert len(eq) == 2
        assert eq[1].construction == "he hablado"

    def test_flat_dict_list(self):
        ld = {"equivalents": [{"construction": "estoy hablando", "note": "progressive"}]}
        eq = _equivalents_from_lesson_data(ld)
        assert eq[0].note == "progressive"

    def test_empty_returns_empty(self):
        assert _equivalents_from_lesson_data({}) == []


class TestContrastsExtractor:
    def test_rich_contrasts(self):
        contrasts = _contrast_notes_from_lesson_data(_RICH_CONJ)
        assert len(contrasts) == 1
        assert contrasts[0].form_a == "hablo"
        assert contrasts[0].form_b == "hablaría"

    def test_flat_contrasts(self):
        ld = {"contrasts": [{"form_a": "a", "form_b": "b", "note": "they differ"}]}
        contrasts = _contrast_notes_from_lesson_data(ld)
        assert contrasts[0].note == "they differ"

    def test_empty_returns_empty(self):
        assert _contrast_notes_from_lesson_data({}) == []


# ── 2. Conjugation builder — Romance/Slavic verbs ─────────────────────────────

class TestConjugationMorphologyAxes:
    def test_spanish_axes_populated(self):
        lesson = _build("conjugation", "hablar:present:indicative:1:Sing", "hablo", _ES_CONJ)
        assert len(lesson.morphology_axes) >= 2
        names = {ax.axis for ax in lesson.morphology_axes}
        assert "tense" in names and "mood" in names

    def test_french_axes_populated(self):
        lesson = _build("conjugation", "parler:present:indicative:1:Sing", "parle", _FR_CONJ)
        names = {ax.axis for ax in lesson.morphology_axes}
        assert "tense" in names

    def test_portuguese_axes_populated(self):
        lesson = _build("conjugation", "falar:present:indicative:1:Sing", "falo", _PT_CONJ)
        names = {ax.axis for ax in lesson.morphology_axes}
        assert "tense" in names

    def test_italian_axes_populated(self):
        lesson = _build("conjugation", "parlare:present:indicative:1:Sing", "parlo", _IT_CONJ)
        names = {ax.axis for ax in lesson.morphology_axes}
        assert "tense" in names

    def test_russian_aspect_axis(self):
        lesson = _build("conjugation", "говорить:present:indicative:1:Sing", "говорю", _RU_CONJ)
        names = {ax.axis for ax in lesson.morphology_axes}
        assert "aspect" in names
        asp = next(ax for ax in lesson.morphology_axes if ax.axis == "aspect")
        assert asp.value == "imperfective"


class TestConjugationNewDrills:
    def test_form_recall_drill_present(self):
        lesson = _build("conjugation", "hablar:present:indicative:1:Sing", "hablo", _ES_CONJ)
        form_recall = [d for d in lesson.drills if isinstance(d, FillBlankDrill) and d.answer == "hablo"]
        assert len(form_recall) >= 1

    def test_russian_aspect_mc_drill(self):
        lesson = _build("conjugation", "говорить:present:indicative:1:Sing", "говорю", _RU_CONJ)
        mc_drills = [d for d in lesson.drills if isinstance(d, MultipleChoiceDrill)]
        # Should have a tense MC and an aspect MC
        assert len(mc_drills) >= 2

    def test_rich_paradigm_drills_generated(self):
        lesson = _build("conjugation", "hablar:present:indicative:1:Sing", "hablo", _RICH_CONJ)
        fill_blanks = [d for d in lesson.drills if isinstance(d, FillBlankDrill)]
        # Should have lemma recall + form recall + at most 2 paradigm cell drills
        assert len(fill_blanks) >= 3

    def test_rich_equivalents_mc_drill(self):
        lesson = _build("conjugation", "hablar:present:indicative:1:Sing", "hablo", _RICH_CONJ)
        mc_prompts = [d.prompt for d in lesson.drills if isinstance(d, MultipleChoiceDrill)]
        assert any("equivalent" in p.lower() or "equivalente" in p.lower() or "äquivalent" in p.lower()
                   or any(eq_word in p.lower() for eq_word in ("equivalent", "construção", "costruzione"))
                   for p in mc_prompts), "Should have an equivalent-choice MC drill"

    def test_rich_contrast_recognition_drill(self):
        lesson = _build("conjugation", "hablar:present:indicative:1:Sing", "hablo", _RICH_CONJ)
        rec_drills = [d for d in lesson.drills if isinstance(d, RecognitionDrill)]
        # Is-reflexive recognition (False) + contrast recognition (False)
        assert any(d.correct is False for d in rec_drills)

    def test_rich_morphology_axes_populated(self):
        lesson = _build("conjugation", "hablar:present:indicative:1:Sing", "hablo", _RICH_CONJ)
        assert len(lesson.morphology_axes) == 4

    def test_rich_paradigms_populated(self):
        lesson = _build("conjugation", "hablar:present:indicative:1:Sing", "hablo", _RICH_CONJ)
        assert len(lesson.paradigms) == 1
        assert len(lesson.paradigms[0].cells) == 6

    def test_rich_equivalents_populated(self):
        lesson = _build("conjugation", "hablar:present:indicative:1:Sing", "hablo", _RICH_CONJ)
        assert len(lesson.equivalents) == 4

    def test_rich_contrasts_populated(self):
        lesson = _build("conjugation", "hablar:present:indicative:1:Sing", "hablo", _RICH_CONJ)
        assert len(lesson.contrasts) == 1
        assert lesson.contrasts[0].form_a == "hablo"


# ── 3. Case agreement — German / Russian ──────────────────────────────────────

class TestCaseAgreementMorphologyAxes:
    def test_german_genitive_axes(self):
        lesson = _build("case_agreement", "case_agreement:gen:des_mannes", "des Mannes", _DE_CASE)
        names = {ax.axis for ax in lesson.morphology_axes}
        assert "case" in names and "gender" in names

    def test_german_genitive_case_value(self):
        lesson = _build("case_agreement", "case_agreement:gen:des_mannes", "des Mannes", _DE_CASE)
        case_ax = next(ax for ax in lesson.morphology_axes if ax.axis == "case")
        assert case_ax.value == "genitive"

    def test_russian_genitive_axes(self):
        lesson = _build("case_agreement", "case_agreement:gen:bolshogo_goroda", "большого города", _RU_CASE)
        names = {ax.axis for ax in lesson.morphology_axes}
        assert "case" in names

    def test_contrast_populated_when_present(self):
        ld_with_contrast = {
            **_DE_CASE,
            "contrasts": [{"form_a": "des", "form_b": "dem", "note": "genitive vs dative"}],
        }
        lesson = _build("case_agreement", "cf", "des Mannes", ld_with_contrast)
        assert len(lesson.contrasts) == 1
        # Should have a contrast recognition drill
        contrast_drills = [d for d in lesson.drills if isinstance(d, RecognitionDrill) and d.correct is False]
        assert len(contrast_drills) >= 1


# ── 4. Inflection builder — Latin declension ──────────────────────────────────

class TestInflectionBuilder:
    def test_basic_fields(self):
        lesson = _build("inflection", "rex:acc:sing", "regem", _LA_INFLECT)
        assert lesson.type == "inflection"
        labels = {f.label for f in lesson.fields}
        assert "Lemma" in labels
        assert "Surface form" in labels
        assert "Case" in labels
        assert "Gender" in labels
        assert "Number" in labels
        assert "Declension" in labels
        assert "Translation" in labels

    def test_title_contains_surface(self):
        lesson = _build("inflection", "rex:acc:sing", "regem", _LA_INFLECT)
        assert "regem" in lesson.title

    def test_shadowing_first(self):
        lesson = _build("inflection", "rex:acc:sing", "regem", _LA_INFLECT)
        assert isinstance(lesson.drills[0], ShadowingDrill)
        assert lesson.drills[0].text == "regem"

    def test_lemma_recall_drill(self):
        lesson = _build("inflection", "rex:acc:sing", "regem", _LA_INFLECT)
        lemma_drills = [d for d in lesson.drills
                        if isinstance(d, FillBlankDrill) and d.answer == "rex"]
        assert len(lemma_drills) >= 1

    def test_case_mc_drill_present(self):
        lesson = _build("inflection", "rex:acc:sing", "regem", _LA_INFLECT)
        mc_drills = [d for d in lesson.drills if isinstance(d, MultipleChoiceDrill)]
        assert len(mc_drills) >= 1  # case MC

    def test_form_recall_drill(self):
        lesson = _build("inflection", "rex:acc:sing", "regem", _LA_INFLECT)
        recall = [d for d in lesson.drills
                  if isinstance(d, FillBlankDrill) and d.answer == "regem"]
        assert len(recall) >= 1

    def test_morphology_axes_populated(self):
        lesson = _build("inflection", "rex:acc:sing", "regem", _LA_INFLECT)
        names = {ax.axis for ax in lesson.morphology_axes}
        assert "case" in names and "gender" in names and "number" in names

    def test_ablative_case(self):
        ld = {**_LA_INFLECT, "case": "Abl", "surface": "rege"}
        lesson = _build("inflection", "rex:abl:sing", "rege", ld)
        case_field = next(f for f in lesson.fields if f.label == "Case")
        assert "ablative" in case_field.value.lower()

    def test_latin_dictionary_mode_unchanged(self):
        """Existing Latin dictionary-mode output is unaffected."""
        lesson = build_lesson(
            object_id="la-1",
            obj_type="vocabulary",
            canonical_form="amor",
            display_label="amor",
            lesson_data={"lemma": "amor", "pos": "NOUN", "gloss": "love"},
            lesson_mode="dictionary",
        )
        assert lesson.lesson_mode == "dictionary"
        assert lesson.morphology_axes == []

    def test_latin_conjugation_flat(self):
        """Latin conjugation data (flat keys) still generates correct drills."""
        lesson = _build("conjugation", "amare:present:indicative:1:Sing", "amo", _LA_CONJ_FLAT)
        assert lesson.type == "conjugation"
        assert any(isinstance(d, FillBlankDrill) and d.answer == "amare" for d in lesson.drills)

    def test_inflection_with_paradigm(self):
        ld = {
            **_LA_INFLECT,
            "morphology": {
                "axes": [{"axis": "case", "value": "accusative"}, {"axis": "number", "value": "singular"}],
                "paradigms": [{
                    "title": "rex — 3rd declension",
                    "cells": [
                        {"form": "rex",   "axes": {"case": "Nom", "number": "Sing"}, "is_highlighted": False},
                        {"form": "regis", "axes": {"case": "Gen", "number": "Sing"}},
                        {"form": "regi",  "axes": {"case": "Dat", "number": "Sing"}},
                        {"form": "regem", "axes": {"case": "Acc", "number": "Sing"}, "is_highlighted": True},
                        {"form": "rege",  "axes": {"case": "Abl", "number": "Sing"}},
                    ],
                }],
            },
        }
        lesson = _build("inflection", "rex:acc:sing", "regem", ld)
        assert len(lesson.paradigms) == 1
        fill_blanks = [d for d in lesson.drills if isinstance(d, FillBlankDrill)]
        # lemma recall + form recall + up to 2 paradigm cell drills
        assert len(fill_blanks) >= 3


# ── 5. Morphology-light: Arabic / Hebrew / CJK ────────────────────────────────

class TestMorphologyLightFallback:
    def test_arabic_dictionary_mode_can_stay_dictionary_only(self):
        lesson = build_lesson(
            object_id="ar-1", obj_type="vocabulary",
            canonical_form="كتب", display_label="كتب",
            lesson_data=_AR_DICT, lesson_mode="dictionary",
        )
        assert lesson.lesson_mode == "dictionary"
        assert lesson.morphology_axes == []
        assert lesson.paradigms == []
        assert lesson.equivalents == []
        assert lesson.contrasts == []

    def test_arabic_only_shadowing_and_gloss(self):
        lesson = build_lesson(
            object_id="ar-2", obj_type="vocabulary",
            canonical_form="كتب", display_label="كتب",
            lesson_data=_AR_DICT, lesson_mode="dictionary",
        )
        drill_types = {type(d).__name__ for d in lesson.drills}
        assert "ShadowingDrill" in drill_types
        assert "MultipleChoiceDrill" not in drill_types

    def test_hebrew_dictionary_mode_can_stay_dictionary_only(self):
        lesson = build_lesson(
            object_id="he-1", obj_type="vocabulary",
            canonical_form="בית", display_label="בית",
            lesson_data=_HE_DICT, lesson_mode="dictionary",
        )
        assert lesson.lesson_mode == "dictionary"
        assert lesson.morphology_axes == []

    def test_chinese_dictionary_mode(self):
        lesson = build_lesson(
            object_id="zh-1", obj_type="vocabulary",
            canonical_form="爱", display_label="爱",
            lesson_data=_ZH_DICT, lesson_mode="dictionary",
        )
        assert lesson.lesson_mode == "dictionary"
        assert lesson.morphology_axes == []

    def test_japanese_dictionary_mode(self):
        lesson = build_lesson(
            object_id="ja-1", obj_type="vocabulary",
            canonical_form="猫", display_label="猫",
            lesson_data=_JA_DICT, lesson_mode="dictionary",
        )
        assert lesson.lesson_mode == "dictionary"
        assert lesson.morphology_axes == []


# ── 6. Backwards compatibility ─────────────────────────────────────────────────

class TestBackwardsCompatibility:
    def test_conjugation_existing_drills_unchanged(self):
        """Core drills (shadowing, lemma fill-blank, tense MC) still present."""
        lesson = _build("conjugation", "hablar:present:indicative:1:Sing", "hablo", _ES_CONJ)
        assert isinstance(lesson.drills[0], ShadowingDrill)
        lemma_drills = [d for d in lesson.drills
                        if isinstance(d, FillBlankDrill) and d.answer == "hablar"]
        assert len(lemma_drills) >= 1
        mc_drills = [d for d in lesson.drills if isinstance(d, MultipleChoiceDrill)]
        assert len(mc_drills) >= 1  # tense MC

    def test_agreement_existing_drills_unchanged(self):
        agree_data = {
            "modifier": "gran", "modifier_pos": "ADJ", "noun": "casa",
            "gender": "Fem", "number": "Sing",
            "gender_match": True, "number_match": True,
        }
        lesson = _build("agreement", "adj:gran_casa", "gran", agree_data)
        assert isinstance(lesson.drills[0], ShadowingDrill)
        mc_drills = [d for d in lesson.drills if isinstance(d, MultipleChoiceDrill)]
        assert len(mc_drills) >= 1

    def test_vocabulary_unaffected(self):
        lesson = _build("vocabulary", "casa", "casa", {"lemma": "casa", "pos": "NOUN"})
        assert lesson.morphology_axes == []
        assert lesson.lesson_mode == "morphology"

    def test_no_extra_drills_without_morphology_data(self):
        """No paradigm/equivalent/contrast drills when lesson_data has no such keys."""
        lesson = _build("conjugation", "hablar:present:indicative:1:Sing", "hablo", _ES_CONJ)
        assert lesson.paradigms == []
        assert lesson.equivalents == []
        # The only RecognitionDrill should be the reflexive drill (correct=False for non-reflexive)
        rec_drills = [d for d in lesson.drills if isinstance(d, RecognitionDrill)]
        assert len(rec_drills) == 1  # only the is_reflexive drill

    def test_determinism_stable(self):
        """Same input → same lesson content across calls."""
        l1 = _build("conjugation", "hablar:present:indicative:1:Sing", "hablo", _RICH_CONJ)
        l2 = _build("conjugation", "hablar:present:indicative:1:Sing", "hablo", _RICH_CONJ)
        assert [d.type for d in l1.drills] == [d.type for d in l2.drills]
        mc1 = [d for d in l1.drills if isinstance(d, MultipleChoiceDrill)]
        mc2 = [d for d in l2.drills if isinstance(d, MultipleChoiceDrill)]
        for a, b in zip(mc1, mc2):
            assert a.options == b.options
            assert a.answer_index == b.answer_index
