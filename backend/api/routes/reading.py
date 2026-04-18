"""GET /reading/{source_document_id} — current reading position and comprehension.
PATCH /reading/{source_document_id} — advance next_position.

A ``SourceProgressionRow`` must already exist for the (user, document) pair;
``POST /ingest`` creates one at ingestion time.

GET  returns the current state without side effects.
PATCH advances next_position by ``sentences_read`` (clamped to sentences_total),
      refreshes avg_comprehension from live UserKnowledgeRow mastery scores, and
      updates last_read_at.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db_session
from backend.models import (
    ParsedText,
    Sentence,
    SentenceObjectRow,
    SourceChunkRow,
    SourceProgressionRow,
    UserKnowledgeRow,
)
from backend.schemas.reading import AdvancePositionRequest, ReadingProgressResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["reading"])


async def _compute_avg_comprehension(
    db: AsyncSession,
    source_document_id: str,
    user_id: str,
) -> float:
    """Return the mean mastery_score across all canonical objects in this document.

    Traversal path:
        SourceChunkRow → ParsedText → Sentence → SentenceObjectRow → object_id
        → UserKnowledgeRow.mastery_score (for the given user_id)

    Returns 0.0 if the document has no objects or the user has no knowledge rows.
    """
    try:
        obj_result = await db.execute(
            select(SentenceObjectRow.object_id)
            .join(Sentence, Sentence.id == SentenceObjectRow.sentence_id)
            .join(ParsedText, ParsedText.id == Sentence.parsed_text_id)
            .join(SourceChunkRow, SourceChunkRow.parsed_text_id == ParsedText.id)
            .where(SourceChunkRow.source_document_id == source_document_id)
            .distinct()
        )
        object_ids = [row[0] for row in obj_result.all()]
    except Exception as exc:
        logger.warning(
            "avg_comprehension: object_id fetch failed for %s: %s",
            source_document_id, exc,
        )
        return 0.0

    if not object_ids:
        return 0.0

    try:
        uk_result = await db.execute(
            select(UserKnowledgeRow.mastery_score).where(
                UserKnowledgeRow.user_id == user_id,
                UserKnowledgeRow.object_id.in_(object_ids),
            )
        )
        scores = [row[0] for row in uk_result.all() if row[0] is not None]
    except Exception as exc:
        logger.warning(
            "avg_comprehension: mastery_score fetch failed for %s: %s",
            source_document_id, exc,
        )
        return 0.0

    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _to_response(row: SourceProgressionRow) -> ReadingProgressResponse:
    """Convert a SourceProgressionRow ORM object to the API response schema."""
    is_complete = row.sentences_total > 0 and row.next_position >= row.sentences_total
    return ReadingProgressResponse(
        source_document_id=row.source_document_id,
        next_position=row.next_position,
        sentences_total=row.sentences_total,
        completion_fraction=row.completion_fraction,
        avg_comprehension=row.avg_comprehension,
        last_read_at=row.last_read_at,
        is_complete=is_complete,
    )


@router.get("/reading/{source_document_id}", response_model=ReadingProgressResponse)
async def get_reading_progress(
    source_document_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> ReadingProgressResponse:
    """Return the current reading position for a source document.

    404 when no ``SourceProgressionRow`` exists for this (user, document) pair.
    A row is created by ``POST /ingest``; it does not exist for texts submitted
    via the legacy ``POST /parse`` endpoint.
    """
    try:
        result = await db.execute(
            select(SourceProgressionRow).where(
                SourceProgressionRow.user_id == current_user,
                SourceProgressionRow.source_document_id == source_document_id,
            )
        )
        row = result.scalar_one_or_none()
    except Exception as exc:
        logger.warning("DB error in GET /reading/%s: %s", source_document_id, exc)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No reading progression found for document '{source_document_id}'. "
                "Progression rows are created by POST /ingest."
            ),
        )

    return _to_response(row)


@router.patch("/reading/{source_document_id}", response_model=ReadingProgressResponse)
async def advance_reading_position(
    source_document_id: str,
    payload: AdvancePositionRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> ReadingProgressResponse:
    """Advance next_position by ``sentences_read`` (clamped to sentences_total).

    Also refreshes ``avg_comprehension`` from the current ``UserKnowledgeRow``
    mastery scores so the document-level comprehension view stays current as the
    user reviews vocabulary from this text.

    ``last_read_at`` is updated to the current UTC timestamp.
    """
    try:
        result = await db.execute(
            select(SourceProgressionRow).where(
                SourceProgressionRow.user_id == current_user,
                SourceProgressionRow.source_document_id == source_document_id,
            )
        )
        row = result.scalar_one_or_none()
    except Exception as exc:
        logger.warning("DB error in PATCH /reading/%s: %s", source_document_id, exc)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No reading progression found for document '{source_document_id}'. "
                "Progression rows are created by POST /ingest."
            ),
        )

    new_position = min(row.next_position + payload.sentences_read, row.sentences_total)
    row.next_position = new_position
    row.completion_fraction = (
        new_position / row.sentences_total if row.sentences_total > 0 else 0.0
    )
    row.last_read_at = datetime.now(UTC)

    # Refresh avg_comprehension — non-fatal: stale value beats a 503.
    try:
        row.avg_comprehension = await _compute_avg_comprehension(
            db, source_document_id, current_user
        )
    except Exception as exc:
        logger.warning(
            "avg_comprehension update skipped for %s: %s", source_document_id, exc
        )

    try:
        await db.commit()
        await db.refresh(row)
    except Exception as exc:
        logger.warning(
            "DB commit error in PATCH /reading/%s: %s", source_document_id, exc
        )
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    return _to_response(row)
