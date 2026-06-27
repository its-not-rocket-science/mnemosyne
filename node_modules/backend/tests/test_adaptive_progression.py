"""Tests for adaptive acquisition stage progression."""
from __future__ import annotations

import pytest

from backend.srs.adaptive_progression import (
    STAGES,
    STAGE_THRESHOLDS,
    advance_stage,
    stage_fraction,
    stage_index,
)


class TestAdvanceStage:
    def test_recognition_advances_at_threshold(self):
        result = advance_stage("recognition", 0.60)
        assert result == "guided_recall"

    def test_recognition_stays_below_threshold(self):
        result = advance_stage("recognition", 0.59)
        assert result == "recognition"

    def test_guided_recall_advances(self):
        result = advance_stage("guided_recall", 0.70)
        assert result == "partial_production"

    def test_guided_recall_stays_below(self):
        result = advance_stage("guided_recall", 0.69)
        assert result == "guided_recall"

    def test_partial_production_advances(self):
        result = advance_stage("partial_production", 0.75)
        assert result == "transformation"

    def test_transformation_advances(self):
        result = advance_stage("transformation", 0.80)
        assert result == "free_production"

    def test_free_production_advances(self):
        result = advance_stage("free_production", 0.85)
        assert result == "contextual_interpretation"

    def test_terminal_stage_stays(self):
        result = advance_stage("contextual_interpretation", 1.0)
        assert result == "contextual_interpretation"

    def test_perfect_mastery_from_recognition(self):
        # Only advances one step at a time regardless of score
        result = advance_stage("recognition", 1.0)
        assert result == "guided_recall"

    def test_unknown_stage_treated_as_recognition(self):
        result = advance_stage("not_a_stage", 0.99)
        # advance_stage treats unknown as recognition, so advances to guided_recall
        assert result == "guided_recall"

    def test_zero_mastery_stays(self):
        for stage in STAGES[:-1]:  # all but terminal
            assert advance_stage(stage, 0.0) == stage

    def test_all_thresholds_produce_next_stage(self):
        for stage in STAGES[:-1]:
            threshold = STAGE_THRESHOLDS[stage]
            assert threshold is not None
            result = advance_stage(stage, threshold)
            expected_idx = STAGES.index(stage) + 1
            assert result == STAGES[expected_idx]


class TestStageIndex:
    def test_recognition_is_zero(self):
        assert stage_index("recognition") == 0

    def test_terminal_is_last(self):
        assert stage_index("contextual_interpretation") == len(STAGES) - 1

    def test_unknown_is_zero(self):
        assert stage_index("bogus") == 0


class TestStageFraction:
    def test_recognition_is_zero(self):
        assert stage_fraction("recognition") == 0.0

    def test_terminal_is_one(self):
        assert stage_fraction("contextual_interpretation") == 1.0

    def test_intermediate_between_zero_and_one(self):
        for stage in STAGES[1:-1]:
            frac = stage_fraction(stage)
            assert 0.0 < frac < 1.0
