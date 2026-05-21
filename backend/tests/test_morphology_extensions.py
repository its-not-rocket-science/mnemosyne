"""Tests for morphology extension fields in LessonResponse.

Covers:
1. Old/simple lessons serialize all extension lists as empty (backwards-compat).
2. Conjugation lessons emit morphology_axes from flat lesson_data keys.
3. Case agreement lessons emit case, gender, number in morphology_axes.
4. Agreement lessons emit gender and number in morphology_axes.
5. lesson_data paradigm/equivalents/contrasts normalized to exact frontend shapes.
"""
from __future__ import annotations

import json

from backend.lesson.generators import build_lesson


# ── 1. Empty extension lists for old/simple lessons ───────────────────────────


class TestEmptyEnrichmentListsOldLessons:

    def test_vocabulary_has_empty_extension_lists(self):
        r = build_lesson(
            object_id="x", obj_type="vocabulary",
            canonical_form="casa", display_label="casa",
            lesson_data={"lemma": "casa", "pos": "NOUN"},
        )
        assert r.morphology_axes == []
        assert r.paradigms == []
        assert r.equivalents == []
        assert r.contrasts == []
        assert r.encountered_vocabulary == []

    def test_idiom_has_empty_extension_lists(self):
        r = build_lesson(
            object_id="x", obj_type="idiom",
            canonical_form="por supuesto", display_label="por supuesto",
            lesson_data={"phrase": "por supuesto", "meaning": "of course"},
        )
        assert r.morphology_axes == []
        assert r.paradigms == []
        assert r.equivalents == []
        assert r.contrasts == []
        assert r.encountered_vocabulary == []

    def test_grammar_has_empty_extension_lists(self):
        r = build_lesson(
            object_id="x", obj_type="grammar",
            canonical_form="grammar:ser_copula", display_label="ser",
            lesson_data={"pattern": "ser + adj", "usage": "permanent qualities"},
        )
        assert r.morphology_axes == []
        assert r.paradigms == []
        assert r.equivalents == []
        assert r.contrasts == []

    def test_extension_lists_serialize_as_empty_array_not_null(self):
        """JSON output must use [] not null for extension list fields."""
        r = build_lesson(
            object_id="x", obj_type="vocabulary",
            canonical_form="libro", display_label="libro",
            lesson_data={"lemma": "libro", "pos": "NOUN"},
        )
        data = json.loads(r.model_dump_json())
        for field in (
            "morphology_axes", "paradigms", "equivalents",
            "contrasts", "encountered_vocabulary",
        ):
            assert field in data, f"field {field!r} missing from JSON"
            assert data[field] == [], f"{field} must be [] not null"


# ── 2. Conjugation morphology_axes from flat lesson_data ─────────────────────


class TestConjugationMorphologyAxes:

    _CONJ = {
        "lemma": "hablar",
        "surface": "hablo",
        "tense": "present",
        "mood": "indicative",
        "person": "1",
        "number": "Sing",
    }

    def _build(self, data: dict | None = None):
        return build_lesson(
            object_id="x", obj_type="conjugation",
            canonical_form="hablar:present:indicative:1:Sing",
            display_label="hablo",
            lesson_data=data or self._CONJ,
        )

    def test_axes_non_empty(self):
        r = self._build()
        assert len(r.morphology_axes) > 0

    def test_tense_axis_present_and_valued(self):
        axes = {a.axis: a.value for a in self._build().morphology_axes}
        assert axes.get("tense") == "present"

    def test_mood_axis_present_and_valued(self):
        axes = {a.axis: a.value for a in self._build().morphology_axes}
        assert axes.get("mood") == "indicative"

    def test_person_axis_normalized(self):
        axes = {a.axis: a.value for a in self._build().morphology_axes}
        assert axes.get("person") == "first"

    def test_number_axis_normalized(self):
        axes = {a.axis: a.value for a in self._build().morphology_axes}
        assert axes.get("number") == "singular"

    def test_aspect_axis_emitted_when_present(self):
        r = self._build({**self._CONJ, "aspect": "Imp"})
        axes = {a.axis: a.value for a in r.morphology_axes}
        assert axes.get("aspect") == "imperfective"

    def test_aspect_perfective_normalized(self):
        r = self._build({**self._CONJ, "aspect": "Perf"})
        axes = {a.axis: a.value for a in r.morphology_axes}
        assert axes.get("aspect") == "perfective"

    def test_unknown_tense_not_emitted(self):
        r = self._build({**self._CONJ, "tense": "unknown"})
        axes = {a.axis: a.value for a in r.morphology_axes}
        assert "tense" not in axes

    def test_unknown_mood_not_emitted(self):
        r = self._build({**self._CONJ, "mood": "unknown"})
        axes = {a.axis: a.value for a in r.morphology_axes}
        assert "mood" not in axes

    def test_each_axis_has_required_fields_in_json(self):
        """Serialized axes must carry axis, value, label, gloss (null allowed)."""
        data = json.loads(self._build().model_dump_json())
        for ax in data["morphology_axes"]:
            assert "axis" in ax
            assert "value" in ax
            assert "label" in ax
            assert "gloss" in ax


# ── 3. Case agreement morphology_axes ─────────────────────────────────────────


class TestCaseAgreementAxes:

    _CASE = {
        "modifier": "der",
        "modifier_pos": "DET",
        "noun": "Mann",
        "case": "Nom",
        "gender": "Masc",
        "number": "Sing",
    }

    def _build(self):
        return build_lesson(
            object_id="x", obj_type="case_agreement",
            canonical_form="case:nom:der_Mann", display_label="der Mann",
            lesson_data=self._CASE,
        )

    def test_case_axis_is_nominative(self):
        axes = {a.axis: a.value for a in self._build().morphology_axes}
        assert axes.get("case") == "nominative"

    def test_gender_axis_is_masculine(self):
        axes = {a.axis: a.value for a in self._build().morphology_axes}
        assert axes.get("gender") == "masculine"

    def test_number_axis_is_singular(self):
        axes = {a.axis: a.value for a in self._build().morphology_axes}
        assert axes.get("number") == "singular"

    def test_accusative_case_normalized(self):
        r = build_lesson(
            object_id="x", obj_type="case_agreement",
            canonical_form="case:acc:den_Mann", display_label="den Mann",
            lesson_data={**self._CASE, "case": "Acc"},
        )
        axes = {a.axis: a.value for a in r.morphology_axes}
        assert axes.get("case") == "accusative"

    def test_dative_case_normalized(self):
        r = build_lesson(
            object_id="x", obj_type="case_agreement",
            canonical_form="case:dat:dem_Mann", display_label="dem Mann",
            lesson_data={**self._CASE, "case": "Dat"},
        )
        axes = {a.axis: a.value for a in r.morphology_axes}
        assert axes.get("case") == "dative"

    def test_feminine_gender_normalized(self):
        r = build_lesson(
            object_id="x", obj_type="case_agreement",
            canonical_form="case:nom:die_Frau", display_label="die Frau",
            lesson_data={**self._CASE, "noun": "Frau", "gender": "Fem"},
        )
        axes = {a.axis: a.value for a in r.morphology_axes}
        assert axes.get("gender") == "feminine"

    def test_plural_number_normalized(self):
        r = build_lesson(
            object_id="x", obj_type="case_agreement",
            canonical_form="case:nom:die_Männer", display_label="die Männer",
            lesson_data={**self._CASE, "noun": "Männer", "number": "Plur"},
        )
        axes = {a.axis: a.value for a in r.morphology_axes}
        assert axes.get("number") == "plural"


# ── 4. Agreement morphology_axes ──────────────────────────────────────────────


class TestAgreementAxes:

    _AGREE = {
        "modifier": "gran",
        "modifier_pos": "ADJ",
        "noun": "casa",
        "gender": "Fem",
        "number": "Sing",
        "gender_match": True,
        "number_match": True,
    }

    def _build(self):
        return build_lesson(
            object_id="x", obj_type="agreement",
            canonical_form="adj:gran_casa", display_label="gran casa",
            lesson_data=self._AGREE,
        )

    def test_gender_axis_is_feminine(self):
        axes = {a.axis: a.value for a in self._build().morphology_axes}
        assert axes.get("gender") == "feminine"

    def test_number_axis_is_singular(self):
        axes = {a.axis: a.value for a in self._build().morphology_axes}
        assert axes.get("number") == "singular"

    def test_masculine_plural_agreement(self):
        r = build_lesson(
            object_id="x", obj_type="agreement",
            canonical_form="adj:buenos_días", display_label="buenos días",
            lesson_data={**self._AGREE, "noun": "días", "gender": "Masc", "number": "Plur"},
        )
        axes = {a.axis: a.value for a in r.morphology_axes}
        assert axes.get("gender") == "masculine"
        assert axes.get("number") == "plural"


# ── 5a. Paradigm normalization ────────────────────────────────────────────────


class TestParadigmNormalization:

    def _conj_with(self, extra: dict):
        return build_lesson(
            object_id="x", obj_type="conjugation",
            canonical_form="hablar:present:indicative:1:Sing",
            display_label="hablo",
            lesson_data={
                "lemma": "hablar", "surface": "hablo",
                "tense": "present", "mood": "indicative",
                "person": "1", "number": "Sing",
                **extra,
            },
        )

    def test_flat_paradigm_list_produces_one_paradigm(self):
        r = self._conj_with({"paradigm": [
            {"form": "hablo",  "person": "1", "number": "singular", "is_highlighted": True},
            {"form": "hablas", "person": "2", "number": "singular"},
            {"form": "habla",  "person": "3", "number": "singular"},
        ]})
        assert len(r.paradigms) == 1
        assert len(r.paradigms[0].cells) == 3

    def test_highlighted_cell_preserved(self):
        r = self._conj_with({"paradigm": [
            {"form": "hablo", "person": "1", "is_highlighted": True},
            {"form": "hablas", "person": "2"},
        ]})
        highlighted = [c for c in r.paradigms[0].cells if c.is_highlighted]
        assert len(highlighted) == 1
        assert highlighted[0].form == "hablo"

    def test_not_highlighted_by_default(self):
        r = self._conj_with({"paradigm": [
            {"form": "hablas", "person": "2"},
        ]})
        assert not r.paradigms[0].cells[0].is_highlighted

    def test_rich_paradigm_title_row_col_axes(self):
        r = self._conj_with({"morphology": {"paradigms": [{
            "title": "Present Indicative",
            "row_axis": "person",
            "col_axis": "number",
            "cells": [
                {"form": "hablo", "axes": {"person": "1", "number": "singular"}, "is_highlighted": True},
                {"form": "hablas", "axes": {"person": "2", "number": "singular"}},
            ],
        }]}})
        p = r.paradigms[0]
        assert p.title == "Present Indicative"
        assert p.row_axis == "person"
        assert p.col_axis == "number"

    def test_paradigm_cell_frontend_shape_in_json(self):
        r = self._conj_with({"paradigm": [
            {"form": "hablo", "person": "1", "number": "singular"},
        ]})
        data = json.loads(r.model_dump_json())
        cell = data["paradigms"][0]["cells"][0]
        assert "form" in cell
        assert "axes" in cell
        assert "is_highlighted" in cell
        assert "gloss" in cell

    def test_paradigm_table_frontend_shape_in_json(self):
        r = self._conj_with({"morphology": {"paradigms": [{
            "title": "Test",
            "row_axis": "person",
            "col_axis": "number",
            "cells": [{"form": "hablo", "axes": {"person": "1"}}],
        }]}})
        data = json.loads(r.model_dump_json())
        p = data["paradigms"][0]
        assert "title" in p
        assert "row_axis" in p
        assert "col_axis" in p
        assert "cells" in p

    def test_no_paradigm_data_yields_empty_list(self):
        r = self._conj_with({})
        assert r.paradigms == []


# ── 5b. Equivalents normalization ─────────────────────────────────────────────


class TestEquivalentsNormalization:

    def _conj_with(self, extra: dict):
        return build_lesson(
            object_id="x", obj_type="conjugation",
            canonical_form="hablar:present:indicative:1:Sing",
            display_label="hablo",
            lesson_data={
                "lemma": "hablar", "surface": "hablo",
                "tense": "present", "mood": "indicative",
                "person": "1", "number": "Sing",
                **extra,
            },
        )

    def test_string_equivalent_normalized(self):
        r = self._conj_with({"equivalents": ["estoy hablando"]})
        assert len(r.equivalents) == 1
        assert r.equivalents[0].construction == "estoy hablando"

    def test_dict_equivalent_fields_preserved(self):
        r = self._conj_with({"equivalents": [{
            "construction": "estoy hablando",
            "note": "present progressive",
            "register": "informal",
        }]})
        eq = r.equivalents[0]
        assert eq.construction == "estoy hablando"
        assert eq.note == "present progressive"
        assert eq.register == "informal"

    def test_equivalents_frontend_shape_in_json(self):
        r = self._conj_with({"equivalents": [{"construction": "estoy hablando"}]})
        data = json.loads(r.model_dump_json())
        eq = data["equivalents"][0]
        assert "construction" in eq
        assert "note" in eq
        assert "register" in eq
        assert "language_code" in eq

    def test_multiple_equivalents(self):
        r = self._conj_with({"equivalents": [
            "estoy hablando",
            "he de hablar",
        ]})
        assert len(r.equivalents) == 2

    def test_no_equivalents_yields_empty_list(self):
        r = self._conj_with({})
        assert r.equivalents == []

    def test_rich_equivalents_under_morphology_key(self):
        r = self._conj_with({"morphology": {"equivalents": [{
            "construction": "estoy hablando",
            "note": "continuous",
            "register": "neutral",
            "language_code": None,
        }]}})
        assert r.equivalents[0].construction == "estoy hablando"
        assert r.equivalents[0].note == "continuous"


# ── 5c. Contrasts normalization ───────────────────────────────────────────────


class TestContrastsNormalization:

    def _case_with(self, extra: dict):
        return build_lesson(
            object_id="x", obj_type="case_agreement",
            canonical_form="case:nom:der_Mann", display_label="der Mann",
            lesson_data={
                "modifier": "der", "modifier_pos": "DET",
                "noun": "Mann", "case": "Nom",
                "gender": "Masc", "number": "Sing",
                **extra,
            },
        )

    def test_contrast_fields_preserved(self):
        r = self._case_with({"contrasts": [{
            "form_a": "der Mann",
            "form_b": "den Mann",
            "note": "nominative vs accusative",
            "example_a": "Der Mann kommt.",
            "example_b": "Ich sehe den Mann.",
        }]})
        c = r.contrasts[0]
        assert c.form_a == "der Mann"
        assert c.form_b == "den Mann"
        assert c.note == "nominative vs accusative"
        assert c.example_a == "Der Mann kommt."
        assert c.example_b == "Ich sehe den Mann."

    def test_contrasts_frontend_shape_in_json(self):
        r = self._case_with({"contrasts": [{
            "form_a": "der", "form_b": "den", "note": "case",
        }]})
        data = json.loads(r.model_dump_json())
        c = data["contrasts"][0]
        assert "form_a" in c
        assert "form_b" in c
        assert "note" in c
        assert "example_a" in c
        assert "example_b" in c

    def test_contrast_missing_examples_is_none_not_absent(self):
        r = self._case_with({"contrasts": [{
            "form_a": "der", "form_b": "den", "note": "case",
        }]})
        assert r.contrasts[0].example_a is None
        assert r.contrasts[0].example_b is None

    def test_no_contrasts_yields_empty_list(self):
        r = self._case_with({})
        assert r.contrasts == []

    def test_rich_contrasts_under_morphology_key(self):
        r = self._case_with({"morphology": {"contrasts": [{
            "form_a": "der", "form_b": "den",
            "note": "nominative vs accusative",
            "example_a": "Der Mann.",
            "example_b": "Den Mann.",
        }]}})
        c = r.contrasts[0]
        assert c.form_a == "der"
        assert c.note == "nominative vs accusative"

    def test_contrast_drill_emitted_for_each_contrast(self):
        r = self._case_with({"contrasts": [{
            "form_a": "der", "form_b": "den", "note": "case",
        }]})
        rec = [d for d in r.drills if d.type == "recognition"]
        assert any("der" in d.statement and "den" in d.statement for d in rec)

    def test_contrast_recognition_drill_is_false(self):
        r = self._case_with({"contrasts": [{
            "form_a": "der", "form_b": "den", "note": "case",
        }]})
        rec = [d for d in r.drills if d.type == "recognition"]
        contrast_drills = [d for d in rec if "der" in d.statement and "den" in d.statement]
        assert all(d.correct is False for d in contrast_drills)
