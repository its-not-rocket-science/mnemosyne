from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_db_session
from backend.models import ReviewStateRow
from backend.schemas.parse import ReviewRequest, ReviewResponse
from backend.srs.fsrs import review

logger = logging.getLogger(__name__)
router = APIRouter(tags=["review"])


@router.post("/review", response_model=ReviewResponse)
async def submit_review(
    payload: ReviewRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ReviewResponse:
    # Load prior state from DB; fall back to payload-supplied state if DB
    # is unavailable or the object has never been reviewed.
    review_state = payload.review_state
    try:
        row = await db.get(ReviewStateRow, payload.object_id)
        if row is not None:
            review_state = row.state
    except Exception:
        logger.warning("DB review state load failed for %r", payload.object_id, exc_info=True)

    next_days, updated_state = review(quality=payload.quality, state=review_state)

    try:
        row = await db.get(ReviewStateRow, payload.object_id)
        if row is None:
            db.add(ReviewStateRow(object_id=payload.object_id, state=updated_state))
        else:
            row.state = updated_state
            row.updated_at = datetime.now(UTC)
        await db.commit()
    except Exception:
        logger.warning("DB review state persist failed for %r", payload.object_id, exc_info=True)

    return ReviewResponse(
        object_id=payload.object_id,
        next_interval_days=next_days,
        review_state=updated_state,
    )
