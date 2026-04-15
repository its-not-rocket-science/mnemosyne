"""GET /metrics — learning effectiveness snapshot.

Computes review success rates, retention, stability, and weak-area
identification from the current ``user_knowledge`` + ``canonical_objects``
tables.  All computation is in-process (no stored aggregates).

What is computable without a review-event log
─────────────────────────────────────────────
  success_rate      1 − (lapses / reviews) per object, from fsrs_state
  retention         mastery_score = FSRS retrievability R(t, S) right now
  avg_stability     fsrs_state["stability"] — days until R drops to 0.90
  time-since-seen   now − first_seen (requires the first_seen column)
  by_language       filter / group UserKnowledgeRow.language
  by_type           join canonical_objects to get the learnable-object type

What requires a future review_events table
──────────────────────────────────────────
  retention curves  — score at multiple past timestamps
  time-to-mastery   — exact datetime the mastery threshold was first crossed
  per-session stats — reviews per day / week
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db_session
from backend.models import CanonicalObjectRow, UserKnowledgeRow
from backend.schemas.metrics import (
    LanguageMetrics,
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
        return _empty_response()

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

    logger.info(
        "metrics lang=%s seen=%d reviewed=%d mastered=%d retention=%.2f",
        language or "all", total_seen, total_reviewed, total_mastered, overall_retention,
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
    )


def _empty_response() -> MetricsResponse:
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
    )
