"""Tests for the backwards-compatible morphology schema extensions.

Covers:
  1. Backwards compatibility — LessonResponse without morphology fields still validates.
  2. Round-trip — new morphology fields serialise and deserialise correctly.
  3. _validate_morphology — M1–M7 contract warnings for malformed optional data.
  4. VALID_MORPHOLOGY_AXES — known axis names pass; unknown names produce M4 warning.
  5. validate_result integration — morphology warnings attach to ContractReport.

Run:
    pytest backend/tests/test_morphology_schema.py -v
"""
from __future__ import annotations

import pytest

from backend.parsing.contract import (
    VALID_MORPHOLOGY_AXES,
    ContractReport,
    ContractWarning,
    _validate_morphology,
    validate_result,
)
from backend.schemas.lesson import (
    ContrastNote,
    EncounteredVocabularySummary,
    EquivalentConstruction,
    FillBlankDrill,
    LessonResponse,
    MorphologyAxis,
    MorphologyParadigm,
    ParadigmCell,
)
from backend.schemas.parse import CandidateObject, CandidateSentenceResult


# ── Helpers ───────────────────────────────────────────────────────────────────

def _minimal_lesson(**extra) -> dict:
    """Minimum dict that passes LessonResponse validation."""
    base = dict(
        id="test-id",
        type="conjugation",
        lesson_mode="morphology",
        title="Test",
        explanation="A test lesson.",
        fields=[],
        examples=[],
        drills=[],
    )
    base.update(extra)
    return base


class _FakeCapabilities:
    code = "xx"
    direction = "ltr"
    idiom_detection = False
    morphology_depth = "full"
    nuance_capabilities = None


class _FakePlugin:
    language_code = "xx"
    direction = "ltr"
    capabilities = _FakeCapabilities()


def _candidate(**extra) -> CandidateObject:
    defaults: dict = dict(
        canonical_form="λύω",
        type="conjugation",
        label="λύω",
        lesson_data={"tense": "present", "mood": "indicative"},
    )
    defaults.update(extra)
    return CandidateObject(**defaults)


def _result(*candidates) -> CandidateSentenceResult:
    return CandidateSentenceResult(text="λύω.", candidates=list(candidates))


# ── 1. Backwards compatibility ─────────────────────────────────────────────────

class TestBackwardsCompat:
    def test_lesson_without_morphology_fields_validates(self):
        """LessonResponse created without any morphology fields must still validate."""
        lesson = LessonResponse(**_minimal_lesson())
        assert lesson.morphology_axes == []
        assert lesson.paradigms == []
        assert lesson.equivalents == []
        assert lesson.contrasts == []
        assert lesson.encountered_vocabulary == []

    def test_existing_fields_unchanged(self):
        drill = FillBlankDrill(type="fill_blank", prompt="λύ___", answer="ω")
        lesson = LessonResponse(**_minimal_lesson(drills=[drill]))
        assert len(lesson.drills) == 1
        assert lesson.drills[0].type == "fill_blank"

    def test_round_trip_json_no_morphology(self):
        lesson = LessonResponse(**_minimal_lesson())
        data = lesson.model_dump()
        restored = LessonResponse(**data)
        assert restored.morphology_axes == []


# ── 2. New morphology fields round-trip ────────────────────────────────────────

class TestMorphologyFields:
    def test_morphology_axes_round_trip(self):
        axes = [
            MorphologyAxis(axis="tense", value="present", label="Present"),
            MorphologyAxis(axis="mood", value="indicative"),
        ]
        lesson = LessonResponse(**_minimal_lesson(morphology_axes=axes))
        data = lesson.model_dump()
        restored = LessonResponse(**data)
        assert len(restored.morphology_axes) == 2
        assert restored.morphology_axes[0].axis == "tense"
        assert restored.morphology_axes[1].label is None

    def test_paradigm_round_trip(self):
        cells = [
            ParadigmCell(form="λύω", axes={"person": "1", "number": "singular"}, is_highlighted=True),
            ParadigmCell(form="λύεις", axes={"person": "2", "number": "singular"}),
        ]
        paradigm = MorphologyParadigm(
            title="Present Indicative Active",
            row_axis="person",
            col_axis="number",
            cells=cells,
        )
        lesson = LessonResponse(**_minimal_lesson(paradigms=[paradigm]))
        data = lesson.model_dump()
        restored = LessonResponse(**data)
        assert len(restored.paradigms) == 1
        assert restored.paradigms[0].title == "Present Indicative Active"
        assert restored.paradigms[0].cells[0].is_highlighted is True

    def test_equivalents_round_trip(self):
        eq = EquivalentConstruction(construction="λύειν", note="infinitive form", register="formal")
        lesson = LessonResponse(**_minimal_lesson(equivalents=[eq]))
        data = lesson.model_dump()
        restored = LessonResponse(**data)
        assert restored.equivalents[0].construction == "λύειν"
        assert restored.equivalents[0].register == "formal"

    def test_contrasts_round_trip(self):
        note = ContrastNote(form_a="λύω", form_b="λύομαι", note="active vs middle voice")
        lesson = LessonResponse(**_minimal_lesson(contrasts=[note]))
        data = lesson.model_dump()
        restored = LessonResponse(**data)
        assert restored.contrasts[0].note == "active vs middle voice"

    def test_encountered_vocabulary_round_trip(self):
        ev = EncounteredVocabularySummary(form="θεός", lemma="θεός", gloss="god", pos="NOUN")
        lesson = LessonResponse(**_minimal_lesson(encountered_vocabulary=[ev]))
        data = lesson.model_dump()
        restored = LessonResponse(**data)
        assert restored.encountered_vocabulary[0].lemma == "θεός"


# ── 3. _validate_morphology warnings ──────────────────────────────────────────

class TestValidateMorphology:
    def test_valid_morphology_no_warnings(self):
        morphology = {
            "axes": [
                {"axis": "tense", "value": "present"},
                {"axis": "mood", "value": "indicative"},
            ],
            "paradigms": [
                {"title": "Present", "cells": [{"form": "λύω", "axes": {}}]},
            ],
            "equivalents": [{"construction": "λύειν"}],
            "contrasts": [{"form_a": "λύω", "form_b": "λύομαι", "note": "voice"}],
        }
        ws = _validate_morphology(morphology, 0, "λύω")
        assert ws == []

    def test_m1_not_a_dict(self):
        ws = _validate_morphology("bad", 0, "λύω")
        assert any(w.rule == "M1" for w in ws)

    def test_m2_axes_not_list(self):
        ws = _validate_morphology({"axes": "bad"}, 0, "λύω")
        assert any(w.rule == "M2" and "axes" in w.message for w in ws)

    def test_m2_paradigms_not_list(self):
        ws = _validate_morphology({"paradigms": 42}, 0, "λύω")
        assert any(w.rule == "M2" and "paradigms" in w.message for w in ws)

    def test_m3_axis_entry_not_dict(self):
        ws = _validate_morphology({"axes": ["bad"]}, 0, "λύω")
        assert any(w.rule == "M3" for w in ws)

    def test_m3_axis_missing_value(self):
        ws = _validate_morphology({"axes": [{"axis": "tense"}]}, 0, "λύω")
        assert any(w.rule == "M3" and "'value'" in w.message for w in ws)

    def test_m3_empty_axis_name(self):
        ws = _validate_morphology({"axes": [{"axis": "", "value": "present"}]}, 0, "λύω")
        assert any(w.rule == "M3" and "'axis'" in w.message for w in ws)

    def test_m4_unknown_axis_warns(self):
        ws = _validate_morphology({"axes": [{"axis": "animacy", "value": "animate"}]}, 0, "λύω")
        assert any(w.rule == "M4" and "animacy" in w.message for w in ws)

    def test_m4_known_axes_no_warning(self):
        for axis in VALID_MORPHOLOGY_AXES:
            ws = _validate_morphology({"axes": [{"axis": axis, "value": "x"}]}, 0, "f")
            m4 = [w for w in ws if w.rule == "M4"]
            assert m4 == [], f"Known axis {axis!r} should not trigger M4"

    def test_m5_paradigm_cells_not_list(self):
        ws = _validate_morphology({"paradigms": [{"cells": "bad"}]}, 0, "λύω")
        assert any(w.rule == "M5" and "cells" in w.message for w in ws)

    def test_m5_paradigm_not_dict(self):
        ws = _validate_morphology({"paradigms": ["bad"]}, 0, "λύω")
        assert any(w.rule == "M5" for w in ws)

    def test_m6_equivalent_no_construction(self):
        ws = _validate_morphology({"equivalents": [{"note": "foo"}]}, 0, "λύω")
        assert any(w.rule == "M6" and "construction" in w.message for w in ws)

    def test_m6_equivalent_not_dict(self):
        ws = _validate_morphology({"equivalents": [42]}, 0, "λύω")
        assert any(w.rule == "M6" for w in ws)

    def test_m7_contrast_missing_note(self):
        ws = _validate_morphology(
            {"contrasts": [{"form_a": "λύω", "form_b": "λύομαι"}]}, 0, "λύω"
        )
        assert any(w.rule == "M7" and "'note'" in w.message for w in ws)

    def test_m7_contrast_not_dict(self):
        ws = _validate_morphology({"contrasts": ["bad"]}, 0, "λύω")
        assert any(w.rule == "M7" for w in ws)

    def test_empty_morphology_no_warnings(self):
        ws = _validate_morphology({}, 0, "λύω")
        assert ws == []


# ── 4. VALID_MORPHOLOGY_AXES completeness ─────────────────────────────────────

class TestValidMorphologyAxes:
    EXPECTED = {"tense", "aspect", "mood", "person", "number", "gender", "case", "voice", "polarity"}

    def test_expected_axes_present(self):
        assert self.EXPECTED <= VALID_MORPHOLOGY_AXES

    def test_is_frozenset(self):
        assert isinstance(VALID_MORPHOLOGY_AXES, frozenset)


# ── 5. validate_result integration ────────────────────────────────────────────

class TestValidateResultMorphologyIntegration:
    def test_no_morphology_key_no_warnings(self):
        result = _result(_candidate())
        report = validate_result(result, _FakePlugin(), input_sentence="λύω.")
        assert report.ok
        assert report.warnings == []

    def test_valid_morphology_no_warnings(self):
        morph = {"axes": [{"axis": "tense", "value": "present"}]}
        cand = _candidate(lesson_data={"tense": "present", "mood": "indicative", "morphology": morph})
        result = _result(cand)
        report = validate_result(result, _FakePlugin(), input_sentence="λύω.")
        assert report.ok
        assert report.warnings == []

    def test_malformed_morphology_produces_warnings_not_violations(self):
        morph = {"axes": "not-a-list"}
        cand = _candidate(lesson_data={"tense": "present", "mood": "indicative", "morphology": morph})
        result = _result(cand)
        report = validate_result(result, _FakePlugin(), input_sentence="λύω.")
        assert report.ok, "Malformed morphology must not produce a hard violation"
        assert any(w.rule == "M2" for w in report.warnings)

    def test_unknown_axis_warning_in_report(self):
        morph = {"axes": [{"axis": "animacy", "value": "animate"}]}
        cand = _candidate(lesson_data={"tense": "present", "mood": "indicative", "morphology": morph})
        result = _result(cand)
        report = validate_result(result, _FakePlugin(), input_sentence="λύω.")
        assert report.ok
        assert any(w.rule == "M4" for w in report.warnings)

    def test_contract_report_str_includes_warning(self):
        morph = {"axes": [{"axis": "animacy", "value": "animate"}]}
        cand = _candidate(lesson_data={"tense": "present", "mood": "indicative", "morphology": morph})
        result = _result(cand)
        report = validate_result(result, _FakePlugin(), input_sentence="λύω.")
        s = str(report)
        assert "WARNING" in s
        assert "M4" in s


# ── 6. Inflection type — C9 required keys and C11 morphology_depth gate ───────

def _inflection_cand(**overrides) -> CandidateObject:
    defaults: dict = dict(
        canonical_form="lupi",
        type="inflection",
        label="lupi",
        lesson_data={"lemma": "lupus", "surface": "lupi"},
    )
    defaults.update(overrides)
    return CandidateObject(**defaults)


class _NoMorphCaps:
    code = "la"
    direction = "ltr"
    idiom_detection = False
    morphology_depth = "none"
    nuance_capabilities = None


class _BasicMorphCaps:
    code = "la"
    direction = "ltr"
    idiom_detection = False
    morphology_depth = "basic"
    nuance_capabilities = None


class _FullMorphCaps:
    code = "la"
    direction = "ltr"
    idiom_detection = False
    morphology_depth = "full"
    nuance_capabilities = None


class _NoMorphPlugin:
    language_code = "la"
    direction = "ltr"
    capabilities = _NoMorphCaps()


class _BasicMorphPlugin:
    language_code = "la"
    direction = "ltr"
    capabilities = _BasicMorphCaps()


class _FullMorphPlugin:
    language_code = "la"
    direction = "ltr"
    capabilities = _FullMorphCaps()


class TestInflectionContract:

    # C9 — required lesson_data keys

    def test_c9_inflection_missing_lemma_triggers_violation(self):
        cand = _inflection_cand(lesson_data={"surface": "lupi"})
        result = _result(cand)
        report = validate_result(result, _FullMorphPlugin(), input_sentence="lupi.")
        assert not report.ok
        c9 = [v for v in report.violations if v.rule == "C9"]
        assert len(c9) == 1
        assert "lemma" in c9[0].message

    def test_c9_inflection_missing_surface_triggers_violation(self):
        cand = _inflection_cand(lesson_data={"lemma": "lupus"})
        result = _result(cand)
        report = validate_result(result, _FullMorphPlugin(), input_sentence="lupi.")
        assert not report.ok
        c9 = [v for v in report.violations if v.rule == "C9"]
        assert len(c9) == 1
        assert "surface" in c9[0].message

    def test_c9_inflection_missing_both_triggers_one_violation(self):
        cand = _inflection_cand(lesson_data={})
        result = _result(cand)
        report = validate_result(result, _FullMorphPlugin(), input_sentence="lupi.")
        assert not report.ok
        c9 = [v for v in report.violations if v.rule == "C9"]
        assert len(c9) == 1
        assert "lemma" in c9[0].message
        assert "surface" in c9[0].message

    def test_c9_inflection_with_lemma_and_surface_passes(self):
        cand = _inflection_cand()
        result = _result(cand)
        report = validate_result(result, _FullMorphPlugin(), input_sentence="lupi.")
        c9 = [v for v in report.violations if v.rule == "C9"]
        assert c9 == []

    def test_c9_inflection_extra_keys_allowed(self):
        cand = _inflection_cand(lesson_data={
            "lemma": "lupus", "surface": "lupi",
            "case": "Gen", "number": "Sing", "declension_class": "2nd",
        })
        result = _result(cand)
        report = validate_result(result, _FullMorphPlugin(), input_sentence="lupi.")
        c9 = [v for v in report.violations if v.rule == "C9"]
        assert c9 == []

    # C11 — morphology_depth gate

    def test_c11_inflection_with_morphology_depth_none_triggers_violation(self):
        cand = _inflection_cand()
        result = _result(cand)
        report = validate_result(result, _NoMorphPlugin(), input_sentence="lupi.")
        assert not report.ok
        c11 = [v for v in report.violations if v.rule == "C11"]
        assert len(c11) == 1
        assert "inflection" in c11[0].message

    def test_c11_inflection_with_morphology_depth_basic_passes(self):
        cand = _inflection_cand()
        result = _result(cand)
        report = validate_result(result, _BasicMorphPlugin(), input_sentence="lupi.")
        c11 = [v for v in report.violations if v.rule == "C11"]
        assert c11 == []

    def test_c11_inflection_with_morphology_depth_full_passes(self):
        cand = _inflection_cand()
        result = _result(cand)
        report = validate_result(result, _FullMorphPlugin(), input_sentence="lupi.")
        c11 = [v for v in report.violations if v.rule == "C11"]
        assert c11 == []

    def test_c11_conjugation_still_blocked_by_none_depth(self):
        """Regression: existing C11 behaviour for conjugation must be unchanged."""
        cand = _candidate()  # type=conjugation, lesson_data has tense+mood
        result = CandidateSentenceResult(text="lupi.", candidates=[cand])
        report = validate_result(result, _NoMorphPlugin(), input_sentence="lupi.")
        c11 = [v for v in report.violations if v.rule == "C11"]
        assert len(c11) == 1

    def test_c11_vocabulary_never_blocked_regardless_of_depth(self):
        """vocabulary type must not be affected by C11 regardless of morphology_depth."""
        cand = CandidateObject(
            canonical_form="lupus",
            type="vocabulary",
            label="lupus",
            lesson_data={"lemma": "lupus"},
        )
        result = CandidateSentenceResult(text="lupi.", candidates=[cand])
        report = validate_result(result, _NoMorphPlugin(), input_sentence="lupi.")
        c11 = [v for v in report.violations if v.rule == "C11"]
        assert c11 == []
