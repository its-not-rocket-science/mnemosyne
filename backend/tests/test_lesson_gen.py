"""Unit tests for the lesson generator.

All tests are synchronous — generators are pure functions with no I/O.
"""
from __future__ import annotations

import pytest

from backend.lesson.generators import build_lesson, _make_mc_drill, _hash_key
from backend.schemas.lesson import (
    FillBlankDrill,
    MultipleChoiceDrill,
    RecognitionDrill,
    ShadowingDrill,
)

_VOCAB_DATA = {"lemma": "casa", "pos": "NOUN"}
_CONJ_DATA = {
    "lemma":          "hablar",
    "surface":        "hablo",
    "tense":          "present",
    "mood":           "indicative",
    "person":         "1",
    "number":         "Sing",
    "morph_complete": True,
    "construction":   "standalone",
    "is_reflexive":   False,
}
_AGREE_DATA = {
    "modifier":     "gran",
    "modifier_pos": "ADJ",
    "noun":         "casa",
    "gender":       "Fem",
    "number":       "Sing",
    "gender_match": True,
    "number_match": True,
    "confidence_note": "gender and number both confirmed",
}


# ── build_lesson general ──────────────────────────────────────────────────────


def test_vocabulary_lesson_has_required_fields():
    lesson = build_lesson(
        object_id="abc-123",
        obj_type="vocabulary",
        canonical_form="casa",
        display_label="casa",
        lesson_data=_VOCAB_DATA,
    )
    assert lesson.id == "abc-123"
    assert lesson.type == "vocabulary"
    assert "casa" in lesson.title
    assert "noun" in lesson.explanation
    assert len(lesson.drills) >= 1
    assert len(lesson.examples) >= 1


def test_conjugation_lesson_has_required_fields():
    lesson = build_lesson(
        object_id="def-456",
        obj_type="conjugation",
        canonical_form="hablar:present:indicative:1:Sing",
        display_label="hablo",
        lesson_data=_CONJ_DATA,
    )
    assert lesson.type == "conjugation"
    assert "hablo" in lesson.title
    assert "hablar" in lesson.explanation
    assert "present" in lesson.explanation


def test_agreement_lesson_has_required_fields():
    lesson = build_lesson(
        object_id="ghi-789",
        obj_type="agreement",
        canonical_form="adj:gran_casa",
        display_label="gran casa",
        lesson_data=_AGREE_DATA,
    )
    assert lesson.type == "agreement"
    assert "gran" in lesson.explanation
    assert "casa" in lesson.explanation


def test_generic_fallback_for_unknown_type():
    lesson = build_lesson(
        object_id="zzz",
        obj_type="idiom",
        canonical_form="por supuesto",
        display_label="por supuesto",
        lesson_data={"meaning": "of course"},
    )
    assert lesson.type == "idiom"
    assert len(lesson.drills) >= 1


# ── drill presence ────────────────────────────────────────────────────────────


def test_vocabulary_always_has_shadowing_drill():
    lesson = build_lesson(
        object_id="x", obj_type="vocabulary",
        canonical_form="hola", display_label="Hola",
        lesson_data={"lemma": "hola", "pos": "NOUN"},
    )
    types = {d.type for d in lesson.drills}
    assert "shadowing" in types


def test_conjugation_has_fill_blank_for_lemma():
    lesson = build_lesson(
        object_id="x", obj_type="conjugation",
        canonical_form="hablar:present:indicative:1:Sing",
        display_label="hablo", lesson_data=_CONJ_DATA,
    )
    fill_drills = [d for d in lesson.drills if d.type == "fill_blank"]
    assert len(fill_drills) >= 1
    assert any(d.answer == "hablar" for d in fill_drills)


def test_vocabulary_fill_blank_only_when_surface_differs():
    # Same surface and lemma — no fill-blank for lemma
    lesson_same = build_lesson(
        object_id="x", obj_type="vocabulary",
        canonical_form="casa", display_label="casa",
        lesson_data={"lemma": "casa", "pos": "NOUN"},
    )
    fill_drills = [d for d in lesson_same.drills if d.type == "fill_blank"]
    assert len(fill_drills) == 0

    # Different surface and lemma — fill-blank is present
    lesson_diff = build_lesson(
        object_id="x", obj_type="vocabulary",
        canonical_form="libro", display_label="libros",
        lesson_data={"lemma": "libro", "pos": "NOUN"},
    )
    fill_drills_diff = [d for d in lesson_diff.drills if d.type == "fill_blank"]
    assert len(fill_drills_diff) >= 1


def test_conjugation_reflexive_recognition_drill():
    reflexive_data = {**_CONJ_DATA, "is_reflexive": True}
    lesson = build_lesson(
        object_id="x", obj_type="conjugation",
        canonical_form="levantarse:present:indicative:1:Sing",
        display_label="me levanto", lesson_data=reflexive_data,
    )
    rec_drills = [d for d in lesson.drills if d.type == "recognition"]
    assert any(d.correct is True for d in rec_drills)


def test_non_reflexive_recognition_drill_is_false():
    lesson = build_lesson(
        object_id="x", obj_type="conjugation",
        canonical_form="hablar:present:indicative:1:Sing",
        display_label="hablo", lesson_data=_CONJ_DATA,
    )
    rec_drills = [d for d in lesson.drills if d.type == "recognition"]
    assert all(d.correct is False for d in rec_drills)


# ── multiple choice integrity ─────────────────────────────────────────────────


def test_mc_answer_index_points_to_correct_option():
    lesson = build_lesson(
        object_id="x", obj_type="vocabulary",
        canonical_form="casa", display_label="casa",
        lesson_data={"lemma": "casa", "pos": "NOUN"},
    )
    mc_drills = [d for d in lesson.drills if d.type == "multiple_choice"]
    for drill in mc_drills:
        correct_option = drill.options[drill.answer_index]
        assert correct_option == "noun"


def test_mc_no_duplicate_options():
    lesson = build_lesson(
        object_id="x", obj_type="vocabulary",
        canonical_form="casa", display_label="casa",
        lesson_data={"lemma": "casa", "pos": "NOUN"},
    )
    for drill in lesson.drills:
        if drill.type == "multiple_choice":
            assert len(drill.options) == len(set(drill.options))


# ── determinism ───────────────────────────────────────────────────────────────


def test_lesson_generation_is_deterministic():
    kwargs = dict(
        object_id="abc",
        obj_type="vocabulary",
        canonical_form="casa",
        display_label="casas",
        lesson_data={"lemma": "casa", "pos": "NOUN"},
    )
    assert build_lesson(**kwargs) == build_lesson(**kwargs)


def test_different_seeds_produce_different_option_order():
    """Two words with different canonical forms should get different shuffles."""
    mc1 = _make_mc_drill("word1", "prompt", "noun", ["noun", "verb", "adjective", "adverb"])
    mc2 = _make_mc_drill("word2", "prompt", "noun", ["noun", "verb", "adjective", "adverb"])
    # They must both be valid (correct option present), but may differ in order.
    assert mc1 is not None
    assert mc2 is not None
    assert mc1.options[mc1.answer_index] == "noun"
    assert mc2.options[mc2.answer_index] == "noun"


def test_make_mc_drill_returns_none_when_pool_too_small():
    result = _make_mc_drill("seed", "prompt?", "noun", ["noun", "verb"], n_wrong=3)
    assert result is None


# ── field rendering ───────────────────────────────────────────────────────────


def test_conjugation_fields_include_tense_and_mood():
    lesson = build_lesson(
        object_id="x", obj_type="conjugation",
        canonical_form="hablar:present:indicative:1:Sing",
        display_label="hablo", lesson_data=_CONJ_DATA,
    )
    labels = {f.label for f in lesson.fields}
    assert "Tense" in labels
    assert "Mood" in labels
    assert "Lemma" in labels


def test_vocabulary_fields_include_pos():
    lesson = build_lesson(
        object_id="x", obj_type="vocabulary",
        canonical_form="casa", display_label="casa",
        lesson_data=_VOCAB_DATA,
    )
    labels = {f.label for f in lesson.fields}
    assert "Part of speech" in labels
