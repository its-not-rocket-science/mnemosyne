"""FSRS-5-inspired spaced repetition scheduler.

This module implements the core FSRS algorithm concepts — power-law forgetting
curve, memory stability, difficulty drift, and per-path stability updates —
using only the Python standard library.

Design intent
─────────────
Clarity and testability are prioritised over exact reproduction of the
published FSRS-5 optimised weights.  Every coefficient is a named constant
with an explanation.  All scheduling functions are pure (no I/O, no global
state mutation).

Core concepts
─────────────
  S  Stability   Days until retention decays to DESIRED_RETENTION (90 %).
                 Defined so that R(S, S) = 0.9 exactly.
  D  Difficulty  Intrinsic item difficulty ∈ [1, 10].
                 Higher D → slower stability growth.
  R  Retrievability  P(recall) right now, derived from S and elapsed time.

Forgetting curve (FSRS-5 power-law model)
──────────────────────────────────────────
  R(t, S) = (1 + FACTOR × t / S) ** DECAY
  FACTOR = 19/81  and  DECAY = −0.5
  Verify: (1 + 19/81) ** (−0.5)  =  (100/81) ** (−0.5)  =  9/10  =  0.9  ✓

Rating scale (SM-2 / FSRS convention)
──────────────────────────────────────
  1  Again  — complete failure, near-zero recall
  2  Hard   — recalled with significant difficulty
  3  Good   — recalled normally; this is the "on-schedule" rating
  4  Easy   — recalled effortlessly / reviewed far too early

Stability update paths
──────────────────────
  First review  — look up INITIAL_STABILITY[rating]; no history to use.
  Successful recall (rating ≥ 2)  — stability_after_recall() grows S.
  Lapse (rating == 1, not first)  — stability_after_lapse() shrinks S.

Assumptions and limitations
────────────────────────────
  · Parameters are FSRS-5 defaults (or close derivations) without
    per-user or per-deck fitting.  Fitting typically improves retention
    predictions by ~5 percentage points.
  · Only two card lifecycle stages are modelled: *new* (reviews == 0)
    and *review* (reviews ≥ 1).  Multi-step relearning queues
    (common in Anki) are not implemented.
  · Clitic clusters, partial recalls, and hint-assisted recalls are
    not distinguished from full recalls.
  · All timestamps are UTC ISO-8601 strings.  No timezone conversion
    is performed here.
  · Stability is capped at MAX_STABILITY (100 years) to prevent
    pathological growth from very late lucky recalls.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


# ────────────────────────────────────────────────────────────────────────────
# Forgetting-curve constants
# ────────────────────────────────────────────────────────────────────────────
# R(t, S) = (1 + FACTOR * t / S) ** DECAY
# Derived from the requirement R(S, S) = 0.9:
#   0.9 = (1 + FACTOR) ** DECAY  →  FACTOR = 0.9^(1/DECAY) - 1 = 19/81
_DECAY:  float = -0.5
_FACTOR: float = 19.0 / 81.0   # ≈ 0.2346


# ────────────────────────────────────────────────────────────────────────────
# Scheduling parameters  (FSRS-5 defaults or close derivations)
# ────────────────────────────────────────────────────────────────────────────

#: Fraction of items we want to recall at their scheduled review date.
DESIRED_RETENTION: float = 0.90

#: Initial stability (days) for a brand-new card, keyed by first-review rating.
#: Source: FSRS-5 default w-vector w[0]–w[3].
INITIAL_STABILITY: dict[int, float] = {
    1: 0.40,    # Again — schedule for almost-immediate relearning
    2: 0.60,    # Hard  — tomorrow
    3: 2.40,    # Good  — in a few days
    4: 5.80,    # Easy  — comfortable head-start
}

#: Initial difficulty for a brand-new card, keyed by first-review rating.
#: Derived from FSRS-5: D_0(G) = w[4] – exp(w[5]*(G-1)) + 1
#: with w[4] = 7.2, w[5] = 0.53, clamped to [1, 10].
INITIAL_DIFFICULTY: dict[int, float] = {
    1: 7.20,    # Again on first exposure → hard item
    2: 6.51,    # Hard
    3: 5.31,    # Good  (near the midpoint of the scale)
    4: 3.28,    # Easy  → likely easy item
}

#: Desired retention level used as the neutral point (Good, rating 3).
_DIFFICULTY_NEUTRAL: float = 5.0

#: How far difficulty shifts per rating unit away from 3 (Good is neutral).
#: Source: FSRS-5 w[6].
DIFFICULTY_DELTA: float = 0.86

#: Fraction of the neutral midpoint (5.0) blended back into D after each
#: review, preventing runaway drift toward 1 or 10.
#: Source: FSRS-5 w[7].
DIFFICULTY_MEAN_REVERSION: float = 0.10

# ── Stability growth after *successful* recall (rating ≥ 2) ─────────────────
#
#   S'_r = S × [exp(G) × (11 − D) × S^(−P) × (exp(W × (1−R)) − 1) + 1]
#              × hard_penalty × easy_bonus
#
# Intuition:
#   • (11 − D)            — easier items grow faster in absolute terms.
#   • S^(−P)              — dampens growth for already-stable cards.
#   • exp(W×(1−R)) − 1    — rewards "risky" recall near the retention
#                            threshold; reviewing too early (R ≈ 1) gains
#                            almost nothing (≈ 0 contribution).

#: Base growth exponent (FSRS-5 w[8]).
STABILITY_GROWTH: float = 1.49

#: Power applied to current S in the growth formula (FSRS-5 w[9]).
STABILITY_DECAY_POWER: float = 0.14

#: Weight on the (1 − R) retrieval-difficulty bonus (FSRS-5 w[10]).
RECALL_GROWTH_FACTOR: float = 1.00

#: Multiplier on stability growth for a Hard recall (FSRS-5 w[15]).
HARD_PENALTY: float = 0.82

#: Multiplier on stability growth for an Easy recall (FSRS-5 w[16]).
EASY_BONUS: float = 1.22

# ── Stability after a *lapse* (rating == 1, not first review) ───────────────
#
#   S'_f = BASE × D^(−DE) × ((S + 1)^SE − 1) × exp(RP × (1 − R))
#
# A harder card (high D) and a more-stable card (high S) lose proportionally
# more; low retrievability (overdue card) slightly softens the penalty.

#: Base coefficient (FSRS-5 w[11]).
LAPSE_BASE: float = 1.95

#: Difficulty-dependent penalty exponent (FSRS-5 w[12]).
LAPSE_DIFFICULTY_EXP: float = 0.11

#: Stability-loss exponent (FSRS-5 w[13]).
LAPSE_STABILITY_EXP: float = 0.29

#: Recall-state multiplier (FSRS-5 w[14]).
LAPSE_RECALL_PENALTY: float = 2.61

# ── Hard floors and ceilings ─────────────────────────────────────────────────
MIN_STABILITY_RECALL: float = 0.50      # days
MIN_STABILITY_LAPSE:  float = 0.25      # days
MAX_STABILITY:        float = 36500.0   # ~100 years


# ────────────────────────────────────────────────────────────────────────────
# State model
# ────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class CardState:
    """Immutable snapshot of a card's memory state.

    ``frozen=True`` enforces value semantics: every review produces a new
    object rather than mutating the old one, making the scheduler easy to
    test and to audit.

    All numeric fields are rounded to 4 decimal places when constructed via
    ``review()``, so JSON round-trips are bit-identical.

    Parameters
    ----------
    stability:
        S — current memory stability in days.
    difficulty:
        D — intrinsic item difficulty ∈ [1, 10].
    reviews:
        Total review count (0 = card has never been reviewed).
    lapses:
        Count of "Again" (forgotten) responses.
    due_at:
        ISO-8601 UTC datetime for the *next* scheduled review.
    last_reviewed_at:
        ISO-8601 UTC datetime for the most recent review, or None.
    last_retrievability:
        Estimated recall probability *at the time of the last review*
        (i.e. how risky the retrieval was).  None for new cards.
    """
    stability:           float
    difficulty:          float
    reviews:             int
    lapses:              int
    due_at:              str
    last_reviewed_at:    str | None
    last_retrievability: float | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict of all fields."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardState:
        """Reconstruct from a dict previously returned by ``to_dict()``.

        Missing optional keys are defaulted so that states serialised by
        earlier versions of this module can be upgraded transparently.
        """
        return cls(
            stability=data["stability"],
            difficulty=data["difficulty"],
            reviews=data.get("reviews", 0),
            lapses=data.get("lapses", 0),
            due_at=data["due_at"],
            last_reviewed_at=data.get("last_reviewed_at"),
            last_retrievability=data.get("last_retrievability"),
        )


# Backward-compatible alias for code that imported the old name.
ReviewState = CardState


def default_state(now: datetime | None = None) -> CardState:
    """Return a fresh CardState for a card that has never been reviewed.

    The card is immediately due (``due_at == now``) so it enters the
    first-review queue right away.  Stability and difficulty are seeded
    from the Good (3) initial values as a neutral prior.
    """
    base = _utcnow() if now is None else now
    return CardState(
        stability=INITIAL_STABILITY[3],
        difficulty=INITIAL_DIFFICULTY[3],
        reviews=0,
        lapses=0,
        due_at=base.isoformat(),
        last_reviewed_at=None,
        last_retrievability=None,
    )


# ────────────────────────────────────────────────────────────────────────────
# Public scheduling API
# ────────────────────────────────────────────────────────────────────────────

def review(
    *,
    quality: int,
    state: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> tuple[int, dict[str, Any]]:
    """Process a single review and return the updated scheduling state.

    Parameters
    ----------
    quality:
        Learner's self-rating: 1 (Again), 2 (Hard), 3 (Good), 4 (Easy).
    state:
        Dict previously returned by this function, or None for a brand-new card.
        Missing optional keys are back-filled with safe defaults.
    now:
        Review timestamp (UTC).  Defaults to the current UTC time.
        Pass an explicit value in tests to get deterministic output.

    Returns
    -------
    next_interval_days : int
        Number of days until the next scheduled review (always ≥ 1).
    updated_state : dict
        JSON-serialisable dict representing the new CardState.
    """
    if quality not in {1, 2, 3, 4}:
        raise ValueError(f"quality must be 1–4, got {quality!r}")

    t = _utcnow() if now is None else now
    card = CardState.from_dict(state) if state is not None else default_state(t)

    # Retrieve the probability of recall *at this review moment*.
    # For first reviews there is no prior review time, so we use None.
    r: float | None = retrievability(card, t) if card.last_reviewed_at is not None else None

    new_d = _next_difficulty(card.difficulty, quality, card.reviews)
    new_s = _next_stability(card.stability, new_d, r, quality, card.reviews)

    interval = next_interval(new_s)

    updated = CardState(
        stability=round(new_s, 4),
        difficulty=round(new_d, 4),
        reviews=card.reviews + 1,
        lapses=card.lapses + (1 if quality == 1 else 0),
        due_at=(t + timedelta(days=interval)).isoformat(),
        last_reviewed_at=t.isoformat(),
        last_retrievability=round(r, 4) if r is not None else None,
    )
    return interval, updated.to_dict()


# ────────────────────────────────────────────────────────────────────────────
# Core pure functions — these are the stable, testable primitives
# ────────────────────────────────────────────────────────────────────────────

def retrievability(card: CardState, at: datetime) -> float:
    """Probability of recall at *at*, given current memory state.

    Uses the FSRS-5 power-law forgetting curve:

        R(t, S) = (1 + FACTOR × t / S) ** DECAY

    where t is elapsed days since the last review.  FACTOR = 19/81 and
    DECAY = −0.5 ensure R(S, S) = 0.9 by construction.

    Returns 1.0 for cards that have never been reviewed (safe prior).
    """
    if card.last_reviewed_at is None:
        return 1.0
    last = datetime.fromisoformat(card.last_reviewed_at)
    elapsed = max(0.0, (at - last).total_seconds() / 86_400.0)
    return _forgetting_curve(elapsed, card.stability)


def next_interval(
    stability: float,
    desired_retention: float = DESIRED_RETENTION,
) -> int:
    """Days until a card with *stability* should next be reviewed.

    Derived by solving R(t, S) = desired_retention for t:

        t = S / FACTOR × (desired_retention^(1/DECAY) − 1)

    For the default desired_retention = 0.9 this simplifies to t = S,
    which is the defining property of stability.

    Always returns at least 1.
    """
    if desired_retention <= 0.0 or desired_retention >= 1.0:
        raise ValueError("desired_retention must be in (0, 1)")
    t = stability / _FACTOR * (desired_retention ** (1.0 / _DECAY) - 1.0)
    return max(1, round(t))


def stability_after_recall(
    stability: float,
    difficulty: float,
    r: float,
    rating: int,
) -> float:
    """New stability after a *successful* recall (rating 2, 3, or 4).

    Formula (FSRS-5):

        S'_r = S × [exp(G) × (11−D) × S^(−P) × (exp(W×(1−R)) − 1) + 1]
                  × hard_penalty × easy_bonus

    where G = STABILITY_GROWTH, P = STABILITY_DECAY_POWER,
    W = RECALL_GROWTH_FACTOR.

    Growth is maximised when:
      - D is small  (easy items benefit more per review)
      - S is small  (short intervals give a larger proportional boost)
      - R ≈ DESIRED_RETENTION  (on-time recall; reviewing too early
        yields near-zero benefit because exp(W×(1−1)) − 1 = 0)
    """
    growth = (
        math.exp(STABILITY_GROWTH)          # e^w₈ ≈ 4.44
        * (11.0 - difficulty)               # difficulty scaling
        * (stability ** -STABILITY_DECAY_POWER)   # dampens high-S cards
        * (math.exp(RECALL_GROWTH_FACTOR * (1.0 - r)) - 1.0)  # retrieval bonus
        + 1.0
    )
    penalty = HARD_PENALTY if rating == 2 else 1.0
    bonus   = EASY_BONUS   if rating == 4 else 1.0
    new_s   = stability * growth * penalty * bonus
    return _clamp(new_s, MIN_STABILITY_RECALL, MAX_STABILITY)


def stability_after_lapse(
    stability: float,
    difficulty: float,
    r: float,
) -> float:
    """New stability after forgetting (rating == 1, "Again").

    Formula (FSRS-5):

        S'_f = BASE × D^(−DE) × ((S+1)^SE − 1) × exp(RP × (1−R))

    where BASE=LAPSE_BASE, DE=LAPSE_DIFFICULTY_EXP,
    SE=LAPSE_STABILITY_EXP, RP=LAPSE_RECALL_PENALTY.

    Properties:
      - Harder cards (high D) lose more stability.
      - More-stable cards (high S) also lose more in absolute terms
        (the (S+1)^SE term grows with S).
      - Low R (card was already overdue) slightly softens the penalty:
        the learner was in a disadvantaged position.
    """
    new_s = (
        LAPSE_BASE
        * (difficulty ** -LAPSE_DIFFICULTY_EXP)
        * ((stability + 1.0) ** LAPSE_STABILITY_EXP - 1.0)
        * math.exp(LAPSE_RECALL_PENALTY * (1.0 - r))
    )
    return _clamp(new_s, MIN_STABILITY_LAPSE, MAX_STABILITY)


# ────────────────────────────────────────────────────────────────────────────
# Private helpers
# ────────────────────────────────────────────────────────────────────────────

def _forgetting_curve(elapsed_days: float, stability: float) -> float:
    """R(t, S) — raw forgetting-curve computation."""
    return (1.0 + _FACTOR * elapsed_days / stability) ** _DECAY


def _next_difficulty(difficulty: float, quality: int, reviews: int) -> float:
    """Compute updated difficulty.

    First review: use the pre-calibrated INITIAL_DIFFICULTY for the rating.

    Subsequent reviews:
      - Good (3) = neutral; no shift.
      - Again/Hard push D up; Easy pulls it down.
      - A 10 % mean-reversion toward 5.0 prevents runaway drift and acts
        as a soft prior that all items are "average".
    """
    if reviews == 0:
        return float(INITIAL_DIFFICULTY[quality])
    shift = DIFFICULTY_DELTA * (3 - quality)       # positive for hard, negative for easy
    raw = difficulty + shift
    reverted = (
        DIFFICULTY_MEAN_REVERSION * _DIFFICULTY_NEUTRAL
        + (1.0 - DIFFICULTY_MEAN_REVERSION) * raw
    )
    return _clamp(reverted, 1.0, 10.0)


def _next_stability(
    stability: float,
    difficulty: float,
    r: float | None,
    quality: int,
    reviews: int,
) -> float:
    """Route to the correct stability update formula."""
    if reviews == 0:
        # First encounter: use the rating-specific initial value.
        return float(INITIAL_STABILITY[quality])

    # Use DESIRED_RETENTION as the assumed retrievability when we have no
    # timestamp history (edge case: state imported without last_reviewed_at).
    r_safe: float = r if r is not None else DESIRED_RETENTION

    if quality == 1:
        return stability_after_lapse(stability, difficulty, r_safe)
    return stability_after_recall(stability, difficulty, r_safe, quality)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _utcnow() -> datetime:
    return datetime.now(UTC)
