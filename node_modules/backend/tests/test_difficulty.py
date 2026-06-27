"""Unit tests for the sentence difficulty scorer.

All tests are synchronous; no database access required.
"""
from __future__ import annotations

import pytest

from backend.difficulty.scorer import (
    KNOWN_THRESHOLD,
    DifficultyScore,
    ObjectMastery,
    _W_GRAMMAR,
    _W_LENGTH,
    _W_UNKNOWN,
    difficulty_label,
    score_sentence,
    target_difficulty_window,
    user_level_label,
)


# ── test helpers ──────────────────────────────────────────────────────────────


def _known(object_id: str, obj_type: str = "vocabulary") -> ObjectMastery:
    """An object the user knows well (above threshold)."""
    return ObjectMastery(
        object_id=object_id,
        obj_type=obj_type,
        mastery_score=0.9,
        total_reviews=5,
    )


def _unknown(object_id: str, obj_type: str = "vocabulary") -> ObjectMastery:
    """An object the user has never reviewed."""
    return ObjectMastery(
        object_id=object_id,
        obj_type=obj_type,
        mastery_score=0.0,
        total_reviews=0,
    )


def _borderline(object_id: str) -> ObjectMastery:
    """An object exactly at the known threshold."""
    return ObjectMastery(
        object_id=object_id,
        obj_type="vocabulary",
        mastery_score=KNOWN_THRESHOLD,
        total_reviews=1,
    )


# ── score_sentence: basic properties ─────────────────────────────────────────


class TestScoreSentenceBasic:
    def test_all_known_low_difficulty(self) -> None:
        objects = [_known(f"id{i}") for i in range(6)]
        score = score_sentence(objects, "El gato grande negro duerme bien.")
        assert score.difficulty < 0.30
        assert score.unknown_count == 0
        assert score.unknown_ratio == 0.0

    def test_all_unknown_high_difficulty(self) -> None:
        objects = [_unknown(f"id{i}") for i in range(4)]
        score = score_sentence(objects, "Habla rápido siempre.")
        assert score.difficulty > 0.40
        assert score.unknown_count == 4
        assert score.unknown_ratio == 1.0

    def test_empty_objects_returns_zero_difficulty(self) -> None:
        score = score_sentence([], "...")
        assert score.difficulty == 0.0
        assert score.total_objects == 0
        assert score.unknown_count == 0
        assert score.known_count == 0

    def test_empty_objects_length_still_scored(self) -> None:
        # Even with no objects, length_score reflects the text length
        short = score_sentence([], "Hi.")
        long  = score_sentence([], "This is a much longer sentence with many words here.")
        assert long.length_score >= short.length_score

    def test_borderline_object_counts_as_known(self) -> None:
        # mastery_score == KNOWN_THRESHOLD is NOT unknown (strict <)
        objects = [_borderline("x")]
        score = score_sentence(objects, "Algo.")
        assert score.unknown_count == 0
        assert score.known_count == 1

    def test_difficulty_bounds(self) -> None:
        for n_unknown in range(7):
            objects = (
                [_known(f"k{i}") for i in range(6 - n_unknown)]
                + [_unknown(f"u{i}") for i in range(n_unknown)]
            )
            score = score_sentence(objects, "Test sentence here now please check.")
            assert 0.0 <= score.difficulty <= 1.0, (
                f"Out of range at n_unknown={n_unknown}: {score.difficulty}"
            )

    def test_counts_sum_to_total(self) -> None:
        objects = [_known("a"), _unknown("b"), _known("c")]
        score = score_sentence(objects, "Three words here.")
        assert score.known_count + score.unknown_count == score.total_objects
        assert score.total_objects == 3

    def test_unknown_ratio_accuracy(self) -> None:
        objects = [_known(f"k{i}") for i in range(8)] + [_unknown(f"u{i}") for i in range(2)]
        score = score_sentence(objects, "Ten objects sentence.")
        assert abs(score.unknown_ratio - 0.2) < 1e-4


# ── score_sentence: component contributions ──────────────────────────────────


class TestScoreSentenceComponents:
    def test_conjugation_raises_grammar_score_vs_vocabulary(self) -> None:
        vocab_only = [_unknown("v1", "vocabulary"), _unknown("v2", "vocabulary")]
        with_conj  = [_unknown("v1", "vocabulary"), _unknown("c1", "conjugation")]
        s_v = score_sentence(vocab_only, "Casa libro.")
        s_c = score_sentence(with_conj,  "Casa habla.")
        assert s_c.grammar_score > s_v.grammar_score

    def test_agreement_raises_grammar_score_vs_vocabulary(self) -> None:
        vocab_only  = [_unknown("v1"), _unknown("v2")]
        with_agree  = [_unknown("v1"), _unknown("a1", "agreement")]
        s_v = score_sentence(vocab_only, "Casa roja.")
        s_a = score_sentence(with_agree, "Casa roja.")
        assert s_a.grammar_score > s_v.grammar_score

    def test_pure_vocabulary_grammar_score_is_zero(self) -> None:
        objects = [_unknown(f"v{i}", "vocabulary") for i in range(5)]
        score = score_sentence(objects, "Una frase con muchas palabras.")
        assert score.grammar_score == 0.0

    def test_all_conjugations_grammar_score_is_0_7(self) -> None:
        # All conjugations: grammar = (n/n)*0.70 = 0.70
        objects = [_unknown(f"c{i}", "conjugation") for i in range(4)]
        score = score_sentence(objects, "Hablo caminas corre lloran.")
        assert abs(score.grammar_score - 0.70) < 1e-4

    def test_all_agreements_grammar_score_is_0_3(self) -> None:
        objects = [_unknown(f"a{i}", "agreement") for i in range(3)]
        score = score_sentence(objects, "Casa roja libro viejo.")
        assert abs(score.grammar_score - 0.30) < 1e-4

    def test_longer_sentence_higher_length_score(self) -> None:
        objects = [_known("v1")]
        short_score = score_sentence(objects, "Hola.")
        long_score  = score_sentence(
            objects, "El gato negro grande duerme bien aquí esta tarde soleada."
        )
        assert long_score.length_score > short_score.length_score

    def test_length_score_caps_at_one(self) -> None:
        objects = [_known("v1")]
        very_long = "word " * 100
        score = score_sentence(objects, very_long)
        assert score.length_score == 1.0

    def test_difficulty_formula_matches_components(self) -> None:
        objects = [_unknown("c1", "conjugation"), _known("v2", "vocabulary")]
        score = score_sentence(objects, "Habla bien.")
        expected = round(
            _W_UNKNOWN * score.unknown_ratio
            + _W_GRAMMAR * score.grammar_score
            + _W_LENGTH  * score.length_score,
            4,
        )
        assert abs(score.difficulty - expected) < 1e-4


# ── target_difficulty_window ──────────────────────────────────────────────────


class TestTargetDifficultyWindow:
    def test_bootstrap_window_for_zero_mastered(self) -> None:
        low, high = target_difficulty_window(0)
        assert low == 0.50
        assert high == 0.75

    def test_all_values_below_bootstrap_threshold_get_bootstrap(self) -> None:
        for n in range(5):  # 0, 1, 2, 3, 4
            assert target_difficulty_window(n) == (0.50, 0.75), f"Failed at n={n}"

    def test_active_window_starts_below_bootstrap_center(self) -> None:
        # bootstrap center = 0.625; active window center at n=5 must be < that
        low, high = target_difficulty_window(5)
        assert (low + high) / 2 < 0.625

    def test_window_has_positive_width(self) -> None:
        for n in [0, 5, 20, 50, 100, 200]:
            low, high = target_difficulty_window(n)
            assert high > low, f"Zero-width window at mastered={n}"

    def test_window_stays_in_unit_interval(self) -> None:
        for n in [0, 5, 10, 50, 100, 200, 1000]:
            low, high = target_difficulty_window(n)
            assert 0.0 <= low <= 1.0, f"low out of range at n={n}: {low}"
            assert 0.0 <= high <= 1.0, f"high out of range at n={n}: {high}"

    def test_window_center_non_decreasing_with_mastery(self) -> None:
        prev = -1.0
        for n in [5, 10, 20, 30, 50, 75, 100, 150]:
            low, high = target_difficulty_window(n)
            center = (low + high) / 2
            assert center >= prev - 1e-9, (
                f"Center decreased at n={n}: {center} < {prev}"
            )
            prev = center

    def test_progression_saturates_at_cap(self) -> None:
        # Beyond _PROGRESSION_CAP (100), window should stop moving
        w100  = target_difficulty_window(100)
        w500  = target_difficulty_window(500)
        w1000 = target_difficulty_window(1000)
        assert w100 == w500 == w1000

    def test_active_window_width_consistent(self) -> None:
        # The half-width is constant in the active phase
        for n in [5, 20, 50, 100]:
            low, high = target_difficulty_window(n)
            assert abs((high - low) - 0.24) < 1e-3, (
                f"Window width unexpected at n={n}: {high - low}"
            )


# ── user_level_label ──────────────────────────────────────────────────────────


class TestUserLevelLabel:
    @pytest.mark.parametrize("n,expected", [
        (0, "beginner"),
        (4, "beginner"),
        (5, "elementary"),
        (19, "elementary"),
        (20, "intermediate"),
        (59, "intermediate"),
        (60, "advanced"),
        (1000, "advanced"),
    ])
    def test_level_boundaries(self, n: int, expected: str) -> None:
        assert user_level_label(n) == expected

    def test_returns_literal_string(self) -> None:
        # Values must be one of the four known strings
        valid = {"beginner", "elementary", "intermediate", "advanced"}
        for n in range(70):
            assert user_level_label(n) in valid


# ── integration: i+1 principle ───────────────────────────────────────────────


class TestIPlusOne:
    def test_twenty_percent_unknown_in_active_window(self) -> None:
        # A sentence with 20% unknown should be in the target window for
        # a user who has mastered ~20 items (elementary level).
        objects = (
            [_known(f"k{i}") for i in range(8)]
            + [_unknown(f"u{i}") for i in range(2)]
        )
        score = score_sentence(objects, "El gato negro grande duerme bien aquí.")
        low, high = target_difficulty_window(20)
        assert low <= score.difficulty <= high, (
            f"i+1 sentence (difficulty={score.difficulty}) not in window [{low}, {high}]"
        )

    def test_all_known_below_active_window(self) -> None:
        # Sentences where everything is known should be below the target window
        # for an active learner (too easy — no new material).
        objects = [_known(f"k{i}") for i in range(5)]
        score = score_sentence(objects, "Short known sentence.")
        low, _ = target_difficulty_window(20)
        # Difficulty with all known is driven only by grammar+length, which
        # for a short vocabulary-only sentence is near 0.
        assert score.difficulty < low

    def test_bootstrap_captures_short_sentences(self) -> None:
        # For a new user, all objects are unknown.  A very short sentence
        # should fall in the bootstrap window (shorter = lower difficulty).
        objects = [_unknown("v1"), _unknown("v2")]
        score = score_sentence(objects, "Casa roja.")
        low, high = target_difficulty_window(0)
        assert low <= score.difficulty <= high, (
            f"Short sentence (difficulty={score.difficulty}) not in bootstrap window"
        )

    def test_bootstrap_excludes_very_long_sentences(self) -> None:
        # For a new user, very long sentences should exceed the bootstrap window.
        objects = [_unknown(f"v{i}", "conjugation") for i in range(15)]
        long_text = " ".join([f"word{i}" for i in range(30)])
        score = score_sentence(objects, long_text)
        _, high = target_difficulty_window(0)
        assert score.difficulty > high, (
            f"Long complex sentence (difficulty={score.difficulty}) unexpectedly in bootstrap window"
        )


# ── difficulty_label ──────────────────────────────────────────────────────────


class TestDifficultyLabel:
    @pytest.mark.parametrize("unknown_ratio,expected", [
        (0.00, "easy"),   # 100% known
        (0.05, "easy"),   # 95% known
        (0.14, "easy"),   # just under the easy/ideal boundary
        (0.15, "ideal"),  # boundary: exactly 15% unknown → ideal
        (0.20, "ideal"),  # ~80% known — classic i+1 zone
        (0.30, "ideal"),  # 70% known — still ideal
        (0.40, "ideal"),  # 60% known — upper edge of ideal
        (0.41, "hard"),   # just over the ideal/hard boundary
        (0.60, "hard"),   # only 40% known
        (1.00, "hard"),   # everything unknown
    ])
    def test_band_boundaries(self, unknown_ratio: float, expected: str) -> None:
        assert difficulty_label(unknown_ratio) == expected, (
            f"unknown_ratio={unknown_ratio} → expected '{expected}'"
        )

    def test_all_known_is_easy(self) -> None:
        objects = [_known(f"k{i}") for i in range(5)]
        score = score_sentence(objects, "El gato duerme bien.")
        assert difficulty_label(score.unknown_ratio) == "easy"

    def test_all_unknown_is_hard(self) -> None:
        objects = [_unknown(f"u{i}") for i in range(5)]
        score = score_sentence(objects, "Habla rápido siempre.")
        assert difficulty_label(score.unknown_ratio) == "hard"

    def test_twenty_percent_unknown_is_ideal(self) -> None:
        objects = (
            [_known(f"k{i}") for i in range(8)]
            + [_unknown(f"u{i}") for i in range(2)]
        )
        score = score_sentence(objects, "El gato negro duerme bien aquí.")
        assert difficulty_label(score.unknown_ratio) == "ideal"

    def test_returns_valid_literal(self) -> None:
        valid = {"easy", "ideal", "hard"}
        for r in [i / 20 for i in range(21)]:  # 0.0, 0.05, ..., 1.0
            assert difficulty_label(r) in valid
