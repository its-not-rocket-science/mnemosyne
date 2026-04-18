"""Tests for backend/srs/fsrs.py.

Organised into focused classes, one per logical concern.  Every test
uses explicit ``now`` / timestamp arguments so there is no dependency on
wall-clock time.
"""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest

from backend.srs.fsrs import (
    DESIRED_RETENTION,
    EASY_BONUS,
    HARD_PENALTY,
    INITIAL_DIFFICULTY,
    INITIAL_STABILITY,
    MAX_STABILITY,
    MIN_STABILITY_LAPSE,
    MIN_STABILITY_RECALL,
    CardState,
    ReviewState,        # backward-compat alias
    default_state,
    next_interval,
    retrievability,
    review,
    stability_after_lapse,
    stability_after_recall,
)

# ── shared fixtures / helpers ────────────────────────────────────────────────

T0 = datetime(2024, 1, 1, tzinfo=UTC)


def _at(days: float) -> datetime:
    """Convenience: T0 + *days* days."""
    return T0 + timedelta(days=days)


def _card(
    *,
    stability: float = 5.0,
    difficulty: float = 5.0,
    reviews: int = 1,
    lapses: int = 0,
    last_days_ago: float = 5.0,
) -> CardState:
    """Build a CardState that was last reviewed *last_days_ago* days before T0."""
    last = _at(-last_days_ago)
    due  = last + timedelta(days=stability)
    return CardState(
        stability=stability,
        difficulty=difficulty,
        reviews=reviews,
        lapses=lapses,
        due_at=due.isoformat(),
        last_reviewed_at=last.isoformat(),
        last_retrievability=None,
    )


# ────────────────────────────────────────────────────────────────────────────
# Forgetting curve / retrievability
# ────────────────────────────────────────────────────────────────────────────

class TestRetrievability:
    """The power-law forgetting curve: R(t, S) = (1 + FACTOR*t/S)**DECAY."""

    def test_at_zero_elapsed_is_one(self) -> None:
        card = _card(stability=10.0, last_days_ago=0.0)
        r = retrievability(card, T0)
        assert math.isclose(r, 1.0, rel_tol=1e-6)

    def test_at_stability_equals_desired_retention(self) -> None:
        # By construction R(S, S) = DESIRED_RETENTION = 0.9
        s = 7.0
        card = _card(stability=s, last_days_ago=s)
        r = retrievability(card, T0)
        assert math.isclose(r, DESIRED_RETENTION, rel_tol=1e-6)

    def test_decreases_monotonically(self) -> None:
        card = _card(stability=10.0, last_days_ago=0.0)
        previous = 1.0
        for days in (1, 3, 7, 14, 30):
            r = retrievability(card, _at(days))
            assert r < previous, f"R did not decrease at t={days}"
            previous = r

    def test_at_double_stability_below_desired_retention(self) -> None:
        s = 10.0
        card = _card(stability=s, last_days_ago=2 * s)
        r = retrievability(card, T0)
        assert r < DESIRED_RETENTION

    def test_new_card_returns_one(self) -> None:
        # A card with no last_reviewed_at has R = 1 by convention.
        card = default_state(T0)
        assert retrievability(card, T0) == 1.0

    def test_higher_stability_means_slower_decay(self) -> None:
        elapsed = 20.0
        low_s  = _card(stability=10.0, last_days_ago=elapsed)
        high_s = _card(stability=50.0, last_days_ago=elapsed)
        assert retrievability(high_s, T0) > retrievability(low_s, T0)

    def test_output_bounded_zero_one(self) -> None:
        for days_ago in (0.0, 0.5, 1.0, 10.0, 100.0, 1000.0):
            r = retrievability(_card(stability=5.0, last_days_ago=days_ago), T0)
            assert 0.0 < r <= 1.0, f"R out of range at t={days_ago}"


# ────────────────────────────────────────────────────────────────────────────
# Next interval
# ────────────────────────────────────────────────────────────────────────────

class TestNextInterval:
    """next_interval(S) gives the number of days until desired_retention."""

    def test_at_desired_retention_equals_stability(self) -> None:
        # For DESIRED_RETENTION = 0.9, interval = round(S).
        for s in (1.0, 2.4, 5.8, 10.0, 30.0):
            assert next_interval(s) == max(1, round(s))

    def test_always_at_least_one(self) -> None:
        assert next_interval(0.001) == 1

    def test_monotone_in_stability(self) -> None:
        intervals = [next_interval(s) for s in (1.0, 2.0, 5.0, 10.0, 30.0)]
        assert intervals == sorted(intervals)

    def test_higher_desired_retention_shortens_interval(self) -> None:
        s = 20.0
        i_90 = next_interval(s, desired_retention=0.90)
        i_95 = next_interval(s, desired_retention=0.95)
        assert i_95 < i_90

    def test_invalid_retention_raises(self) -> None:
        with pytest.raises(ValueError):
            next_interval(10.0, desired_retention=0.0)
        with pytest.raises(ValueError):
            next_interval(10.0, desired_retention=1.0)


# ────────────────────────────────────────────────────────────────────────────
# Stability after recall
# ────────────────────────────────────────────────────────────────────────────

class TestStabilityAfterRecall:
    """stability_after_recall grows S; rating and difficulty modulate growth."""

    # At R = DESIRED_RETENTION (on-time review), stability should grow
    # for all ratings ≥ 2.
    def test_grows_after_good_recall(self) -> None:
        s = 5.0
        new_s = stability_after_recall(s, difficulty=5.0, r=DESIRED_RETENTION, rating=3)
        assert new_s > s

    def test_easy_grows_more_than_good(self) -> None:
        kw = dict(stability=5.0, difficulty=5.0, r=DESIRED_RETENTION)
        assert stability_after_recall(**kw, rating=4) > stability_after_recall(**kw, rating=3)

    def test_good_grows_more_than_hard(self) -> None:
        kw = dict(stability=5.0, difficulty=5.0, r=DESIRED_RETENTION)
        assert stability_after_recall(**kw, rating=3) > stability_after_recall(**kw, rating=2)

    def test_rating_order_respected(self) -> None:
        kw = dict(stability=5.0, difficulty=5.0, r=DESIRED_RETENTION)
        s2 = stability_after_recall(**kw, rating=2)
        s3 = stability_after_recall(**kw, rating=3)
        s4 = stability_after_recall(**kw, rating=4)
        assert s2 < s3 < s4

    def test_low_difficulty_grows_faster_than_high(self) -> None:
        kw = dict(stability=5.0, r=DESIRED_RETENTION, rating=3)
        assert (
            stability_after_recall(**kw, difficulty=2.0)
            > stability_after_recall(**kw, difficulty=8.0)
        )

    def test_reviewing_too_early_gives_no_growth(self) -> None:
        # R ≈ 1.0 (reviewed immediately) → growth factor ≈ 1 → S' ≈ S.
        # The e^(W*(1−R)) − 1 term vanishes as R → 1.
        s = 10.0
        new_s = stability_after_recall(s, difficulty=5.0, r=0.9999, rating=3)
        # Should be barely above the floor, not much above s.
        # (Not equal to s because of rounding, but much less than on-time growth.)
        on_time = stability_after_recall(s, difficulty=5.0, r=DESIRED_RETENTION, rating=3)
        assert new_s < on_time

    def test_output_bounded(self) -> None:
        new_s = stability_after_recall(5.0, difficulty=5.0, r=DESIRED_RETENTION, rating=3)
        assert MIN_STABILITY_RECALL <= new_s <= MAX_STABILITY

    def test_hard_penalty_applied(self) -> None:
        kw = dict(stability=5.0, difficulty=5.0, r=DESIRED_RETENTION)
        raw_growth = stability_after_recall(**kw, rating=3)
        hard_growth = stability_after_recall(**kw, rating=2)
        # Hard/Good growth ratio should reflect HARD_PENALTY.
        assert math.isclose(hard_growth / raw_growth, HARD_PENALTY, rel_tol=0.01)

    def test_easy_bonus_applied(self) -> None:
        kw = dict(stability=5.0, difficulty=5.0, r=DESIRED_RETENTION)
        raw_growth  = stability_after_recall(**kw, rating=3)
        easy_growth = stability_after_recall(**kw, rating=4)
        assert math.isclose(easy_growth / raw_growth, EASY_BONUS, rel_tol=0.01)


# ────────────────────────────────────────────────────────────────────────────
# Stability after lapse
# ────────────────────────────────────────────────────────────────────────────

class TestStabilityAfterLapse:
    """stability_after_lapse shrinks S; hard/stable cards lose more."""

    def test_shrinks_stability(self) -> None:
        s = 10.0
        new_s = stability_after_lapse(s, difficulty=5.0, r=DESIRED_RETENTION)
        assert new_s < s

    def test_never_below_floor(self) -> None:
        new_s = stability_after_lapse(0.0, difficulty=10.0, r=1.0)
        assert new_s >= MIN_STABILITY_LAPSE

    def test_harder_card_loses_more(self) -> None:
        # High D → larger penalty (D^(-exp) is smaller for high D when exp > 0).
        easy_loss = stability_after_lapse(10.0, difficulty=2.0, r=DESIRED_RETENTION)
        hard_loss = stability_after_lapse(10.0, difficulty=8.0, r=DESIRED_RETENTION)
        assert hard_loss < easy_loss

    def test_overdue_card_slightly_softened(self) -> None:
        # Very low R (overdue) vs. on-time R: overdue should be less punishing.
        on_time  = stability_after_lapse(10.0, difficulty=5.0, r=DESIRED_RETENTION)
        overdue  = stability_after_lapse(10.0, difficulty=5.0, r=0.1)
        assert overdue > on_time

    def test_higher_initial_stability_retains_some(self) -> None:
        # A card with S=30 that lapses should have higher new S than one with S=1.
        low  = stability_after_lapse(1.0,  difficulty=5.0, r=DESIRED_RETENTION)
        high = stability_after_lapse(30.0, difficulty=5.0, r=DESIRED_RETENTION)
        assert high > low

    def test_output_bounded(self) -> None:
        new_s = stability_after_lapse(5.0, difficulty=5.0, r=DESIRED_RETENTION)
        assert MIN_STABILITY_LAPSE <= new_s <= MAX_STABILITY


# ────────────────────────────────────────────────────────────────────────────
# CardState serialisation
# ────────────────────────────────────────────────────────────────────────────

class TestCardState:
    def test_to_dict_returns_json_compatible_types(self) -> None:
        state = default_state(T0)
        d = state.to_dict()
        for value in d.values():
            assert isinstance(value, (int, float, str, type(None))), (
                f"Non-JSON-compatible value: {value!r}"
            )

    def test_round_trip_is_identical(self) -> None:
        original = default_state(T0)
        restored = CardState.from_dict(original.to_dict())
        assert original == restored

    def test_from_dict_fills_missing_optional_keys(self) -> None:
        # A state dict from an older version without lapses / last_retrievability.
        minimal = {
            "stability": 5.0,
            "difficulty": 5.0,
            "reviews": 1,
            "due_at": T0.isoformat(),
            "last_reviewed_at": T0.isoformat(),
        }
        card = CardState.from_dict(minimal)
        assert card.lapses == 0
        assert card.last_retrievability is None

    def test_reviewstate_alias(self) -> None:
        assert ReviewState is CardState

    def test_frozen(self) -> None:
        card = default_state(T0)
        with pytest.raises((AttributeError, TypeError)):
            card.stability = 99.0  # type: ignore[misc]  # assignment to frozen dataclass field; we're testing it raises at runtime


# ────────────────────────────────────────────────────────────────────────────
# review() — the top-level scheduling function
# ────────────────────────────────────────────────────────────────────────────

class TestReview:
    def test_returns_positive_interval(self) -> None:
        state = default_state(T0).to_dict()
        days, _ = review(quality=3, state=state, now=T0)
        assert days >= 1

    def test_reviews_counter_increments(self) -> None:
        state = default_state(T0).to_dict()
        _, updated = review(quality=3, state=state, now=T0)
        assert updated["reviews"] == 1
        _, updated2 = review(quality=3, state=updated, now=T0)
        assert updated2["reviews"] == 2

    def test_lapse_increments_lapses(self) -> None:
        state = default_state(T0).to_dict()
        _, first = review(quality=3, state=state, now=T0)
        _, lapsed = review(quality=1, state=first, now=_at(3))
        assert lapsed["lapses"] == 1

    def test_good_does_not_increment_lapses(self) -> None:
        state = default_state(T0).to_dict()
        _, updated = review(quality=3, state=state, now=T0)
        assert updated["lapses"] == 0

    def test_invalid_quality_raises(self) -> None:
        state = default_state(T0).to_dict()
        with pytest.raises(ValueError):
            review(quality=0, state=state, now=T0)
        with pytest.raises(ValueError):
            review(quality=5, state=state, now=T0)

    def test_none_state_creates_new_card(self) -> None:
        days, updated = review(quality=3, state=None, now=T0)
        assert days >= 1
        assert updated["reviews"] == 1

    def test_first_review_uses_initial_stability(self) -> None:
        for q in (1, 2, 3, 4):
            _, updated = review(quality=q, state=None, now=T0)
            assert math.isclose(
                updated["stability"],
                INITIAL_STABILITY[q],
                rel_tol=1e-4,
            ), f"Wrong initial stability for quality={q}"

    def test_first_review_uses_initial_difficulty(self) -> None:
        for q in (1, 2, 3, 4):
            _, updated = review(quality=q, state=None, now=T0)
            assert math.isclose(
                updated["difficulty"],
                INITIAL_DIFFICULTY[q],
                rel_tol=1e-4,
            ), f"Wrong initial difficulty for quality={q}"

    def test_easy_interval_longer_than_good_longer_than_hard(self) -> None:
        for q in (1, 2, 3, 4):
            s = default_state(T0).to_dict()
            _, s = review(quality=q, state=s, now=T0)      # first review
            days, _ = review(quality=q, state=s, now=_at(next_interval(s["stability"])))
        # Compare second-review intervals
        intervals: dict[int, int] = {}
        for q in (2, 3, 4):
            s0 = default_state(T0).to_dict()
            _, s1 = review(quality=3, state=s0, now=T0)           # same first review
            days, _ = review(quality=q, state=s1, now=_at(next_interval(s1["stability"])))
            intervals[q] = days
        assert intervals[2] < intervals[3] < intervals[4]

    def test_due_at_is_in_future(self) -> None:
        _, updated = review(quality=3, state=None, now=T0)
        due = datetime.fromisoformat(updated["due_at"])
        assert due > T0

    def test_last_reviewed_at_set_to_now(self) -> None:
        _, updated = review(quality=3, state=None, now=T0)
        assert updated["last_reviewed_at"] == T0.isoformat()

    def test_state_is_json_serialisable(self) -> None:
        import json
        _, updated = review(quality=3, state=None, now=T0)
        json.dumps(updated)     # must not raise

    def test_repeated_good_reviews_grow_interval(self) -> None:
        state: dict | None = None
        prev_interval = 0
        t = T0
        for _ in range(6):
            days, state = review(quality=3, state=state, now=t)
            assert days >= prev_interval or days == 1  # allow floor to kick in early
            prev_interval = days
            t = t + timedelta(days=days)
        assert prev_interval > 5     # after 6 Good reviews the interval should be substantial


# ────────────────────────────────────────────────────────────────────────────
# default_state
# ────────────────────────────────────────────────────────────────────────────

class TestDefaultState:
    def test_reviews_zero(self) -> None:
        assert default_state(T0).reviews == 0

    def test_lapses_zero(self) -> None:
        assert default_state(T0).lapses == 0

    def test_last_reviewed_at_is_none(self) -> None:
        assert default_state(T0).last_reviewed_at is None

    def test_due_at_equals_now(self) -> None:
        card = default_state(T0)
        assert card.due_at == T0.isoformat()

    def test_stability_seeded_from_good(self) -> None:
        card = default_state(T0)
        assert math.isclose(card.stability, INITIAL_STABILITY[3])

    def test_difficulty_seeded_from_good(self) -> None:
        card = default_state(T0)
        assert math.isclose(card.difficulty, INITIAL_DIFFICULTY[3])


# ────────────────────────────────────────────────────────────────────────────
# Behavioural / integration properties
# ────────────────────────────────────────────────────────────────────────────

class TestBehaviouralProperties:
    """Higher-level properties that validate the scheduler behaves sensibly."""

    def test_again_gives_shorter_interval_than_good(self) -> None:
        base = default_state(T0).to_dict()
        days_again, _ = review(quality=1, state=base, now=T0)
        days_good,  _ = review(quality=3, state=base, now=T0)
        assert days_again < days_good

    def test_stability_drops_after_lapse(self) -> None:
        s0 = default_state(T0).to_dict()
        _, after_good  = review(quality=3, state=s0, now=T0)
        _, after_lapse = review(quality=1, state=after_good, now=_at(2))
        assert after_lapse["stability"] < after_good["stability"]

    def test_difficulty_increases_after_again(self) -> None:
        s0 = default_state(T0).to_dict()
        _, first = review(quality=3, state=s0, now=T0)          # establishes baseline D
        _, harder = review(quality=1, state=first, now=_at(2))
        assert harder["difficulty"] > first["difficulty"]

    def test_difficulty_decreases_after_easy(self) -> None:
        s0 = default_state(T0).to_dict()
        _, first = review(quality=3, state=s0, now=T0)
        _, easier = review(quality=4, state=first, now=_at(2))
        assert easier["difficulty"] < first["difficulty"]

    def test_difficulty_stable_after_good(self) -> None:
        s0 = default_state(T0).to_dict()
        _, first = review(quality=3, state=s0, now=T0)
        _, again = review(quality=3, state=first, now=_at(2))
        # After Good, D drifts only via mean-reversion; net change is tiny.
        assert abs(again["difficulty"] - first["difficulty"]) < 0.6

    def test_last_retrievability_stored_on_second_review(self) -> None:
        s0 = default_state(T0).to_dict()
        _, first = review(quality=3, state=s0, now=T0)
        # Review 5 days later (stability ≈ 2.4, so R < 1)
        _, second = review(quality=3, state=first, now=_at(5))
        assert second["last_retrievability"] is not None
        assert 0.0 < second["last_retrievability"] <= 1.0

    def test_low_difficulty_card_grows_faster(self) -> None:
        """A card with the same history but lower difficulty should schedule further ahead."""
        r = DESIRED_RETENTION
        s_easy = stability_after_recall(5.0, difficulty=2.0, r=r, rating=3)
        s_hard = stability_after_recall(5.0, difficulty=8.0, r=r, rating=3)
        assert next_interval(s_easy) > next_interval(s_hard)
