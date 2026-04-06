from fastapi import APIRouter

from backend.schemas.parse import ReviewRequest, ReviewResponse
from backend.srs.fsrs import review

router = APIRouter(tags=["review"])


@router.post("/review", response_model=ReviewResponse)
async def submit_review(payload: ReviewRequest) -> ReviewResponse:
    next_days, state = review(quality=payload.quality, state=payload.review_state)
    return ReviewResponse(
        object_id=payload.object_id,
        next_interval_days=next_days,
        review_state=state,
    )
