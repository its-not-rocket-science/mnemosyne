"""Tests for nuance pair loader and discrimination drill generation."""
from __future__ import annotations

import pytest

from backend.lesson.nuance_pairs import (
    build_discrimination_drills,
    get_nuance_sets,
    get_nuance_sets_for_pattern,
    get_nuance_sets_for_type,
)
from backend.schemas.lesson import DiscriminationDrill, NuancePair, NuanceSet


class TestGetNuanceSets:
    def test_spanish_loads(self):
        sets = get_nuance_sets("es")
        assert len(sets) >= 2
        assert all(isinstance(s, NuanceSet) for s in sets)

    def test_russian_loads(self):
        sets = get_nuance_sets("ru")
        assert len(sets) >= 1
        first = sets[0]
        assert first.concept == "perfective_vs_imperfective"
        assert len(first.pairs) >= 2

    def test_french_loads(self):
        sets = get_nuance_sets("fr")
        assert len(sets) >= 1

    def test_german_loads(self):
        sets = get_nuance_sets("de")
        assert len(sets) >= 1

    def test_finnish_loads(self):
        sets = get_nuance_sets("fi", limit=10)
        assert len(sets) >= 5
        concepts = {s.concept for s in sets}
        assert "finnish_location_cases" in concepts
        assert "finnish_negative_auxiliary" in concepts

    def test_finnish_location_case_concept(self):
        sets = get_nuance_sets("fi", concept="finnish_location_cases")
        assert len(sets) == 1
        assert len(sets[0].pairs) >= 4

    def test_japanese_loads(self):
        sets = get_nuance_sets("ja")
        assert len(sets) >= 1

    def test_arabic_loads(self):
        sets = get_nuance_sets("ar")
        assert len(sets) >= 1

    def test_arabic_negation_concept(self):
        sets = get_nuance_sets("ar", concept="negation_particles")
        assert len(sets) == 1
        assert sets[0].concept == "negation_particles"
        assert len(sets[0].pairs) >= 1

    def test_chinese_loads(self):
        sets = get_nuance_sets("zh")
        assert len(sets) >= 1

    def test_chinese_aspect_concept(self):
        sets = get_nuance_sets("zh", concept="aspect_particles")
        assert len(sets) == 1
        assert len(sets[0].pairs) >= 2

    def test_korean_loads(self):
        sets = get_nuance_sets("ko")
        assert len(sets) >= 1

    def test_korean_speech_levels(self):
        sets = get_nuance_sets("ko", concept="speech_levels")
        assert len(sets) == 1

    def test_italian_loads(self):
        sets = get_nuance_sets("it")
        assert len(sets) >= 1

    def test_italian_congiuntivo(self):
        sets = get_nuance_sets("it", concept="congiuntivo_vs_indicativo")
        assert len(sets) == 1

    def test_portuguese_loads(self):
        sets = get_nuance_sets("pt")
        assert len(sets) >= 1

    def test_portuguese_ser_estar_ficar(self):
        sets = get_nuance_sets("pt", concept="ser_estar_ficar")
        assert len(sets) == 1
        assert len(sets[0].pairs) >= 2

    def test_latin_loads(self):
        sets = get_nuance_sets("la")
        assert len(sets) >= 1

    def test_latin_indicative_vs_subjunctive(self):
        sets = get_nuance_sets("la", concept="indicative_vs_subjunctive")
        assert len(sets) == 1

    def test_greek_loads(self):
        sets = get_nuance_sets("grc")
        assert len(sets) >= 1

    def test_greek_ou_vs_me(self):
        sets = get_nuance_sets("grc", concept="ou_vs_me")
        assert len(sets) == 1
        assert len(sets[0].pairs) >= 2

    def test_unknown_language_returns_empty(self):
        sets = get_nuance_sets("xx")
        assert sets == []

    def test_concept_filter(self):
        sets = get_nuance_sets("es", concept="preterite_vs_imperfect")
        assert len(sets) == 1
        assert sets[0].concept == "preterite_vs_imperfect"

    def test_concept_filter_no_match(self):
        sets = get_nuance_sets("es", concept="nonexistent_concept")
        assert sets == []

    def test_limit_respected(self):
        sets = get_nuance_sets("es", limit=1)
        assert len(sets) == 1

    def test_pairs_are_nuance_pair_instances(self):
        sets = get_nuance_sets("es")
        for ns in sets:
            for pair in ns.pairs:
                assert isinstance(pair, NuancePair)

    def test_pair_answer_is_a_or_b(self):
        sets = get_nuance_sets("es")
        for ns in sets:
            for pair in ns.pairs:
                assert pair.answer in ("a", "b"), f"answer must be 'a' or 'b', got {pair.answer!r}"

    def test_pair_has_required_fields(self):
        sets = get_nuance_sets("es")
        for ns in sets:
            for pair in ns.pairs:
                assert pair.sentence_a
                assert pair.sentence_b
                assert pair.question
                assert pair.explanation
                assert pair.dimension


class TestGetNuanceSetsForType:
    def test_imperfect_maps_to_preterite_vs_imperfect(self):
        sets = get_nuance_sets_for_type("es", "imperfect_aspect")
        assert any(s.concept == "preterite_vs_imperfect" for s in sets)

    def test_russian_aspect_maps(self):
        sets = get_nuance_sets_for_type("ru", "russian_aspect")
        assert any(s.concept == "perfective_vs_imperfective" for s in sets)

    def test_finnish_negative_auxiliary_maps(self):
        sets = get_nuance_sets_for_type("fi", "finnish_negative_auxiliary")
        assert any(s.concept == "finnish_negative_auxiliary" for s in sets)

    def test_finnish_consonant_gradation_maps(self):
        sets = get_nuance_sets_for_type("fi", "consonant_gradation")
        assert any(s.concept == "finnish_consonant_gradation" for s in sets)

    def test_unmapped_type_returns_empty(self):
        sets = get_nuance_sets_for_type("es", "totally_unknown_nuance")
        assert sets == []


class TestGetNuanceSetsForPattern:
    def test_ser_copula_maps(self):
        sets = get_nuance_sets_for_pattern("es", "ser_copula")
        assert any(s.concept == "ser_vs_estar" for s in sets)

    def test_estar_copula_maps(self):
        sets = get_nuance_sets_for_pattern("es", "estar_copula")
        assert any(s.concept == "ser_vs_estar" for s in sets)

    def test_unmapped_pattern_returns_empty(self):
        sets = get_nuance_sets_for_pattern("es", "unknown_pattern")
        assert sets == []


class TestBuildDiscriminationDrills:
    def test_returns_discrimination_drills(self):
        drills = build_discrimination_drills("es", concept="preterite_vs_imperfect")
        assert len(drills) >= 1
        assert all(isinstance(d, DiscriminationDrill) for d in drills)

    def test_drill_type_field(self):
        drills = build_discrimination_drills("es", concept="preterite_vs_imperfect")
        for d in drills:
            assert d.type == "discrimination"

    def test_drill_answer_is_a_or_b(self):
        drills = build_discrimination_drills("es")
        for d in drills:
            assert d.answer in ("a", "b")

    def test_drill_has_explanation(self):
        drills = build_discrimination_drills("es", concept="preterite_vs_imperfect")
        for d in drills:
            assert d.explanation

    def test_nuance_type_selector(self):
        drills = build_discrimination_drills("es", nuance_type="imperfect_aspect")
        assert len(drills) >= 1
        assert all(d.concept == "preterite_vs_imperfect" for d in drills)

    def test_pattern_id_selector(self):
        drills = build_discrimination_drills("es", pattern_id="ser_copula")
        assert len(drills) >= 1

    def test_unknown_language_returns_empty(self):
        drills = build_discrimination_drills("xx", concept="preterite_vs_imperfect")
        assert drills == []

    def test_pairs_per_set_limits_output(self):
        drills = build_discrimination_drills("es", concept="preterite_vs_imperfect", pairs_per_set=1)
        assert len(drills) == 1

    def test_russian_drills(self):
        drills = build_discrimination_drills("ru", nuance_type="russian_aspect")
        assert len(drills) >= 1
        for d in drills:
            assert d.sentence_a
            assert d.sentence_b

    def test_arabic_negation_drills(self):
        drills = build_discrimination_drills("ar", nuance_type="negation_la")
        assert len(drills) >= 1
        assert all(d.concept == "negation_particles" for d in drills)

    def test_chinese_aspect_drills(self):
        drills = build_discrimination_drills("zh", nuance_type="aspect_le")
        assert len(drills) >= 1
        assert all(d.concept == "aspect_particles" for d in drills)

    def test_korean_politeness_drills(self):
        drills = build_discrimination_drills("ko", nuance_type="politeness")
        assert len(drills) >= 1
        assert all(d.concept == "speech_levels" for d in drills)

    def test_italian_congiuntivo_drills(self):
        drills = build_discrimination_drills("it", nuance_type="congiuntivo")
        assert len(drills) >= 1

    def test_portuguese_personal_infinitive_drills(self):
        drills = build_discrimination_drills("pt", nuance_type="personal_infinitive")
        assert len(drills) >= 1

    def test_latin_subjunctive_drills(self):
        drills = build_discrimination_drills("la", nuance_type="discourse_particle_la")
        assert len(drills) >= 1

    def test_greek_negation_drills(self):
        drills = build_discrimination_drills("grc", nuance_type="negation_ou")
        assert len(drills) >= 1
        assert all(d.concept == "ou_vs_me" for d in drills)

    def test_finnish_passive_drills(self):
        drills = build_discrimination_drills("fi", nuance_type="finnish_passive_voice")
        assert len(drills) >= 1
        assert all(d.concept == "finnish_passive_voice" for d in drills)


class TestNuanceSchemaPydantic:
    """Schema validation — ensure Pydantic accepts all data from files."""

    def test_nuance_pair_round_trip(self):
        pair = NuancePair(
            sentence_a="Ayer comí.",
            sentence_b="Comía todos los días.",
            label_a="completed",
            label_b="habitual",
            question="Which is a single event?",
            answer="a",
            dimension="temporal",
            explanation="Preterite = completed; imperfect = habitual.",
            cefr_level="B1",
        )
        data = pair.model_dump()
        roundtripped = NuancePair(**data)
        assert roundtripped.answer == "a"

    def test_nuance_set_round_trip(self):
        ns = NuanceSet(
            concept="test_concept",
            title="Test",
            dimension="temporal",
            description="A test set.",
            cefr_level="B1",
        )
        data = ns.model_dump()
        roundtripped = NuanceSet(**data)
        assert roundtripped.concept == "test_concept"

    def test_discrimination_drill_round_trip(self):
        drill = DiscriminationDrill(
            type="discrimination",
            concept="test",
            dimension="temporal",
            sentence_a="A",
            sentence_b="B",
            question="Which?",
            answer="a",
            explanation="Because.",
        )
        assert drill.type == "discrimination"
        assert drill.answer == "a"
