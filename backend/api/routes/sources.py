"""GET /sources — list user's saved source documents.
GET /sources/{source_id} — reconstruct lesson sentences from a saved source.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db_session
from backend.models import (
    CanonicalObjectRow,
    Sentence,
    SentenceObjectRow,
    SourceChunkRow,
    SourceDocumentRow,
    SourceProgressionRow,
)
from backend.schemas.parse import LearnableObject, SentenceResult
from backend.schemas.sources import SourceDetailResponse, SourceItem, SourceListResponse

router = APIRouter(tags=["sources"])


@router.get("/sources", response_model=SourceListResponse)
async def list_sources(
    language: str | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> SourceListResponse:
    q = (
        select(SourceDocumentRow)
        .join(
            SourceProgressionRow,
            SourceProgressionRow.source_document_id == SourceDocumentRow.id,
        )
        .where(SourceProgressionRow.user_id == current_user)
        .order_by(SourceDocumentRow.created_at.desc())
    )
    if language:
        q = q.where(SourceDocumentRow.language == language)

    result = await db.execute(q)
    docs = result.scalars().all()

    return SourceListResponse(
        sources=[
            SourceItem(
                id=d.id,
                title=d.title,
                language=d.language,
                created_at=d.created_at,
                char_count=d.char_count,
            )
            for d in docs
        ]
    )


@router.get("/sources/{source_id}", response_model=SourceDetailResponse)
async def get_source(
    source_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> SourceDetailResponse:
    prog = await db.execute(
        select(SourceProgressionRow).where(
            SourceProgressionRow.user_id == current_user,
            SourceProgressionRow.source_document_id == source_id,
        )
    )
    if not prog.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Source not found")

    doc_q = await db.execute(
        select(SourceDocumentRow).where(SourceDocumentRow.id == source_id)
    )
    doc = doc_q.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Source not found")

    chunk_q = await db.execute(
        select(SourceChunkRow)
        .where(SourceChunkRow.source_document_id == source_id)
        .order_by(SourceChunkRow.chunk_index)
    )
    chunks = chunk_q.scalars().all()

    sentences: list[SentenceResult] = []
    for chunk in chunks:
        sent_q = await db.execute(
            select(Sentence)
            .where(Sentence.parsed_text_id == chunk.parsed_text_id)
            .order_by(Sentence.position)
        )
        for sent_row in sent_q.scalars().all():
            obj_q = await db.execute(
                select(SentenceObjectRow, CanonicalObjectRow)
                .join(
                    CanonicalObjectRow,
                    SentenceObjectRow.object_id == CanonicalObjectRow.id,
                )
                .where(SentenceObjectRow.sentence_id == sent_row.id)
                .order_by(SentenceObjectRow.position)
            )
            learnable_objects = [
                LearnableObject(
                    id=co.id,
                    language=co.language,
                    type=co.type,
                    label=co.display_label,
                    lesson_data=co.lesson_data or {},
                    confidence=co.confidence or 1.0,
                )
                for _, co in obj_q.all()
            ]
            sentences.append(
                SentenceResult(text=sent_row.text, learnable_objects=learnable_objects)
            )

    return SourceDetailResponse(
        id=doc.id,
        title=doc.title,
        language=doc.language,
        sentences=sentences,
    )
