from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_db_session
from backend.models import UserKnowledgeRow
from backend.schemas.parse import ReviewRequest, ReviewResponse
from backend.srs.fsrs import review
from backend.srs.knowledge import DEFAULT_USER_ID, mastery_score

logger = logging.getLogger(__name__)
router = APIRouter(tags=["review"])


@router.post("/review", response_model=ReviewResponse)
async def submit_review(
    payload: ReviewRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ReviewResponse:
    now = datetime.now(UTC)

    # Load prior FSRS state from UserKnowledge.  DB row takes precedence over
    # the payload-supplied state so that the server's record is authoritative.
    # Fall back to the payload state only when the DB is unavailable.
    prior_state = payload.review_state
    row: UserKnowledgeRow | None = None
    try:
        result = await db.execute(
            select(UserKnowledgeRow).where(
                UserKnowledgeRow.user_id == DEFAULT_USER_ID,
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

    next_days, updated_state = review(quality=payload.quality, state=prior_state, now=now)

    score = mastery_score(updated_state, now)
    due_at = datetime.fromisoformat(updated_state["due_at"])

    try:
        if row is None:
            # No existing row — create a fresh one.
            # (row may be None either because the object was never parsed or
            #  because the DB was unavailable above; both paths are safe here)
            result2 = await db.execute(
                select(UserKnowledgeRow).where(
                    UserKnowledgeRow.user_id == DEFAULT_USER_ID,
                    UserKnowledgeRow.object_id == payload.object_id,
                )
            )
            row = result2.scalar_one_or_none()

        if row is None:
            db.add(UserKnowledgeRow(
                user_id=DEFAULT_USER_ID,
                object_id=payload.object_id,
                fsrs_state=updated_state,
                mastery_score=score,
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
        await db.commit()
    except Exception:
        logger.warning(
            "DB knowledge persist failed for %r", payload.object_id, exc_info=True
        )

    return ReviewResponse(
        object_id=payload.object_id,
        next_interval_days=next_days,
        review_state=updated_state,
    )
