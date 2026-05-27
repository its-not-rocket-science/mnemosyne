"""Tests for the grammar concept catalogue (backend/lesson/concepts.py).

Also covers:
  - Concept IDs wired onto LessonField in Spanish conjugation lessons.
  - Concept IDs wired onto MorphologyAxis from lesson data.
  - Chinese Romanized field receiving axis.romanized concept ID.
  - Spanish noun vocabulary lessons exposing gender/number fields with concept IDs.
"""
from __future__ import annotations

import pytest

from backend.lesson.concepts import all_concept_ids, resolve_concept
from backend.lesson.generators import build_lesson
from backend.schemas.lesson import GrammarConceptExplanation


# ── resolve_concept basics ────────────────────────────────────────────────────

class TestResolveConceptBasics:
    def test_unknown_concept_returns_none(self):
        assert resolve_concept("not.a.concept") is None

    def test_axis_tense_returns_explanation(self):
        c = resolve_concept("axis.tense")
        assert c is not None
        assert isinstance(c, GrammarConceptExplanation)
        assert c.concept_id == "axis.tense"

    def test_tense_imperfect_returns_explanation(self):
        c = resolve_concept("tense.imperfect")
        assert c is not None
        assert c.title == "Imperfect"
        assert c.axis == "tense"
        assert c.value == "imperfect"

    def test_mood_subjunctive_returns_explanation(self):
        c = resolve_concept("mood.subjunctive")
        assert c is not None
        assert "subjunctive" in c.title.lower()

    def test_pos_noun_returns_explanation(self):
        c = resolve_concept("pos.noun")
        assert c is not None
        assert "noun" in c.title.lower()

    def test_axis_romanized_returns_explanation(self):
        c = resolve_concept("axis.romanized")
        assert c is not None
        assert c.concept_id == "axis.romanized"

    def test_has_short_definition(self):
        c = resolve_concept("axis.tense")
        assert c is not None
        assert len(c.short_definition) > 0

    def test_has_learner_explanation(self):
        c = resolve_concept("tense.imperfect")
        assert c is not None
        assert len(c.learner_explanation) > 0

    def test_related_concepts_are_list(self):
        c = resolve_concept("axis.tense")
        assert c is not None
        assert isinstance(c.related_concepts, list)

    def test_examples_are_list(self):
        c = resolve_concept("tense.present")
        assert c is not None
        assert isinstance(c.examples, list)

    def test_practice_tags_are_list(self):
        c = resolve_concept("tense.imperfect")
        assert c is not None
        assert isinstance(c.practice_tags, list)

    def test_all_concept_ids_nonempty(self):
        ids = all_concept_ids()
        assert len(ids) >= 20

    def test_all_concept_ids_resolve(self):
        for cid in all_concept_ids():
            assert resolve_concept(cid) is not None, f"concept {cid!r} failed to resolve"


# ── Language-specific notes ───────────────────────────────────────────────────

class TestLanguageSpecificNotes:
    def test_imperfect_es_has_target_note(self):
        c = resolve_concept("tense.imperfect", language_code="es")
        assert c is not None
        assert c.target_language_note is not None
        assert "imperfecto" in c.target_language_note.lower()

    def test_subjunctive_es_has_target_note(self):
        c = resolve_concept("mood.subjunctive", language_code="es")
        assert c is not None
        assert c.target_language_note is not None
        assert "weirdo" in c.target_language_note.lower() or "subjunct" in c.target_language_note.lower()

    def test_gender_es_has_target_note(self):
        c = resolve_concept("axis.gender", language_code="es")
        assert c is not None
        assert c.target_language_note is not None

    def test_no_target_note_for_unregistered_language(self):
        c = resolve_concept("tense.imperfect", language_code="xx")
        assert c is not None
        assert c.target_language_note is None

    def test_imperfect_en_l1_has_comparison(self):
        c = resolve_concept("tense.imperfect", l1_language="en")
        assert c is not None
        assert c.l1_comparison is not None
        assert "english" in c.l1_comparison.lower() or "used to" in c.l1_comparison.lower()

    def test_subjunctive_en_l1_has_comparison(self):
        c = resolve_concept("mood.subjunctive", l1_language="en")
        assert c is not None
        assert c.l1_comparison is not None

    def test_gender_en_l1_has_comparison(self):
        c = resolve_concept("axis.gender", l1_language="en")
        assert c is not None
        assert c.l1_comparison is not None

    def test_romanized_zh_has_target_note(self):
        c = resolve_concept("axis.romanized", language_code="zh")
        assert c is not None
        assert c.target_language_note is not None
        assert "pinyin" in c.target_language_note.lower()

    def test_language_note_does_not_mutate_base(self):
        c1 = resolve_concept("tense.imperfect", language_code="es")
        c2 = resolve_concept("tense.imperfect")
        assert c2 is not None
        assert c2.target_language_note is None
        assert c1 is not c2


# ── Chinese concepts ──────────────────────────────────────────────────────────

class TestChineseConcepts:
    def test_zh_word_segmentation(self):
        c = resolve_concept("zh.word_segmentation")
        assert c is not None

    def test_zh_pinyin(self):
        c = resolve_concept("zh.pinyin")
        assert c is not None

    def test_zh_aspect_particle_le(self):
        c = resolve_concept("zh.aspect_particle.le")
        assert c is not None
        assert "了" in c.title or "le" in c.title.lower()

    def test_zh_aspect_particle_guo(self):
        c = resolve_concept("zh.aspect_particle.guo")
        assert c is not None

    def test_zh_aspect_particle_zhe(self):
        c = resolve_concept("zh.aspect_particle.zhe")
        assert c is not None

    def test_zh_structural_particle_de(self):
        c = resolve_concept("zh.structural_particle.de")
        assert c is not None

    def test_zh_classifier(self):
        c = resolve_concept("zh.classifier")
        assert c is not None


# ── Conjugation lesson concept IDs ───────────────────────────────────────────

_ES_CONJ = {
    "lemma":   "hablar",
    "surface": "hablaba",
    "tense":   "imperfect",
    "mood":    "indicative",
    "person":  "3",
    "number":  "Sing",
}


class TestConjugationConceptIds:
    @pytest.fixture()
    def lesson(self):
        return build_lesson(
            object_id="es-conj-1",
            obj_type="conjugation",
            canonical_form="hablar:imperfect:indicative:3:Sing",
            display_label="hablaba",
            lesson_data=_ES_CONJ,
        )

    def test_tense_field_has_concept_id(self, lesson):
        tense_f = next(f for f in lesson.fields if f.label == "Tense")
        assert tense_f.concept_id == "axis.tense"

    def test_tense_field_has_value_concept_id(self, lesson):
        tense_f = next(f for f in lesson.fields if f.label == "Tense")
        assert tense_f.value_concept_id == "tense.imperfect"

    def test_mood_field_has_concept_id(self, lesson):
        mood_f = next(f for f in lesson.fields if f.label == "Mood")
        assert mood_f.concept_id == "axis.mood"
        assert mood_f.value_concept_id == "mood.indicative"

    def test_person_field_has_concept_id(self, lesson):
        person_f = next(f for f in lesson.fields if f.label == "Person")
        assert person_f.concept_id == "axis.person"
        assert person_f.value_concept_id == "person.third"

    def test_number_field_has_concept_id(self, lesson):
        number_f = next(f for f in lesson.fields if f.label == "Number")
        assert number_f.concept_id == "axis.number"
        assert number_f.value_concept_id == "number.singular"

    def test_lemma_field_has_concept_id(self, lesson):
        lemma_f = next(f for f in lesson.fields if f.label == "Lemma")
        assert lemma_f.concept_id == "axis.lemma"

    def test_surface_form_field_has_concept_id(self, lesson):
        surf_f = next(f for f in lesson.fields if f.label == "Surface form")
        assert surf_f.concept_id == "axis.surface_form"


# ── Morphology axis concept IDs ───────────────────────────────────────────────

class TestMorphologyAxisConceptIds:
    def test_axes_carry_concept_ids(self):
        lesson = build_lesson(
            object_id="ru-conj-1",
            obj_type="conjugation",
            canonical_form="говорить:present:indicative:1:Sing",
            display_label="говорю",
            lesson_data={
                "lemma": "говорить",
                "surface": "говорю",
                "tense": "present",
                "mood": "indicative",
                "person": "1",
                "number": "Sing",
                "aspect": "Imp",
            },
        )
        for ax in lesson.morphology_axes:
            assert ax.axis_concept_id is not None, f"axis {ax.axis!r} has no axis_concept_id"

    def test_tense_axis_has_present_value_cid(self):
        lesson = build_lesson(
            object_id="fr-conj-1",
            obj_type="conjugation",
            canonical_form="parler:present:indicative:1:Sing",
            display_label="parle",
            lesson_data={
                "lemma": "parler",
                "surface": "parle",
                "tense": "present",
                "mood": "indicative",
                "person": "1",
                "number": "Sing",
            },
        )
        tense_ax = next((ax for ax in lesson.morphology_axes if ax.axis == "tense"), None)
        if tense_ax:
            assert tense_ax.value_concept_id == "tense.present"


# ── Spanish noun gender/number in vocabulary ─────────────────────────────────

class TestSpanishNounGenderNumber:
    def test_noun_with_gender_shows_gender_field(self):
        lesson = build_lesson(
            object_id="es-noun-1",
            obj_type="vocabulary",
            canonical_form="casa",
            display_label="casa",
            lesson_data={"lemma": "casa", "pos": "NOUN", "gender": "Fem", "number": "Sing"},
        )
        labels = [f.label for f in lesson.fields]
        assert "Gender" in labels

    def test_noun_gender_field_value(self):
        lesson = build_lesson(
            object_id="es-noun-2",
            obj_type="vocabulary",
            canonical_form="libro",
            display_label="libro",
            lesson_data={"lemma": "libro", "pos": "NOUN", "gender": "Masc", "number": "Sing"},
        )
        gender_f = next(f for f in lesson.fields if f.label == "Gender")
        assert gender_f.value == "masculine"

    def test_noun_gender_field_concept_id(self):
        lesson = build_lesson(
            object_id="es-noun-3",
            obj_type="vocabulary",
            canonical_form="casa",
            display_label="casa",
            lesson_data={"lemma": "casa", "pos": "NOUN", "gender": "Fem"},
        )
        gender_f = next(f for f in lesson.fields if f.label == "Gender")
        assert gender_f.concept_id == "axis.gender"
        assert gender_f.value_concept_id == "gender.feminine"

    def test_noun_number_field_concept_id(self):
        lesson = build_lesson(
            object_id="es-noun-4",
            obj_type="vocabulary",
            canonical_form="casa",
            display_label="casa",
            lesson_data={"lemma": "casa", "pos": "NOUN", "gender": "Fem", "number": "Sing"},
        )
        number_f = next(f for f in lesson.fields if f.label == "Number")
        assert number_f.concept_id == "axis.number"
        assert number_f.value_concept_id == "number.singular"

    def test_non_noun_has_no_gender_field(self):
        lesson = build_lesson(
            object_id="es-verb-1",
            obj_type="vocabulary",
            canonical_form="correr",
            display_label="correr",
            lesson_data={"lemma": "correr", "pos": "VERB"},
        )
        labels = [f.label for f in lesson.fields]
        assert "Gender" not in labels

    def test_noun_without_gender_has_no_gender_field(self):
        lesson = build_lesson(
            object_id="es-noun-5",
            obj_type="vocabulary",
            canonical_form="casa",
            display_label="casa",
            lesson_data={"lemma": "casa", "pos": "NOUN"},
        )
        labels = [f.label for f in lesson.fields]
        assert "Gender" not in labels

    def test_noun_gender_unknown_has_no_gender_field(self):
        lesson = build_lesson(
            object_id="es-noun-6",
            obj_type="vocabulary",
            canonical_form="casa",
            display_label="casa",
            lesson_data={"lemma": "casa", "pos": "NOUN", "gender": "unknown"},
        )
        labels = [f.label for f in lesson.fields]
        assert "Gender" not in labels


# ── Chinese Romanized field ───────────────────────────────────────────────────

class TestChineseRomanizedConceptId:
    def test_romanized_field_has_axis_concept_id(self):
        lesson = build_lesson(
            object_id="zh-vocab-1",
            obj_type="vocabulary",
            canonical_form="学习",
            display_label="学习",
            lesson_data={"word": "学习", "pos": "WORD", "pinyin": "xué xí"},
            lesson_mode="vocabulary",
        )
        rom_f = next((f for f in lesson.fields if f.label == "Romanized"), None)
        assert rom_f is not None
        assert rom_f.concept_id == "axis.romanized"
        assert rom_f.value_concept_id == "zh.pinyin"
