from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db_session
from backend.models import (
    CanonicalObjectRow,
    ReviewEventRow,
    TermProgressRow,
    UserFsrsParamsRow,
    UserKnowledgeRow,
)
from backend.schemas.parse import ReviewRequest, ReviewResponse
from backend.srs.fsrs import DESIRED_RETENTION, review
from backend.srs.knowledge import mastery_score
from backend.srs.term_scheduler import classify_term

logger = logging.getLogger(__name__)
router = APIRouter(tags=["review"])


@router.post("/review", response_model=ReviewResponse)
async def submit_review(
    payload: ReviewRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> ReviewResponse:
    now = datetime.now(UTC)

    # Load per-user desired_retention (defaults to DESIRED_RETENTION if absent).
    user_desired_retention = DESIRED_RETENTION
    try:
        params_row = await db.get(UserFsrsParamsRow, current_user)
        if params_row is not None:
            user_desired_retention = params_row.desired_retention
    except Exception:
        logger.warning(
            "DB fsrs-params load failed for user %r, using default", current_user, exc_info=True
        )

    # Load prior FSRS state from UserKnowledge.  DB row takes precedence over
    # the payload-supplied state so that the server's record is authoritative.
    # Fall back to the payload state only when the DB is unavailable.
    prior_state = payload.review_state
    row: UserKnowledgeRow | None = None
    try:
        result = await db.execute(
            select(UserKnowledgeRow).where(
                UserKnowledgeRow.user_id == current_user,
                UserKnowledgeRow.object_id == payload.object_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is not None:
            prior_state = row.fsrs_state
    except Exception:
        logger.warning(
            "DB knowledge load failed for %r", payload.object_id, exc_info=True
        )

    score_before = mastery_score(prior_state, now)
    next_days, updated_state = review(
        quality=payload.quality,
        state=prior_state,
        now=now,
        desired_retention=user_desired_retention,
    )

    score = mastery_score(updated_state, now)
    due_at = datetime.fromisoformat(updated_state["due_at"])

    try:
        if row is None:
            # No existing row — create a fresh one.
            # (row may be None either because the object was never parsed or
            #  because the DB was unavailable above; both paths are safe here)
            result2 = await db.execute(
                select(UserKnowledgeRow).where(
                    UserKnowledgeRow.user_id == current_user,
                    UserKnowledgeRow.object_id == payload.object_id,
                )
            )
            row = result2.scalar_one_or_none()

        if row is None:
            db.add(UserKnowledgeRow(
                user_id=current_user,
                object_id=payload.object_id,
                fsrs_state=updated_state,
                mastery_score=score,
                first_seen=now,
                last_seen=now,
                total_reviews=updated_state["reviews"],
                due_at=due_at,
            ))
        else:
            row.fsrs_state = updated_state
            row.mastery_score = score
            row.last_seen = now
            row.total_reviews = updated_state["reviews"]
            row.due_at = due_at
        db.add(ReviewEventRow(
            user_id=current_user,
            object_id=payload.object_id,
            quality=payload.quality,
            mastery_score_before=round(score_before, 4),
            mastery_score_after=round(score, 4),
            reviewed_at=now,
        ))
        await db.commit()
    except Exception:
        logger.warning(
            "DB knowledge persist failed for %r", payload.object_id, exc_info=True
        )

    # Sync TermProgressRow so Memory Map reflects this review.
    # Runs after the FSRS commit; failure here is non-fatal.
    tp_synced: TermProgressRow | None = None
    try:
        canonical_obj = await db.get(CanonicalObjectRow, payload.object_id)
        if canonical_obj is not None:
            correct = payload.quality >= 3
            tp_row = await db.get(
                TermProgressRow,
                (current_user, canonical_obj.language, canonical_obj.display_label),
            )
            if tp_row is None:
                tp_row = TermProgressRow(
                    user_id=current_user,
                    language=canonical_obj.language,
                    term=canonical_obj.display_label,
                    lemma=canonical_obj.canonical_form,
                    first_seen=now,
                    last_seen=now,
                    exposure_count=1,
                    review_count=1,
                    correct_count=1 if correct else 0,
                    incorrect_count=0 if correct else 1,
                    mastery_score=round(score, 4),
                    next_review_at=due_at,
                    source_lesson_ids=[payload.object_id],
                )
                db.add(tp_row)
            else:
                tp_row.last_seen = now
                tp_row.review_count += 1
                if correct:
                    tp_row.correct_count += 1
                else:
                    tp_row.incorrect_count += 1
                tp_row.mastery_score = round(score, 4)
                tp_row.next_review_at = due_at
                if payload.object_id not in (tp_row.source_lesson_ids or []):
                    tp_row.source_lesson_ids = list(tp_row.source_lesson_ids or []) + [payload.object_id]
            await db.commit()
            tp_synced = tp_row
    except Exception:
        logger.warning(
            "TermProgress sync failed for %r", payload.object_id, exc_info=True
        )

    review_bucket: str | None = None
    if tp_synced is not None:
        review_bucket = classify_term(
            review_count=tp_synced.review_count,
            mastery_score=tp_synced.mastery_score,
            next_review_at=tp_synced.next_review_at,
            now=now,
        )

    return ReviewResponse(
        object_id=payload.object_id,
        next_interval_days=next_days,
        review_state=updated_state,
        mastery_score_before=round(score_before, 4),
        mastery_score=round(score, 4),
        next_review_at=due_at.isoformat(),
        review_count=tp_synced.review_count if tp_synced else None,
        correct_count=tp_synced.correct_count if tp_synced else None,
        incorrect_count=tp_synced.incorrect_count if tp_synced else None,
        review_bucket=review_bucket,
    )
