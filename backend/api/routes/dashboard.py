from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_db_session
from backend.models import UserKnowledgeRow
from backend.schemas.knowledge import DashboardResponse, KnowledgeObject
from backend.srs.knowledge import (
    DEFAULT_USER_ID,
    KnowledgeStatus,
    classify,
    mastery_score,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dashboard"])


def _ensure_utc(dt: datetime) -> datetime:
    """Return *dt* as a UTC-aware datetime, adding UTC tzinfo if naive.

    SQLite stores datetimes without timezone info; this normalises them
    for comparison with timezone-aware datetimes from Python code.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    language: str | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> DashboardResponse:
    """Return a summary of the learner's knowledge state.

    Pass ``?language=es`` to scope the results to a single language.
    Omit the parameter to return all languages combined.

    All UserKnowledge rows for the default user are loaded and classified
    in-process.  For the single-user MVP this is fast enough; a future
    multi-user version should add indexed DB-side filtering.
    """
    now = datetime.now(UTC)

    try:
        query = select(UserKnowledgeRow).where(
            UserKnowledgeRow.user_id == DEFAULT_USER_ID
        )
        if language is not None:
            query = query.where(UserKnowledgeRow.language == language)
        result = await db.execute(query)
        rows = result.scalars().all()
    except Exception as exc:
        logger.warning("DB dashboard query failed", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    known: list[KnowledgeObject] = []
    weak: list[KnowledgeObject] = []
    new: list[KnowledgeObject] = []
    due_for_review: list[KnowledgeObject] = []

    for row in rows:
        score = mastery_score(row.fsrs_state, now)
        status = classify(row.total_reviews, row.fsrs_state, now)
        obj = KnowledgeObject(
            object_id=row.object_id,
            language=row.language,
            status=status,
            mastery_score=round(score, 4),
            total_reviews=row.total_reviews,
            last_seen=row.last_seen,
            due_at=row.due_at,
        )

        if status == KnowledgeStatus.MASTERED:
            known.append(obj)
        elif status == KnowledgeStatus.NEW:
            new.append(obj)
        else:
            # LEARNING and FORGOTTEN are both "weak" — not yet mastered
            weak.append(obj)

        due_at_aware = _ensure_utc(row.due_at)
        if due_at_aware <= now and row.total_reviews > 0:
            due_for_review.append(obj)

    # Sort due queue by most overdue first
    due_for_review.sort(key=lambda o: _ensure_utc(o.due_at))

    return DashboardResponse(
        known=known,
        weak=weak,
        new=new,
        due_for_review=due_for_review,
        total_objects=len(rows),
    )
