"""GET /sources — list user's saved source documents.
GET /sources/{source_id} — reconstruct lesson sentences from a saved source.
GET /corpus — browse all ingested source documents with filters and pagination.
POST /corpus/import-url — fetch a URL server-side, extract text, and ingest it.
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import and_, case, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db_session, get_plugin_registry
from backend.core.config import get_settings
from backend.ingestion.validator import detect_dominant_script, validate_ingest_text
from backend.models import (
    CanonicalObjectRow,
    CorpusDocumentNoteRow,
    CorpusDocumentTagRow,
    Sentence,
    SentenceObjectRow,
    SentenceReviewItemRow,
    SourceChunkRow,
    SourceDocumentRow,
    SourceProgressionRow,
    UserKnowledgeRow,
    UserSentenceReviewRow,
)
from backend.parsing.pipeline import PipelineResult, pipeline_cache_key, run_pipeline
from backend.parsing.plugin_loader import PluginRegistry
from backend.schemas.parse import LearnableObject, SentenceResult
from backend.schemas.sources import (
    CorpusBrowseItem,
    CorpusBrowseResponse,
    CorpusLanguagesResponse,
    CorpusLanguageSummary,
    CorpusStats,
    CorpusStudyResult,
    CorpusTagsResponse,
    NoteResponse,
    NoteUpsertRequest,
    SourceDetailResponse,
    SourceItem,
    SourceListResponse,
    TagAddRequest,
    UrlImportRequest,
    UrlImportResponse,
)
from backend.services.parse_persistence import persist_ingest
from backend.srs.sentence_miner import mine_sentence

_URL_IMPORT_MAX_CHARS = 50_000
_URL_FETCH_TIMEOUT    = 15.0
_URL_FETCH_MAX_BYTES  = 5 * 1024 * 1024  # 5 MB raw HTML cap

logger = logging.getLogger(__name__)
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


@router.get("/corpus/all-tags", response_model=CorpusTagsResponse)
async def list_all_corpus_tags(
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> CorpusTagsResponse:
    """Return all unique tags the user has applied across the corpus."""
    rows = await db.execute(
        select(CorpusDocumentTagRow.tag)
        .where(CorpusDocumentTagRow.user_id == current_user)
        .group_by(CorpusDocumentTagRow.tag)
        .order_by(CorpusDocumentTagRow.tag)
    )
    return CorpusTagsResponse(tags=[r.tag for r in rows.all()])


@router.post("/corpus/import-url", response_model=UrlImportResponse, status_code=201)
async def import_corpus_url(
    payload: UrlImportRequest,
    registry: PluginRegistry = Depends(get_plugin_registry),
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> UrlImportResponse:
    """Fetch a URL, extract its text, and ingest it as a corpus document."""
    # ── 0. URL dedup ──────────────────────────────────────────────────────────
    url_dup = await db.execute(
        select(SourceDocumentRow.id, SourceDocumentRow.title)
        .where(SourceDocumentRow.source_url == payload.url)
    )
    url_dup_row = url_dup.first()
    if url_dup_row:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "already_imported",
                "source_document_id": url_dup_row.id,
                "title": url_dup_row.title,
            },
        )

    # ── 1. Fetch ──────────────────────────────────────────────────────────────
    headers = {"User-Agent": "Mnemosyne/1.0 (+educational-language-tool)"}
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=_URL_FETCH_TIMEOUT) as client:
            resp = await client.get(payload.url, headers=headers)
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Remote server returned {exc.response.status_code}.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Could not fetch that URL.") from exc

    content_type_header = resp.headers.get("content-type", "")
    if "html" not in content_type_header and "text" not in content_type_header:
        raise HTTPException(status_code=422, detail="URL does not point to an HTML or text resource.")

    raw = resp.text[:_URL_FETCH_MAX_BYTES]

    # ── 2. Extract text + title ───────────────────────────────────────────────
    extracted_title, text = _extract_html_text(raw)
    title = payload.title or extracted_title

    if not text.strip():
        raise HTTPException(status_code=422, detail="No readable text found at that URL.")

    truncated = len(text) > _URL_IMPORT_MAX_CHARS
    if truncated:
        text = text[:_URL_IMPORT_MAX_CHARS]

    # ── 3. Validate + pipeline ────────────────────────────────────────────────
    try:
        normalized_text, _ = validate_ingest_text(text, payload.language)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        plugin = registry.get(payload.language)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    script_hint = detect_dominant_script(normalized_text)

    # ── 3b. Content-hash dedup ────────────────────────────────────────────────
    content_hash = hashlib.sha256(normalized_text.encode()).hexdigest()
    hash_dup = await db.execute(
        select(SourceDocumentRow.id, SourceDocumentRow.title)
        .where(SourceDocumentRow.content_hash == content_hash)
    )
    hash_dup_row = hash_dup.first()
    if hash_dup_row:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "duplicate_content",
                "source_document_id": hash_dup_row.id,
                "title": hash_dup_row.title,
            },
        )

    result: PipelineResult = await run_pipeline(
        text=normalized_text,
        language=payload.language,
        plugin=plugin,
        cache_key=pipeline_cache_key(normalized_text, payload.language),
    )

    # ── 4. Persist ────────────────────────────────────────────────────────────
    source_document_id = str(uuid.uuid4())
    try:
        await persist_ingest(
            db,
            language=payload.language,
            content_type="article",
            normalized_text=normalized_text,
            script_hint=script_hint,
            source_document_id=source_document_id,
            candidate_results=result.candidate_results,
            sentences=result.sentences,
            uuid_to_candidate=result.uuid_to_candidate,
            title=title,
            source_url=payload.url,
            content_hash=content_hash,
            user_id=current_user,
        )
    except Exception as exc:
        logger.warning("DB persistence failed for /corpus/import-url", exc_info=exc)
        raise HTTPException(status_code=500, detail="Failed to save imported document.") from exc

    return UrlImportResponse(
        source_document_id=source_document_id,
        title=title,
        char_count=len(normalized_text),
        truncated=truncated,
    )


def _extract_html_text(html: str) -> tuple[str | None, str]:
    """Return (title, body_text) extracted from raw HTML."""
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title: str | None = None
    title_tag = soup.find("title")
    if title_tag:
        title = re.sub(r"\s+", " ", title_tag.get_text(" ", strip=True)).strip() or None

    # Remove noise tags
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript", "form"]):
        tag.decompose()

    # Best-effort main content
    container = soup.find("article") or soup.find("main") or soup.find("body") or soup

    paragraphs: list[str] = []
    for elem in container.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "td"]):
        t = re.sub(r"\s+", " ", elem.get_text(" ", strip=True))
        if t:
            paragraphs.append(t)

    text = "\n\n".join(paragraphs) if paragraphs else re.sub(r"\n{3,}", "\n\n", container.get_text("\n"))
    return title, text


@router.put("/corpus/{doc_id}/note", response_model=NoteResponse)
async def upsert_doc_note(
    doc_id: str,
    payload: NoteUpsertRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> NoteResponse:
    """Create or replace the user's note for a corpus document."""
    await db.execute(
        delete(CorpusDocumentNoteRow).where(
            CorpusDocumentNoteRow.user_id == current_user,
            CorpusDocumentNoteRow.source_document_id == doc_id,
        )
    )
    db.add(CorpusDocumentNoteRow(
        user_id=current_user,
        source_document_id=doc_id,
        note=payload.text,
        updated_at=datetime.now(UTC),
    ))
    await db.commit()
    return NoteResponse(text=payload.text)


@router.delete("/corpus/{doc_id}/note", status_code=204)
async def delete_doc_note(
    doc_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> Response:
    """Delete the user's note for a corpus document."""
    await db.execute(
        delete(CorpusDocumentNoteRow).where(
            CorpusDocumentNoteRow.user_id == current_user,
            CorpusDocumentNoteRow.source_document_id == doc_id,
        )
    )
    await db.commit()
    return Response(status_code=204)


@router.get("/corpus/{doc_id}/tags", response_model=CorpusTagsResponse)
async def get_doc_tags(
    doc_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> CorpusTagsResponse:
    rows = await db.execute(
        select(CorpusDocumentTagRow.tag)
        .where(
            CorpusDocumentTagRow.user_id == current_user,
            CorpusDocumentTagRow.source_document_id == doc_id,
        )
        .order_by(CorpusDocumentTagRow.tag)
    )
    return CorpusTagsResponse(tags=[r.tag for r in rows.all()])


@router.post("/corpus/{doc_id}/tags", status_code=201, response_model=CorpusTagsResponse)
async def add_doc_tag(
    doc_id: str,
    body: TagAddRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> CorpusTagsResponse:
    """Add a tag to a corpus document (idempotent)."""
    existing = await db.scalar(
        select(CorpusDocumentTagRow).where(
            CorpusDocumentTagRow.user_id == current_user,
            CorpusDocumentTagRow.source_document_id == doc_id,
            CorpusDocumentTagRow.tag == body.tag,
        )
    )
    if not existing:
        db.add(CorpusDocumentTagRow(
            user_id=current_user,
            source_document_id=doc_id,
            tag=body.tag,
        ))
        await db.commit()
    rows = await db.execute(
        select(CorpusDocumentTagRow.tag)
        .where(
            CorpusDocumentTagRow.user_id == current_user,
            CorpusDocumentTagRow.source_document_id == doc_id,
        )
        .order_by(CorpusDocumentTagRow.tag)
    )
    return CorpusTagsResponse(tags=[r.tag for r in rows.all()])


@router.delete("/corpus/{doc_id}/tags/{tag}", status_code=204)
async def remove_doc_tag(
    doc_id: str,
    tag: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> Response:
    await db.execute(
        delete(CorpusDocumentTagRow).where(
            CorpusDocumentTagRow.user_id == current_user,
            CorpusDocumentTagRow.source_document_id == doc_id,
            CorpusDocumentTagRow.tag == tag,
        )
    )
    await db.commit()
    return Response(status_code=204)


@router.post("/corpus/{doc_id}/study", response_model=CorpusStudyResult)
async def study_corpus_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> CorpusStudyResult:
    """Mine a corpus document for sentence-level review items.

    Equivalent to running ``/review/sentence-items/mine`` but scoped to a
    single corpus document.  Items already mined from the same sentence are
    skipped (idempotent).
    """
    doc = await db.scalar(
        select(SourceDocumentRow).where(SourceDocumentRow.id == doc_id)
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk_rows = (await db.execute(
        select(SourceChunkRow)
        .where(SourceChunkRow.source_document_id == doc_id)
        .order_by(SourceChunkRow.chunk_index)
    )).scalars().all()

    if not chunk_rows:
        return CorpusStudyResult(mined=0, skipped_duplicate=0, sentences_processed=0)

    now = datetime.now(UTC)
    mined_count = 0
    skip_count = 0
    sent_count = 0

    for chunk in chunk_rows:
        sentences = (await db.execute(
            select(Sentence)
            .where(Sentence.parsed_text_id == chunk.parsed_text_id)
            .order_by(Sentence.position)
        )).scalars().all()

        for sentence in sentences:
            sent_count += 1
            obj_rows = (await db.execute(
                select(CanonicalObjectRow)
                .join(SentenceObjectRow, CanonicalObjectRow.id == SentenceObjectRow.object_id)
                .where(SentenceObjectRow.sentence_id == sentence.id)
            )).scalars().all()

            obj_dicts = [
                {
                    "id": o.id,
                    "type": o.type,
                    "display_label": o.display_label,
                    "surface_forms": o.surface_forms or [],
                    "lesson_data": o.lesson_data or {},
                    "confidence": o.confidence or 0.0,
                }
                for o in obj_rows
            ]

            specs = mine_sentence(sentence.id, sentence.text, doc.language, obj_dicts)

            for spec in specs:
                existing = (await db.execute(
                    select(SentenceReviewItemRow.id).where(
                        SentenceReviewItemRow.sentence_id == spec.sentence_id,
                        SentenceReviewItemRow.item_type == spec.item_type,
                        SentenceReviewItemRow.target_span == spec.target_span,
                    )
                )).scalar_one_or_none()

                if existing:
                    skip_count += 1
                    continue

                item_row = SentenceReviewItemRow(
                    sentence_id=spec.sentence_id,
                    language=spec.language,
                    item_type=spec.item_type,
                    prompt=spec.prompt,
                    target_span=spec.target_span,
                    answer=spec.answer,
                    distractors=spec.distractors,
                    hint=spec.hint,
                    grammar_concept=spec.grammar_concept,
                    cefr_level=spec.cefr_level,
                    difficulty_score=spec.difficulty_score,
                    target_object_ids=spec.target_object_ids,
                )
                db.add(item_row)
                try:
                    await db.flush()
                except Exception:
                    await db.rollback()
                    logger.warning("Flush failed for study item, skipping", exc_info=True)
                    continue

                db.add(UserSentenceReviewRow(
                    user_id=current_user,
                    item_id=item_row.id,
                    due_at=now,
                ))
                mined_count += 1

    try:
        await db.commit()
    except Exception:
        logger.warning("Commit failed during corpus study mining", exc_info=True)
        await db.rollback()

    return CorpusStudyResult(
        mined=mined_count,
        skipped_duplicate=skip_count,
        sentences_processed=sent_count,
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
    tag: str | None = None,
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
    if tag:
        tag_subq = (
            select(CorpusDocumentTagRow.source_document_id)
            .where(
                CorpusDocumentTagRow.user_id == current_user,
                CorpusDocumentTagRow.tag == tag,
            )
        )
        conditions.append(SourceDocumentRow.id.in_(tag_subq))

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

    # Fetch tags, notes, and vocab density for all returned docs in one batch each.
    doc_ids = [doc.id for doc, _ in rows]
    tags_by_doc: dict[str, list[str]] = {}
    notes_by_doc: dict[str, str] = {}
    density_by_doc: dict[str, float] = {}

    if doc_ids:
        tag_rows = (await db.execute(
            select(CorpusDocumentTagRow.source_document_id, CorpusDocumentTagRow.tag)
            .where(
                CorpusDocumentTagRow.user_id == current_user,
                CorpusDocumentTagRow.source_document_id.in_(doc_ids),
            )
            .order_by(CorpusDocumentTagRow.tag)
        )).all()
        for doc_id_val, tag_val in tag_rows:
            tags_by_doc.setdefault(doc_id_val, []).append(tag_val)

        note_rows = (await db.execute(
            select(CorpusDocumentNoteRow.source_document_id, CorpusDocumentNoteRow.note)
            .where(
                CorpusDocumentNoteRow.user_id == current_user,
                CorpusDocumentNoteRow.source_document_id.in_(doc_ids),
            )
        )).all()
        notes_by_doc = {r.source_document_id: r.note for r in note_rows}

        density_rows = (await db.execute(
            select(
                SourceChunkRow.source_document_id,
                func.count(func.distinct(SentenceObjectRow.object_id)).label("total"),
                func.count(func.distinct(SentenceObjectRow.object_id)).filter(
                    UserKnowledgeRow.object_id.is_not(None)
                ).label("known"),
            )
            .select_from(SourceChunkRow)
            .join(Sentence, Sentence.parsed_text_id == SourceChunkRow.parsed_text_id)
            .join(SentenceObjectRow, SentenceObjectRow.sentence_id == Sentence.id)
            .outerjoin(UserKnowledgeRow, and_(
                UserKnowledgeRow.object_id == SentenceObjectRow.object_id,
                UserKnowledgeRow.user_id == current_user,
            ))
            .where(SourceChunkRow.source_document_id.in_(doc_ids))
            .group_by(SourceChunkRow.source_document_id)
        )).all()
        density_by_doc = {
            r.source_document_id: round(r.known / r.total, 3) if r.total > 0 else 0.0
            for r in density_rows
        }

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
            tags=tags_by_doc.get(doc.id, []),
            note=notes_by_doc.get(doc.id),
            vocab_density=density_by_doc.get(doc.id, 0.0),
        )
        for doc, prog in rows
    ]
    return CorpusBrowseResponse(items=items, total=total)
