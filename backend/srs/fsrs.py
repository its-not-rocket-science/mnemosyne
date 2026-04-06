from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta


@dataclass(slots=True)
class ReviewState:
    due_at: str
    last_reviewed_at: str | None
    reviews: int
    difficulty: float
    stability: float

    def to_dict(self) -> dict[str, str | int | float | None]:
        return asdict(self)


def utcnow() -> datetime:
    return datetime.now(UTC)


def default_state(now: datetime | None = None) -> ReviewState:
    base = now or utcnow()
    return ReviewState(
        due_at=base.isoformat(),
        last_reviewed_at=None,
        reviews=0,
        difficulty=5.0,
        stability=0.4,
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def update_difficulty(difficulty: float, quality: int) -> float:
    adjustment = {1: 0.9, 2: 0.35, 3: -0.15, 4: -0.35}[quality]
    return _clamp(difficulty + adjustment, 1.0, 10.0)


def update_stability(stability: float, difficulty: float, quality: int) -> float:
    if quality == 1:
        return max(0.25, stability * 0.45)
    growth = {2: 1.18, 3: 1.65, 4: 2.3}[quality]
    difficulty_penalty = 1 + ((difficulty - 5.0) / 12.0)
    return max(0.3, stability * growth / difficulty_penalty)


def interval_days(stability: float, difficulty: float, quality: int) -> int:
    base = stability * (11.0 - difficulty)
    multiplier = {1: 0.2, 2: 0.9, 3: 1.3, 4: 1.8}[quality]
    return max(1, round(base * multiplier))


def review(
    *,
    quality: int,
    state: dict | None = None,
    now: datetime | None = None,
) -> tuple[int, dict]:
    if quality not in {1, 2, 3, 4}:
        raise ValueError("quality must be between 1 and 4")

    current_time = now or utcnow()
    review_state = ReviewState(**state) if state is not None else default_state(current_time)

    new_difficulty = update_difficulty(review_state.difficulty, quality)
    new_stability = update_stability(review_state.stability, new_difficulty, quality)
    next_days = interval_days(new_stability, new_difficulty, quality)
    due_at = current_time + timedelta(days=next_days)

    updated = ReviewState(
        due_at=due_at.isoformat(),
        last_reviewed_at=current_time.isoformat(),
        reviews=review_state.reviews + 1,
        difficulty=round(new_difficulty, 4),
        stability=round(new_stability, 4),
    )
    return next_days, updated.to_dict()
