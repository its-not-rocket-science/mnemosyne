"""GET /sources — list user's saved source documents.
GET /sources/{source_id} — reconstruct lesson sentences from a saved source.
GET /corpus — browse all ingested source documents with filters and pagination.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, case, delete, func, or_, select
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
from backend.schemas.sources import (
    CorpusBrowseItem,
    CorpusBrowseResponse,
    CorpusLanguagesResponse,
    CorpusLanguageSummary,
    CorpusStats,
    SourceDetailResponse,
    SourceItem,
    SourceListResponse,
)

router = APIRouter(tags=["sources"])


@router.get("/sources", response_model=SourceListResponse)
async def list_sources(
    language: str | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> SourceListResponse:
    q = (
        select(SourceDocumentRow, SourceProgressionRow)
        .join(
            SourceProgressionRow,
            SourceProgressionRow.source_document_id == SourceDocumentRow.id,
        )
        .where(SourceProgressionRow.user_id == current_user)
        .order_by(SourceDocumentRow.created_at.desc())
    )
    if language:
        q = q.where(SourceDocumentRow.language == language)

    rows = (await db.execute(q)).all()

    return SourceListResponse(
        sources=[
            SourceItem(
                id=d.id,
                title=d.title,
                language=d.language,
                created_at=d.created_at,
                char_count=d.char_count,
                next_position=p.next_position or 0,
                sentences_total=p.sentences_total or 0,
                completion_fraction=p.completion_fraction or 0.0,
                is_complete=bool(
                    p.sentences_total and p.next_position >= p.sentences_total
                ),
            )
            for d, p in rows
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


@router.get("/corpus/languages", response_model=CorpusLanguagesResponse)
async def list_corpus_languages(
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> CorpusLanguagesResponse:
    """Return each language present in the corpus with its document count."""
    stmt = (
        select(SourceDocumentRow.language, func.count().label("count"))
        .group_by(SourceDocumentRow.language)
        .order_by(SourceDocumentRow.language)
    )
    rows = (await db.execute(stmt)).all()
    return CorpusLanguagesResponse(
        languages=[
            CorpusLanguageSummary(language=row.language, count=row.count)
            for row in rows
        ]
    )


@router.get("/corpus/stats", response_model=CorpusStats)
async def get_corpus_stats(
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> CorpusStats:
    """Return per-user reading-progress counts across the entire corpus."""
    prog_join = and_(
        SourceProgressionRow.source_document_id == SourceDocumentRow.id,
        SourceProgressionRow.user_id == current_user,
    )
    stmt = (
        select(
            func.count().label("total"),
            func.sum(case(
                (or_(
                    SourceProgressionRow.user_id == None,   # noqa: E711
                    SourceProgressionRow.next_position == 0,
                ), 1),
                else_=0,
            )).label("not_started"),
            func.sum(case(
                (and_(
                    SourceProgressionRow.next_position > 0,
                    or_(
                        SourceProgressionRow.sentences_total == 0,
                        SourceProgressionRow.next_position < SourceProgressionRow.sentences_total,
                    ),
                ), 1),
                else_=0,
            )).label("in_progress"),
            func.sum(case(
                (and_(
                    SourceProgressionRow.sentences_total > 0,
                    SourceProgressionRow.next_position >= SourceProgressionRow.sentences_total,
                ), 1),
                else_=0,
            )).label("complete"),
        )
        .select_from(SourceDocumentRow)
        .outerjoin(SourceProgressionRow, prog_join)
    )
    row = (await db.execute(stmt)).one()
    return CorpusStats(
        total=row.total or 0,
        not_started=row.not_started or 0,
        in_progress=row.in_progress or 0,
        complete=row.complete or 0,
    )


@router.delete("/corpus/{doc_id}/progress", status_code=204)
async def reset_corpus_progress(
    doc_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> Response:
    """Delete the user's reading-progress record for a corpus document."""
    await db.execute(
        delete(SourceProgressionRow).where(
            SourceProgressionRow.source_document_id == doc_id,
            SourceProgressionRow.user_id == current_user,
        )
    )
    await db.commit()
    return Response(status_code=204)


_VALID_CORPUS_SORT = frozenset({"recent", "in_progress", "not_started", "complete"})


@router.get("/corpus", response_model=CorpusBrowseResponse)
async def browse_corpus(
    language: str | None = None,
    content_type: str | None = None,
    q: str | None = None,
    sort: str = Query(default="recent"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> CorpusBrowseResponse:
    """Browse all ingested source documents with optional filters and pagination.

    ``sort`` controls ordering and optional progress filtering:

    * ``recent`` (default) — all documents, newest first.
    * ``in_progress`` — only documents the user has started but not finished,
      ordered by descending completion fraction.
    * ``not_started`` — only documents the user has never opened, newest first.
    * ``complete`` — only documents the user has fully read, newest first.
    """
    if sort not in _VALID_CORPUS_SORT:
        sort = "recent"

    # All queries outerjoin progression so progress conditions are available.
    prog_join = and_(
        SourceProgressionRow.source_document_id == SourceDocumentRow.id,
        SourceProgressionRow.user_id == current_user,
    )
    joined = (
        select(SourceDocumentRow, SourceProgressionRow)
        .outerjoin(SourceProgressionRow, prog_join)
    )

    # Document-level filter conditions
    conditions: list = []
    if language:
        conditions.append(SourceDocumentRow.language == language)
    if content_type:
        conditions.append(SourceDocumentRow.content_type == content_type)
    if q:
        conditions.append(SourceDocumentRow.title.ilike(f"%{q}%"))

    # Progress filter + sort order
    if sort == "in_progress":
        conditions.append(SourceProgressionRow.next_position > 0)
        conditions.append(
            or_(
                SourceProgressionRow.sentences_total == 0,
                SourceProgressionRow.next_position < SourceProgressionRow.sentences_total,
            )
        )
        order_clause = SourceProgressionRow.completion_fraction.desc()
    elif sort == "not_started":
        conditions.append(
            or_(
                SourceProgressionRow.user_id == None,   # noqa: E711 (SA null check)
                SourceProgressionRow.next_position == 0,
            )
        )
        order_clause = SourceDocumentRow.created_at.desc()
    elif sort == "complete":
        conditions.append(SourceProgressionRow.sentences_total > 0)
        conditions.append(
            SourceProgressionRow.next_position >= SourceProgressionRow.sentences_total
        )
        order_clause = SourceDocumentRow.created_at.desc()
    else:  # recent
        order_clause = SourceDocumentRow.created_at.desc()

    base_filtered = joined.where(*conditions)
    total = await db.scalar(
        select(func.count()).select_from(base_filtered.subquery())
    ) or 0

    data_stmt = (
        base_filtered
        .order_by(order_clause)
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(data_stmt)).all()

    items = [
        CorpusBrowseItem(
            id=doc.id,
            title=doc.title,
            language=doc.language,
            content_type=doc.content_type,
            author=doc.author,
            char_count=doc.char_count,
            created_at=doc.created_at,
            next_position=prog.next_position if prog else 0,
            sentences_total=prog.sentences_total if prog else 0,
            completion_fraction=prog.completion_fraction if prog else 0.0,
            started=bool(prog and prog.next_position and prog.next_position > 0),
            is_complete=bool(
                prog
                and prog.sentences_total
                and prog.next_position
                and prog.next_position >= prog.sentences_total
            ),
        )
        for doc, prog in rows
    ]
    return CorpusBrowseResponse(items=items, total=total)
