"""Tests for the language-aware practice engine.

Verifies:
- Transformation drills use real paradigm/contrast/equivalent forms as expected_answer
- No placeholder drills (expected_answer == instruction text, same as prompt, or grammar label)
- Morphological hint added to cloze when axes are present
- Sentence recombination extracts word tokens
- Distractors are morphologically plausible when paradigm data is available
- Language-specific hooks normalize correctly
- Transformations return [] when no real data is available
"""
from __future__ import annotations

import pytest

from backend.lesson.context import LessonContext
from backend.lesson.cloze import build_cloze_prompt
from backend.lesson.distractors import (
    build_best_distractors,
    build_contrast_distractors,
    build_paradigm_distractors,
)
from backend.lesson.generators import build_lesson
from backend.lesson.practice_hooks import hooks_for_language
from backend.lesson.transformations import TransformationSpec, build_transformation_specs
from backend.schemas.lesson import (
    ContrastNote,
    EquivalentConstruction,
    MorphologyAxis,
    MorphologyParadigm,
    ParadigmCell,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _paradigm_with_cells(*forms: tuple[str, dict, bool]) -> MorphologyParadigm:
    cells = [
        ParadigmCell(form=f, axes=axes, is_highlighted=hi)
        for f, axes, hi in forms
    ]
    return MorphologyParadigm(cells=cells)


def _lesson_with_paradigm(lang: str = "es") -> object:
    return build_lesson(
        object_id="obj-conj",
        obj_type="conjugation",
        canonical_form="hablar",
        display_label="hablo",
        lesson_data={
            "lemma": "hablar",
            "surface": "hablo",
            "tense": "present",
            "mood": "indicative",
            "person": "1",
            "number": "Sing",
            "morphology": {
                "paradigms": [{
                    "title": "Present Indicative",
                    "cells": [
                        {"form": "hablo",   "axes": {"person": "1", "number": "singular"}, "is_highlighted": True},
                        {"form": "hablas",  "axes": {"person": "2", "number": "singular"}, "is_highlighted": False},
                        {"form": "habla",   "axes": {"person": "3", "number": "singular"}, "is_highlighted": False},
                        {"form": "hablamos","axes": {"person": "1", "number": "plural"},   "is_highlighted": False},
                    ]
                }]
            }
        },
        context=LessonContext(language_code=lang, language_name="Spanish", direction="ltr"),
    )


# ── Transformations module ────────────────────────────────────────────────────

class TestBuildTransformationSpecs:
    def test_returns_empty_with_no_data(self):
        specs = build_transformation_specs([], [], [])
        assert specs == []

    def test_paradigm_cells_become_specs(self):
        paradigm = _paradigm_with_cells(
            ("hablo",  {"person": "1", "number": "singular"}, True),
            ("hablas", {"person": "2", "number": "singular"}, False),
        )
        specs = build_transformation_specs([paradigm], [], [], lemma="hablar")
        assert len(specs) == 1
        assert specs[0].expected == "hablas"
        assert specs[0].source == "paradigm"
        assert "hablar" in specs[0].prompt

    def test_paradigm_expected_is_real_form_not_instruction(self):
        paradigm = _paradigm_with_cells(
            ("hablo",  {"person": "1"}, True),
            ("hablas", {"person": "2"}, False),
            ("habla",  {"person": "3"}, False),
        )
        specs = build_transformation_specs([paradigm], [], [], limit=3)
        for spec in specs:
            # Must be a real word form, not an instruction string
            assert not spec.expected.startswith("Transform")
            assert not spec.expected.startswith("Use ")
            assert spec.expected in {"hablas", "habla"}

    def test_contrast_example_b_used_as_expected(self):
        contrast = ContrastNote(
            form_a="ser", form_b="estar",
            note="ser = permanent; estar = temporary",
            example_a="Soy médico.",
            example_b="Estoy cansado.",
        )
        specs = build_transformation_specs([], [contrast], [])
        assert len(specs) == 1
        assert specs[0].expected == "Estoy cansado."
        assert specs[0].source == "contrast"
        assert "estar" in specs[0].prompt

    def test_contrast_without_example_b_skipped(self):
        contrast = ContrastNote(
            form_a="ser", form_b="estar",
            note="ser = permanent; estar = temporary",
        )
        specs = build_transformation_specs([], [contrast], [])
        assert specs == []

    def test_equivalent_construction_used(self):
        eq = EquivalentConstruction(construction="estoy hablando", note="progressive")
        specs = build_transformation_specs([], [], [eq])
        assert len(specs) == 1
        assert specs[0].expected == "estoy hablando"
        assert specs[0].source == "equivalent"

    def test_limit_respected(self):
        paradigm = _paradigm_with_cells(
            ("hablo",   {"person": "1"}, True),
            ("hablas",  {"person": "2"}, False),
            ("habla",   {"person": "3"}, False),
            ("hablamos",{"person": "4"}, False),
        )
        specs = build_transformation_specs([paradigm], [], [], limit=2)
        assert len(specs) == 2

    def test_priority_paradigm_before_contrast(self):
        paradigm = _paradigm_with_cells(
            ("hablo",  {"person": "1"}, True),
            ("hablas", {"person": "2"}, False),
        )
        contrast = ContrastNote(form_a="ser", form_b="estar", note="x", example_b="Estoy.")
        specs = build_transformation_specs([paradigm], [contrast], [], limit=2)
        sources = [s.source for s in specs]
        assert sources[0] == "paradigm"

    def test_cells_without_axes_skipped(self):
        paradigm = _paradigm_with_cells(
            ("hablo",  {}, True),
            ("hablas", {}, False),  # no axes → no description → skip
        )
        specs = build_transformation_specs([paradigm], [], [])
        assert specs == []


# ── Integration: transformation_drills in lesson ──────────────────────────────

class TestTransformationDrillsIntegration:
    def test_paradigm_lesson_emits_transformation_drills(self):
        lesson = _lesson_with_paradigm("es")
        drills = [a for a in lesson.practice_activities if a.type == "transformation_drills"]
        assert len(drills) >= 1

    def test_transformation_expected_is_real_form(self):
        lesson = _lesson_with_paradigm("es")
        drills = [a for a in lesson.practice_activities if a.type == "transformation_drills"]
        real_forms = {"hablas", "habla", "hablamos"}
        for d in drills:
            assert d.expected_answer in real_forms, (
                f"expected_answer={d.expected_answer!r} is not a real paradigm form"
            )

    def test_no_transformation_drills_without_morphology_data(self):
        lesson = build_lesson(
            object_id="obj-voc",
            obj_type="vocabulary",
            canonical_form="parler",
            display_label="parler",
            lesson_data={"lemma": "parler", "pos": "VERB", "translation": "to speak"},
            context=LessonContext(language_code="fr", language_name="French", direction="ltr"),
        )
        assert all(a.type != "transformation_drills" for a in lesson.practice_activities)

    def test_expected_answer_never_equals_prompt(self):
        lesson = _lesson_with_paradigm("es")
        for a in lesson.practice_activities:
            if a.type == "transformation_drills":
                assert a.expected_answer != a.prompt

    def test_expected_answer_never_is_grammar_label(self):
        """Regression: old code set expected_answer = notes[0] (a grammar label string)."""
        lesson = build_lesson(
            object_id="obj-voc",
            obj_type="vocabulary",
            canonical_form="hablar",
            display_label="hablar",
            lesson_data={
                "lemma": "hablar",
                "pos": "VERB",
                "grammar_notes": ["Use present tense in neutral register."],
            },
            context=LessonContext(language_code="es", language_name="Spanish", direction="ltr"),
        )
        for a in lesson.practice_activities:
            if a.type == "transformation_drills":
                assert "Use present tense" not in a.expected_answer


# ── Cloze module ──────────────────────────────────────────────────────────────

class TestBuildClozePrompt:
    def test_blank_replaces_answer(self):
        prompt, _ = build_cloze_prompt("Yo hablo español.", "hablo")
        assert "____" in prompt
        assert "hablo" not in prompt

    def test_fallback_when_answer_not_in_sentence(self):
        prompt, _ = build_cloze_prompt("Some other sentence.", "hablo")
        assert "____" in prompt

    def test_no_hint_without_axes(self):
        _, hint = build_cloze_prompt("Yo hablo.", "hablo", [])
        assert hint is None

    def test_hint_from_axes(self):
        axes = [
            MorphologyAxis(axis="person", value="1", label="first person"),
            MorphologyAxis(axis="number", value="singular", label="singular"),
            MorphologyAxis(axis="tense",  value="present",  label="present"),
        ]
        _, hint = build_cloze_prompt("Yo hablo.", "hablo", axes)
        assert hint is not None
        assert "first person" in hint
        assert "singular" in hint
        assert "present" in hint

    def test_hint_in_cloze_prompt_when_axes_present(self):
        lesson = _lesson_with_paradigm("es")
        cloze_acts = [a for a in lesson.practice_activities if a.type == "cloze_completion"]
        assert len(cloze_acts) >= 1
        cloze = cloze_acts[0]
        assert "____" in cloze.prompt
        # Axes are present in conjugation lesson — hint should appear
        if lesson.morphology_axes:
            assert "[" in cloze.prompt


# ── Distractors module ────────────────────────────────────────────────────────

class TestDistractors:
    def test_paradigm_distractors_from_non_highlighted_cells(self):
        paradigm = _paradigm_with_cells(
            ("hablo",   {"person": "1"}, True),
            ("hablas",  {"person": "2"}, False),
            ("habla",   {"person": "3"}, False),
        )
        distractors = build_paradigm_distractors([paradigm], "hablo")
        assert "hablas" in distractors
        assert "habla" in distractors
        assert "hablo" not in distractors

    def test_contrast_distractors_from_form_b(self):
        contrast = ContrastNote(form_a="ser", form_b="estar", note="x")
        distractors = build_contrast_distractors([contrast], "ser")
        assert "estar" in distractors
        assert "ser" not in distractors

    def test_build_best_distractors_uses_paradigm_first(self):
        paradigm = _paradigm_with_cells(
            ("hablo",  {}, True),
            ("hablas", {}, False),
        )
        result = build_best_distractors("hablo", "explanation", "text", paradigms=[paradigm])
        assert "hablas" in result
        assert "Not: hablo" not in result

    def test_build_best_distractors_fallback_when_no_data(self):
        result = build_best_distractors("correct", "explanation", "text")
        assert any("Not:" in d for d in result)

    def test_correct_form_never_in_distractors(self):
        paradigm = _paradigm_with_cells(
            ("hablo",  {}, True),
            ("habla",  {}, False),
        )
        result = build_best_distractors("hablo", "x", "y", paradigms=[paradigm])
        assert "hablo" not in result

    def test_limit_respected(self):
        paradigm = _paradigm_with_cells(
            ("hablo",   {}, True),
            ("hablas",  {}, False),
            ("habla",   {}, False),
            ("hablamos",{}, False),
            ("habláis", {}, False),
        )
        result = build_best_distractors("hablo", "x", "y", paradigms=[paradigm], limit=2)
        assert len(result) <= 2


# ── Practice hooks ────────────────────────────────────────────────────────────

class TestPracticeHooks:
    def test_german_umlaut_ascii_variant(self):
        hooks = hooks_for_language("de")
        variants = hooks.answer_variants("hätte", None)
        assert "haette" in variants

    def test_german_ss_variant(self):
        hooks = hooks_for_language("de")
        variants = hooks.answer_variants("straße", None)
        assert "strasse" in variants

    def test_russian_stress_mark_stripped(self):
        hooks = hooks_for_language("ru")
        # Stress mark is combining acute U+0301
        normalized = hooks.normalize_term("говори́т")
        assert "́" not in normalized
        assert "говорит" in normalized

    def test_russian_yo_ye_variant(self):
        hooks = hooks_for_language("ru")
        variants = hooks.answer_variants("ёж", None)
        assert "еж" in variants

    def test_japanese_particle_stripped_variant(self):
        hooks = hooks_for_language("ja")
        variants = hooks.answer_variants("猫は", None)
        assert "猫" in variants

    def test_arabic_diacritic_stripped(self):
        hooks = hooks_for_language("ar")
        # كَتَبَ with tashkeel should normalize to كتب
        normalized = hooks.normalize_term("كَتَبَ")
        assert normalized == "كتب"

    def test_arabic_alef_variant(self):
        hooks = hooks_for_language("ar")
        variants = hooks.answer_variants("أحمد", None)
        assert "احمد" in variants

    def test_italian_reflexive_clitic_stripped(self):
        hooks = hooks_for_language("it")
        variants = hooks.answer_variants("si parla", None)
        assert "parla" in variants

    def test_portuguese_romance_reflexive(self):
        hooks = hooks_for_language("pt")
        variants = hooks.answer_variants("se falar", None)
        assert "falar" in variants

    def test_known_languages_all_return_hooks(self):
        for lang in ("en", "es", "fr", "it", "pt", "de", "ru", "ja", "ar", "ko", "zh"):
            hooks = hooks_for_language(lang)
            assert hooks.normalize_term("test") is not None

    def test_unknown_language_returns_safe_default(self):
        hooks = hooks_for_language("xx")
        assert hooks.normalize_term("test") == "test"
        assert "Not:" in hooks.distractors("correct", "explanation", "text")[-1]


# ── Sentence recombination ────────────────────────────────────────────────────

class TestSentenceRecombination:
    def test_recombination_prompt_contains_words(self):
        lesson = build_lesson(
            object_id="obj-rec",
            obj_type="vocabulary",
            canonical_form="speak",
            display_label="speak",
            lesson_data={
                "lemma": "speak",
                "pos": "VERB",
                "translation": "to talk",
                "examples": ["I speak three languages"],
            },
            context=LessonContext(language_code="en", language_name="English", direction="ltr"),
        )
        rec = next(a for a in lesson.practice_activities if a.type == "sentence_recombination")
        # Prompt lists the shuffled tokens; expected is the full text_basis
        assert "|" in rec.prompt  # tokens joined with " | "
        assert "speak" in rec.prompt
        # expected_answer is text_basis = " ".join(lesson.examples)
        assert "speak" in rec.expected_answer
        assert "languages" in rec.expected_answer

    def test_recombination_tokens_in_alternatives(self):
        lesson = build_lesson(
            object_id="obj-rec2",
            obj_type="vocabulary",
            canonical_form="run",
            display_label="run",
            lesson_data={
                "lemma": "run",
                "pos": "VERB",
                "translation": "to run",
                "examples": ["She runs every day"],
            },
            context=LessonContext(language_code="en", language_name="English", direction="ltr"),
        )
        rec = next(a for a in lesson.practice_activities if a.type == "sentence_recombination")
        # Tokens should be present as alternatives for frontend rendering
        all_words = set(rec.expected_answer.split())
        alternatives_words = set(rec.acceptable_alternatives)
        assert alternatives_words == all_words or alternatives_words.issubset(all_words)


# ── Full count invariant ──────────────────────────────────────────────────────

class TestActivityCount:
    def test_minimum_nine_activities_without_paradigm_data(self):
        lesson = build_lesson(
            object_id="obj-count",
            obj_type="vocabulary",
            canonical_form="run",
            display_label="run",
            lesson_data={"lemma": "run", "pos": "VERB", "translation": "to run"},
            context=LessonContext(language_code="en", language_name="English", direction="ltr"),
        )
        assert len(lesson.practice_activities) >= 9

    def test_minimum_activities_with_paradigm_data(self):
        lesson = _lesson_with_paradigm("es")
        # Paradigm adds transformation drills and grammar discrimination on top of baseline
        assert len(lesson.practice_activities) >= 10

    def test_all_expected_answers_non_empty(self):
        lesson = _lesson_with_paradigm("es")
        for a in lesson.practice_activities:
            assert a.expected_answer, f"Empty expected_answer for {a.type}"
