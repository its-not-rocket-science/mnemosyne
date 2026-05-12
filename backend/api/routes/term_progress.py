from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db_session
from backend.models import TermProgressRow
from backend.schemas.term_progress import TermProgressOut, TermProgressUpsert

router = APIRouter(prefix="/term-progress", tags=["term-progress"])


@router.get("/{language}", response_model=list[TermProgressOut])
async def list_term_progress(
    language: str,
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> list[TermProgressOut]:
    result = await db.execute(
        select(TermProgressRow)
        .where(TermProgressRow.user_id == current_user, TermProgressRow.language == language)
        .order_by(TermProgressRow.last_seen.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.post("", response_model=TermProgressOut)
async def upsert_term_progress(
    payload: TermProgressUpsert,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> TermProgressOut:
    now = datetime.now(UTC)
    row = await db.get(TermProgressRow, (current_user, payload.language, payload.term))

    if row is None:
        row = TermProgressRow(
            user_id=current_user,
            language=payload.language,
            term=payload.term,
            lemma=payload.lemma,
            first_seen=now,
            last_seen=now,
            exposure_count=0,
            review_count=0,
            correct_count=0,
            incorrect_count=0,
            mastery_score=0.0,
            next_review_at=payload.next_review_at,
            source_lesson_ids=[],
        )
        db.add(row)

    if payload.lemma:
        row.lemma = payload.lemma
    if payload.seen:
        row.exposure_count += 1
        row.last_seen = now
    if payload.reviewed:
        row.review_count += 1
        if payload.correct is True:
            row.correct_count += 1
        elif payload.correct is False:
            row.incorrect_count += 1
    row.mastery_score = max(0.0, min(1.0, row.mastery_score + payload.mastery_delta))
    if payload.next_review_at is not None:
        row.next_review_at = payload.next_review_at
    if payload.source_lesson_id and payload.source_lesson_id not in row.source_lesson_ids:
        row.source_lesson_ids = list(row.source_lesson_ids) + [payload.source_lesson_id]

    await db.commit()
    await db.refresh(row)
    return row
