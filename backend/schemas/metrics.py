"""Response schemas for GET /metrics."""
from __future__ import annotations

from pydantic import BaseModel, Field


class DailyActivity(BaseModel):
    """Review count for a single calendar day (UTC)."""
    date: str = Field(description="ISO-8601 date string, e.g. '2026-04-16'")
    count: int = Field(description="Number of reviews submitted on this day")


class LanguageMetrics(BaseModel):
    """Per-language breakdown of knowledge state."""
    language: str
    seen: int = Field(description="Objects encountered via /parse")
    reviewed: int = Field(description="Objects reviewed at least once")
    mastered: int = Field(description="Objects at mastery threshold")
    retention: float = Field(description="Mean mastery_score (reviewed objects only), 0 when none")


class TypeMetrics(BaseModel):
    """Per-object-type breakdown (vocabulary / conjugation / agreement)."""
    type: str
    seen: int
    reviewed: int
    mastered: int
    retention: float = Field(description="Mean mastery_score (reviewed only)")


class WeakObject(BaseModel):
    """A low-mastery object surfaced in the weakest-areas list."""
    object_id: str
    language: str | None
    type: str | None
    canonical_form: str | None
    mastery_score: float
    total_reviews: int
    lapse_rate: float = Field(description="lapses / total_reviews; 0 for unreviewed")
    days_since_first_seen: int | None = Field(
        description="Days since the object was first encountered via /parse; "
                    "None when first_seen is not recorded"
    )


class MetricsResponse(BaseModel):
    """Full metrics snapshot for the default user.

    All figures are computed in-process from the current ``user_knowledge``
    table state.  No historical time-series is stored yet — retention curves
    require a future ``review_events`` table.

    Filtering by ``?language=`` scopes every figure to a single language.
    """
    # ── Overall ───────────────────────────────────────────────────────────────
    total_seen: int = Field(description="Objects ever encountered")
    total_reviewed: int = Field(description="Objects reviewed at least once")
    total_mastered: int = Field(description="Objects at mastery threshold (≥0.80, ≥3 reviews)")
    overall_retention: float = Field(
        description="Mean mastery_score across reviewed objects (0 when none reviewed)"
    )
    success_rate: float = Field(
        description="Mean per-object recall rate = 1 − lapse_rate (reviewed objects only)"
    )
    avg_stability_days: float = Field(
        description="Mean FSRS stability in days (reviewed objects only)"
    )
    overdue_count: int = Field(description="Reviewed objects whose next review is now or overdue")

    # ── Breakdowns ────────────────────────────────────────────────────────────
    by_language: list[LanguageMetrics]
    by_type: list[TypeMetrics]

    # ── Weakest areas ─────────────────────────────────────────────────────────
    weakest: list[WeakObject] = Field(
        description="Up to 10 reviewed objects with the lowest mastery_score"
    )

    # ── Activity (from review_events) ─────────────────────────────────────────
    reviews_today: int = Field(
        default=0,
        description="Reviews submitted today (UTC calendar day)",
    )
    streak_days: int = Field(
        default=0,
        description="Consecutive calendar days (UTC) ending today with ≥1 review",
    )
    daily_activity: list[DailyActivity] = Field(
        default_factory=list,
        description="Per-day review counts for the last 30 days (newest first)",
    )
