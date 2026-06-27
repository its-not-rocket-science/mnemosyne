"""Tests for concept-type-aware FSRS scheduling adjustments."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.srs.concept_scheduler import (
    CONCEPT_TYPE_MULTIPLIERS,
    apply_concept_type_adjustment,
    concept_label,
)


NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)

SAMPLE_STATE = {
    "stability": 10.0,
    "difficulty": 5.0,
    "reviews": 3,
    "lapses": 0,
    "due_at": (NOW + timedelta(days=10)).isoformat(),
    "last_reviewed_at": NOW.isoformat(),
    "last_retrievability": 0.90,
}


class TestApplyConceptTypeAdjustment:
    def test_vocabulary_unchanged(self):
        days, state = apply_concept_type_adjustment(10, SAMPLE_STATE, "vocabulary", NOW)
        assert days == 10
        assert state is SAMPLE_STATE  # same object, no copy

    def test_nuance_shortens_interval(self):
        days, state = apply_concept_type_adjustment(10, SAMPLE_STATE, "nuance", NOW)
        # nuance multiplier = 0.50
        assert days == 5
        assert "due_at" in state
        expected_due = NOW + timedelta(days=5)
        assert state["due_at"].startswith(expected_due.isoformat()[:16])

    def test_aspect_shortens_interval(self):
        days, state = apply_concept_type_adjustment(20, SAMPLE_STATE, "aspect", NOW)
        assert days == 10

    def test_grammar_slightly_shorter(self):
        days, state = apply_concept_type_adjustment(10, SAMPLE_STATE, "grammar", NOW)
        assert days == 9  # 10 * 0.9 = 9.0

    def test_idiom_shorter(self):
        days, state = apply_concept_type_adjustment(10, SAMPLE_STATE, "idiom", NOW)
        assert days == 7  # 10 * 0.7 = 7.0

    def test_minimum_one_day(self):
        # Very short base interval * nuance multiplier should still be >= 1
        days, state = apply_concept_type_adjustment(1, SAMPLE_STATE, "nuance", NOW)
        assert days >= 1

    def test_unknown_type_returns_original(self):
        days, state = apply_concept_type_adjustment(10, SAMPLE_STATE, "unknown_type", NOW)
        assert days == 10
        assert state is SAMPLE_STATE

    def test_state_not_mutated(self):
        original_due = SAMPLE_STATE["due_at"]
        apply_concept_type_adjustment(10, SAMPLE_STATE, "nuance", NOW)
        assert SAMPLE_STATE["due_at"] == original_due

    def test_all_types_produce_valid_intervals(self):
        for obj_type, mult in CONCEPT_TYPE_MULTIPLIERS.items():
            days, state = apply_concept_type_adjustment(10, SAMPLE_STATE, obj_type, NOW)
            assert days >= 1
            assert isinstance(state, dict)
            assert "due_at" in state


class TestConceptLabel:
    def test_vocabulary_label(self):
        assert concept_label("vocabulary") == "Vocabulary"

    def test_nuance_label(self):
        assert concept_label("nuance") == "Nuance"

    def test_none_returns_none(self):
        assert concept_label(None) is None

    def test_unknown_returns_none(self):
        assert concept_label("not_a_type") is None
