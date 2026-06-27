"""GET /metrics — learning effectiveness snapshot.

Computes review success rates, retention, stability, and weak-area
identification from the current ``user_knowledge`` + ``canonical_objects``
tables.  Activity figures (streak, daily counts) come from ``review_events``.
All computation is in-process (no stored aggregates).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db_session
from backend.core.config import get_settings
from backend.models import (
    CanonicalObjectRow,
    LearningEventRow,
    ReviewEventRow,
    UserKnowledgeRow,
    UserRow,
    UserSentenceReviewRow,
)
from backend.schemas.metrics import (
    DailyActivity,
    LanguageMetrics,
    LearningEventSummary,
    LearningEventsResponse,
    MetricsResponse,
    TypeMetrics,
    WeakObject,
)
from backend.srs.knowledge import (
    MASTERY_SCORE_THRESHOLD,
    MIN_REVIEWS_FOR_MASTERY,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["metrics"])

_WEAKEST_LIMIT = 10


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    language: str | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> MetricsResponse:
    """Return a learning-effectiveness snapshot for the default user.

    Pass ``?language=es`` to scope all figures to a single language.
    """
    now = datetime.now(UTC)

    # ── Load user_knowledge joined with canonical_objects for type info ────────
    try:
        stmt = (
            select(
                UserKnowledgeRow,
                CanonicalObjectRow.type.label("obj_type"),
                CanonicalObjectRow.canonical_form.label("canonical_form"),
            )
            .select_from(UserKnowledgeRow)
            .outerjoin(
                CanonicalObjectRow,
                CanonicalObjectRow.id == UserKnowledgeRow.object_id,
            )
            .where(UserKnowledgeRow.user_id == current_user)
        )
        if language is not None:
            stmt = stmt.where(UserKnowledgeRow.language == language)

        result = await db.execute(stmt)
        rows = result.all()
    except Exception as exc:
        logger.warning("DB metrics query failed", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    if not rows:
        reviews_today, streak_days, daily_activity = await _activity_metrics(
            db, current_user, now
        )
        return _empty_response(
            reviews_today=reviews_today,
            streak_days=streak_days,
            daily_activity=daily_activity,
        )

    # ── Aggregate in Python ───────────────────────────────────────────────────

    # Per-language buckets: {lang: {seen, reviewed, mastered, retention_sum}}
    by_lang: dict[str, dict] = defaultdict(lambda: dict(seen=0, reviewed=0, mastered=0, ret_sum=0.0))
    # Per-type buckets (from canonical_objects join)
    by_type: dict[str, dict] = defaultdict(lambda: dict(seen=0, reviewed=0, mastered=0, ret_sum=0.0))

    total_seen = 0
    total_reviewed = 0
    total_mastered = 0
    ret_sum = 0.0          # mastery_score sum for reviewed objects
    success_sum = 0.0      # (1 - lapse_rate) sum for reviewed objects
    stability_sum = 0.0
    overdue_count = 0

    weak_candidates: list[tuple[float, UserKnowledgeRow, str | None, str | None]] = []

    for row_tuple in rows:
        uk: UserKnowledgeRow = row_tuple[0]
        obj_type: str | None = row_tuple[1]
        canonical_form: str | None = row_tuple[2]

        lang = uk.language or "unknown"
        total_seen += 1
        by_lang[lang]["seen"] += 1
        if obj_type:
            by_type[obj_type]["seen"] += 1

        reviewed = uk.total_reviews > 0
        mastered = (
            reviewed
            and uk.mastery_score >= MASTERY_SCORE_THRESHOLD
            and uk.total_reviews >= MIN_REVIEWS_FOR_MASTERY
        )

        if reviewed:
            total_reviewed += 1
            ret_sum += uk.mastery_score
            by_lang[lang]["reviewed"] += 1
            if obj_type:
                by_type[obj_type]["reviewed"] += 1

            # Per-object success rate from FSRS state
            lapses = uk.fsrs_state.get("lapses", 0) if uk.fsrs_state else 0
            lapse_rate = lapses / uk.total_reviews
            success_sum += 1.0 - lapse_rate

            # FSRS stability
            stability = uk.fsrs_state.get("stability", 0.0) if uk.fsrs_state else 0.0
            stability_sum += stability

            # Retention by group
            by_lang[lang]["ret_sum"] += uk.mastery_score
            if obj_type:
                by_type[obj_type]["ret_sum"] += uk.mastery_score

            # Overdue: due_at <= now (normalise naive datetimes from SQLite)
            due = uk.due_at
            if due.tzinfo is None:
                due = due.replace(tzinfo=UTC)
            if due <= now:
                overdue_count += 1

            # Weak candidates for bottom-N list
            weak_candidates.append((uk.mastery_score, uk, obj_type, canonical_form))

        if mastered:
            total_mastered += 1
            by_lang[lang]["mastered"] += 1
            if obj_type:
                by_type[obj_type]["mastered"] += 1

    overall_retention = ret_sum / total_reviewed if total_reviewed else 0.0
    overall_success = success_sum / total_reviewed if total_reviewed else 0.0
    avg_stability = stability_sum / total_reviewed if total_reviewed else 0.0

    # ── Build weakest list ────────────────────────────────────────────────────
    weak_candidates.sort(key=lambda t: t[0])  # ascending mastery
    weakest: list[WeakObject] = []
    for score, uk, obj_type, canonical_form in weak_candidates[:_WEAKEST_LIMIT]:
        lapses = uk.fsrs_state.get("lapses", 0) if uk.fsrs_state else 0
        lapse_rate = lapses / uk.total_reviews if uk.total_reviews else 0.0
        first = uk.first_seen
        if first is not None and first.tzinfo is None:
            first = first.replace(tzinfo=UTC)
        days_since = (now - first).days if first is not None else None
        weakest.append(WeakObject(
            object_id=uk.object_id,
            language=uk.language,
            type=obj_type,
            canonical_form=canonical_form,
            mastery_score=round(score, 4),
            total_reviews=uk.total_reviews,
            lapse_rate=round(lapse_rate, 4),
            days_since_first_seen=days_since,
        ))

    # ── Build per-language breakdown ─────────────────────────────────────────
    language_rows: list[LanguageMetrics] = []
    for lang, b in sorted(by_lang.items()):
        language_rows.append(LanguageMetrics(
            language=lang,
            seen=b["seen"],
            reviewed=b["reviewed"],
            mastered=b["mastered"],
            retention=round(b["ret_sum"] / b["reviewed"], 4) if b["reviewed"] else 0.0,
        ))

    # ── Build per-type breakdown ──────────────────────────────────────────────
    type_rows: list[TypeMetrics] = []
    for t, b in sorted(by_type.items()):
        type_rows.append(TypeMetrics(
            type=t,
            seen=b["seen"],
            reviewed=b["reviewed"],
            mastered=b["mastered"],
            retention=round(b["ret_sum"] / b["reviewed"], 4) if b["reviewed"] else 0.0,
        ))

    # ── Activity from review_events ──────────────────────────────────────────
    reviews_today, streak_days, daily_activity = await _activity_metrics(
        db, current_user, now
    )

    logger.info(
        "metrics lang=%s seen=%d reviewed=%d mastered=%d retention=%.2f streak=%d",
        language or "all", total_seen, total_reviewed, total_mastered,
        overall_retention, streak_days,
    )

    return MetricsResponse(
        total_seen=total_seen,
        total_reviewed=total_reviewed,
        total_mastered=total_mastered,
        overall_retention=round(overall_retention, 4),
        success_rate=round(overall_success, 4),
        avg_stability_days=round(avg_stability, 4),
        overdue_count=overdue_count,
        by_language=language_rows,
        by_type=type_rows,
        weakest=weakest,
        reviews_today=reviews_today,
        streak_days=streak_days,
        daily_activity=daily_activity,
    )


async def _activity_metrics(
    db: AsyncSession,
    user_id: str,
    now: datetime,
) -> tuple[int, int, list[DailyActivity]]:
    """Return (reviews_today, streak_days, daily_activity) from review_events.

    Loads at most 31 days of events for the user so the query is bounded.
    Falls back to zeroes if the table is unavailable.

    ``daily_activity`` contains one entry per day that had at least one review,
    covering the last 30 calendar days, newest first.  Days with zero reviews
    are omitted to keep the payload small.

    ``streak_days`` is the length of the longest unbroken run of days ending
    on today (UTC).  A day counts if it has at least one review event.
    """
    _LOOKBACK = 31  # days
    cutoff = now - timedelta(days=_LOOKBACK)
    try:
        result = await db.execute(
            select(ReviewEventRow.reviewed_at)
            .where(
                ReviewEventRow.user_id == user_id,
                ReviewEventRow.reviewed_at >= cutoff,
            )
            .order_by(ReviewEventRow.reviewed_at)
        )
        timestamps = [row[0] for row in result.all()]
    except Exception:
        logger.warning("review_events query failed", exc_info=True)
        return 0, 0, []

    if not timestamps:
        return 0, 0, []

    today_utc: date = now.date()

    # Count events per calendar day (UTC).
    counts: dict[date, int] = defaultdict(int)
    for ts in timestamps:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        counts[ts.date()] += 1

    reviews_today = counts.get(today_utc, 0)

    # Streak: walk backwards from today, stop at first gap.
    streak_days = 0
    cursor = today_utc
    while counts.get(cursor, 0) > 0:
        streak_days += 1
        cursor -= timedelta(days=1)

    # Daily activity list for last 30 days, newest first, zero-count days omitted.
    daily_activity: list[DailyActivity] = []
    for i in range(30):
        d = today_utc - timedelta(days=i)
        if d in counts:
            daily_activity.append(DailyActivity(date=d.isoformat(), count=counts[d]))

    return reviews_today, streak_days, daily_activity


def _empty_response(
    reviews_today: int = 0,
    streak_days: int = 0,
    daily_activity: list[DailyActivity] | None = None,
) -> MetricsResponse:
    return MetricsResponse(
        total_seen=0,
        total_reviewed=0,
        total_mastered=0,
        overall_retention=0.0,
        success_rate=0.0,
        avg_stability_days=0.0,
        overdue_count=0,
        by_language=[],
        by_type=[],
        weakest=[],
        reviews_today=reviews_today,
        streak_days=streak_days,
        daily_activity=daily_activity or [],
    )


@router.get("/metrics/learning-events", response_model=LearningEventsResponse)
async def get_learning_events_summary(
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> LearningEventsResponse:
    """Return aggregate learning-event counts grouped by (event_type, language).

    DEBUG mode only — returns 404 in production to prevent aggregate
    enumeration of event types, even though no per-user data is exposed.

    Analytics events are written by the analytics service only when the
    user has not opted out (UserRow.analytics_opt_out=False).
    """
    if not get_settings().debug:
        raise HTTPException(status_code=404, detail="Not found")

    total_rows = await db.scalar(
        select(func.count()).select_from(LearningEventRow)
    ) or 0

    opt_out_count = await db.scalar(
        select(func.count()).select_from(UserRow).where(UserRow.analytics_opt_out.is_(True))
    ) or 0

    summary_result = await db.execute(
        select(
            LearningEventRow.event_type,
            LearningEventRow.language,
            func.sum(LearningEventRow.count).label("total_count"),
            func.count(LearningEventRow.id).label("event_rows"),
        )
        .group_by(LearningEventRow.event_type, LearningEventRow.language)
        .order_by(LearningEventRow.event_type, LearningEventRow.language)
    )

    by_type = [
        LearningEventSummary(
            event_type=row.event_type,
            language=row.language,
            total_count=int(row.total_count or 0),
            event_rows=int(row.event_rows or 0),
        )
        for row in summary_result.all()
    ]

    return LearningEventsResponse(
        total_event_rows=total_rows,
        opt_out_users=opt_out_count,
        by_event_type=by_type,
    )

@router.get("/metrics/forecast")
async def get_review_forecast(
    days: int = Query(default=7, ge=1, le=30),
    language: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> dict:
    """Return projected review item counts per day for the next N days.

    Combines annotation items (UserKnowledgeRow) and sentence review items
    (UserSentenceReviewRow).  Day 0 (today) absorbs all overdue items
    (due_at before today_start) so the caller always sees a full 7-bar chart.
    """
    now         = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    epoch       = datetime(1970, 1, 1, tzinfo=UTC)

    result_days = []
    for i in range(days):
        day_start  = today_start + timedelta(days=i)
        day_end    = day_start   + timedelta(days=1)
        lower      = epoch if i == 0 else day_start

        try:
            ann_q = (
                select(func.count())
                .select_from(UserKnowledgeRow)
                .where(
                    UserKnowledgeRow.user_id == current_user,
                    UserKnowledgeRow.due_at  >= lower,
                    UserKnowledgeRow.due_at  <  day_end,
                )
            )
            if language:
                ann_q = ann_q.where(UserKnowledgeRow.language == language)
            ann_count = (await db.execute(ann_q)).scalar() or 0

            sent_q = (
                select(func.count())
                .select_from(UserSentenceReviewRow)
                .where(
                    UserSentenceReviewRow.user_id == current_user,
                    UserSentenceReviewRow.due_at  >= lower,
                    UserSentenceReviewRow.due_at  <  day_end,
                )
            )
            sent_count = (await db.execute(sent_q)).scalar() or 0
        except Exception as exc:
            logger.warning("forecast day %d query failed: %s", i, exc)
            ann_count = sent_count = 0

        result_days.append({
            "date":             day_start.strftime("%Y-%m-%d"),
            "day_label":        day_start.strftime("%a"),
            "annotation_count": ann_count,
            "sentence_count":   sent_count,
            "total":            ann_count + sent_count,
            "is_today":         i == 0,
        })

    return {"days": result_days, "total_days": days}