"""User knowledge model — mastery scoring and object classification.

All functions are pure (no I/O, no global state).  Pass an explicit *now*
in tests to get deterministic results.

Classification bands
────────────────────
  NEW        The object has been seen (via /parse) but never reviewed.
  LEARNING   Reviewed at least once; not yet mastered or forgotten.
  MASTERED   Retrievability ≥ MASTERY_THRESHOLD and ≥ MIN_REVIEWS reviews.
  FORGOTTEN  Retrievability < FORGOTTEN_THRESHOLD (was known, now decayed).

Mastery score
─────────────
Mastery is defined as the current retrievability R(t, S) — the FSRS power-law
estimate of the probability that the learner can recall the item right now.

  score = R(elapsed, S)  using the learner's stored CardState

A score of 0.9 means the learner would recall the item 9 times in 10.
A score near 0 means the item has been largely forgotten.
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from backend.srs.fsrs import CardState, DESIRED_RETENTION, retrievability

# ── Constants ────────────────────────────────────────────────────────────────

#: All single-user requests use this ID until auth is implemented.
DEFAULT_USER_ID: str = "default"

#: Retrievability must be at or above this to classify as MASTERED.
MASTERY_SCORE_THRESHOLD: float = 0.80

#: Retrievability below this classifies a reviewed item as FORGOTTEN.
FORGOTTEN_SCORE_THRESHOLD: float = 0.30

#: Minimum number of reviews before an item can be classified MASTERED.
#: Prevents a lucky first recall from immediately marking a card as known.
MIN_REVIEWS_FOR_MASTERY: int = 3


# ── Classification ───────────────────────────────────────────────────────────

class KnowledgeStatus(str, Enum):
    NEW = "new"
    LEARNING = "learning"
    MASTERED = "mastered"
    FORGOTTEN = "forgotten"


def mastery_score(fsrs_state: dict | None, now: datetime | None = None) -> float:
    """Current recall probability (0–1) for a stored FSRS state.

    Returns 0.0 for items that have no review history — the learner has not
    yet attempted the item so there is no meaningful recall estimate.
    """
    if fsrs_state is None:
        return 0.0
    card = CardState.from_dict(fsrs_state)
    if card.last_reviewed_at is None:
        return 0.0
    t = now if now is not None else datetime.now(UTC)
    return retrievability(card, t)


def classify(
    total_reviews: int,
    fsrs_state: dict | None,
    now: datetime | None = None,
) -> KnowledgeStatus:
    """Classify a learnable object into one of the four knowledge bands.

    Parameters
    ----------
    total_reviews:
        Number of times the item has been reviewed (0 = never).
    fsrs_state:
        CardState dict from the last review, or None for unseen items.
    now:
        Reference timestamp for retrievability calculation.  Defaults to
        the current UTC time.

    Returns
    -------
    KnowledgeStatus
    """
    if total_reviews == 0:
        return KnowledgeStatus.NEW
    score = mastery_score(fsrs_state, now)
    if score < FORGOTTEN_SCORE_THRESHOLD:
        return KnowledgeStatus.FORGOTTEN
    if score >= MASTERY_SCORE_THRESHOLD and total_reviews >= MIN_REVIEWS_FOR_MASTERY:
        return KnowledgeStatus.MASTERED
    return KnowledgeStatus.LEARNING
