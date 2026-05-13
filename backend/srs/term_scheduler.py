from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class TermSchedulerConfig:
    correct_mastery_gain: float = 0.15
    incorrect_mastery_penalty: float = 0.20
    min_mastery: float = 0.0
    max_mastery: float = 1.0
    initial_interval_days: int = 1
    max_interval_days: int = 60
    incorrect_interval_days: int = 1
    overdue_mastery_penalty: float = 0.08
    mastery_well_learned_threshold: float = 0.85
    growth_factor: float = 1.8


DEFAULT_TERM_SCHEDULER_CONFIG = TermSchedulerConfig()


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def classify_term(
    *,
    review_count: int,
    mastery_score: float,
    next_review_at: datetime | None,
    now: datetime,
    cfg: TermSchedulerConfig = DEFAULT_TERM_SCHEDULER_CONFIG,
) -> str:
    if review_count == 0:
        return "new"
    if next_review_at is not None and next_review_at <= now:
        return "due"
    if mastery_score >= cfg.mastery_well_learned_threshold:
        return "strong"
    if mastery_score >= 0.60:
        return "fading"
    return "learning"


def schedule_after_review(
    *,
    review_count: int,
    mastery_score: float,
    correct: bool,
    now: datetime,
    next_review_at: datetime | None,
    cfg: TermSchedulerConfig = DEFAULT_TERM_SCHEDULER_CONFIG,
) -> tuple[float, datetime]:
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    if next_review_at is not None and next_review_at.tzinfo is None:
        next_review_at = next_review_at.replace(tzinfo=UTC)

    adjusted_mastery = mastery_score
    if next_review_at is not None and next_review_at < now:
        adjusted_mastery -= cfg.overdue_mastery_penalty

    if correct:
        new_mastery = adjusted_mastery + cfg.correct_mastery_gain
    else:
        new_mastery = adjusted_mastery - cfg.incorrect_mastery_penalty
    new_mastery = clamp(new_mastery, cfg.min_mastery, cfg.max_mastery)

    if correct:
        prev_interval = cfg.initial_interval_days if review_count <= 1 else max(
            1, int((next_review_at - now).total_seconds() // 86400)
        ) if next_review_at is not None else cfg.initial_interval_days
        scaled = int(round(prev_interval * cfg.growth_factor * (0.6 + new_mastery)))
        interval_days = max(cfg.initial_interval_days, min(cfg.max_interval_days, scaled))
    else:
        interval_days = cfg.incorrect_interval_days

    return new_mastery, now + timedelta(days=interval_days)
