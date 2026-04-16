"""POST /ingest — rich text ingestion with source-document tracking.

Accepts text plus attribution/source metadata, runs the full parse pipeline,
and persists a ``SourceDocument`` + ``SourceChunk`` row alongside the
existing ``ParsedText`` / ``Sentence`` / ``CanonicalObject`` records.

The ``source_document_id`` in the response is the stable reference for
repeated-exposure tracking, recommendation, and reading-progression features.

``POST /parse`` remains unchanged for backward compatibility.  New clients
should prefer ``/ingest``.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_db_session, get_plugin_registry
from backend.core.cache import get_json, set_json
from backend.core.config import Settings, get_settings
from backend.ingestion.validator import detect_dominant_script, validate_ingest_text
from backend.models import (
    CanonicalObjectRow,
    ObjectRelationRow,
    ParsedText,
    Sentence,
    SentenceObjectRow,
    SourceChunkRow,
    SourceDocumentRow,
    UserKnowledgeRow,
)
from backend.parsing.canonical import canonical_object_id
from backend.parsing.plugin_loader import PluginRegistry
from backend.schemas.ingest import IngestRequest, IngestResponse
from backend.schemas.parse import (
    CandidateObject,
    CandidateSentenceResult,
    LearnableObject,
    SentenceResult,
)
from backend.srs.knowledge import DEFAULT_USER_ID

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_text(
    payload: IngestRequest,
    registry: PluginRegistry = Depends(get_plugin_registry),
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> IngestResponse:
    # ── 0. Size guard — reject before any NLP work ───────────────────────────
    if len(payload.text) > settings.max_parse_chars:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Text is {len(payload.text):,} characters; "
                f"the limit is {settings.max_parse_chars:,}. "
                "Split the text into smaller passages and submit each separately."
            ),
        )

    # ── 1. Validate and normalize text ───────────────────────────────────────
    try:
        normalized_text, warnings = validate_ingest_text(payload.text, payload.language)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    script_hint = detect_dominant_script(normalized_text)

    # ── 2. Plugin lookup ──────────────────────────────────────────────────────
    try:
        plugin = registry.get(payload.language)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    t0 = time.perf_counter()

    # ── 3. Cache check — keyed on normalized text so re-submits are fast ─────
    cache_key = _cache_key(normalized_text, payload.language)
    cached_sentences: list[SentenceResult] | None = None
    try:
        cached = await get_json(cache_key)
        if cached is not None:
            from backend.schemas.parse import ParseResponse
            parsed_cached = ParseResponse.model_validate(cached)
            cached_sentences = parsed_cached.sentences
            logger.debug(
                "ingest cache=HIT lang=%s chars=%d elapsed_ms=%.1f",
                payload.language, len(normalized_text),
                (time.perf_counter() - t0) * 1000,
            )
    except Exception:
        pass  # Redis unavailable — continue without cache

    # ── 4. NLP analysis (skip when cache hit) ────────────────────────────────
    uuid_to_candidate: dict[str, tuple[str, CandidateObject]] = {}
    candidate_results: list[CandidateSentenceResult] = []

    if cached_sentences is None:
        t_nlp = time.perf_counter()
        candidate_results = plugin.analyze_text(normalized_text)
        logger.debug(
            "ingest nlp_ms=%.1f sentences=%d",
            (time.perf_counter() - t_nlp) * 1000, len(candidate_results),
        )

        sentences: list[SentenceResult] = []
        for cand_result in candidate_results:
            resolved: list[LearnableObject] = []
            for cand in cand_result.candidates:
                obj_id = canonical_object_id(payload.language, cand.type, cand.canonical_form)
                lo = LearnableObject(
                    id=obj_id,
                    language=payload.language,
                    type=cand.type,
                    label=cand.label,
                    lesson_data=cand.lesson_data,
                    confidence=cand.confidence,
                )
                resolved.append(lo)
                uuid_to_candidate[obj_id] = (cand.canonical_form, cand)
            sentences.append(SentenceResult(text=cand_result.text, learnable_objects=resolved))
    else:
        sentences = cached_sentences

    # ── 5. Populate plugin lesson_store for DB-unavailable fallback ───────────
    for obj_id, (_, cand) in uuid_to_candidate.items():
        plugin.lesson_store[obj_id] = cand

    # ── 6. Persist: source document + parse records ───────────────────────────
    source_document_id = str(uuid.uuid4())
    persist_exc: Exception | None = None
    try:
        await _persist_ingest(
            db=db,
            payload=payload,
            normalized_text=normalized_text,
            script_hint=script_hint,
            source_document_id=source_document_id,
            candidate_results=candidate_results,
            sentences=sentences,
            uuid_to_candidate=uuid_to_candidate,
        )
    except Exception as exc:
        persist_exc = exc

    # ── 7. Cache write (background, non-fatal) ────────────────────────────────
    if cached_sentences is None:
        from backend.schemas.parse import ParseResponse
        response_json = ParseResponse(sentences=sentences).model_dump(mode="json")
        cache_task = asyncio.ensure_future(set_json(cache_key, response_json))
        try:
            await cache_task
        except Exception:
            pass

    if persist_exc is not None:
        logger.warning("DB persistence failed for /ingest", exc_info=persist_exc)

    logger.info(
        "ingest lang=%s content_type=%s chars=%d sentences=%d objects=%d elapsed_ms=%.1f",
        payload.language,
        payload.content_type.value,
        len(normalized_text),
        len(sentences),
        len(uuid_to_candidate),
        (time.perf_counter() - t0) * 1000,
    )

    return IngestResponse(
        sentences=sentences,
        source_document_id=source_document_id,
        warnings=warnings,
    )


async def _persist_ingest(
    db: AsyncSession,
    payload: IngestRequest,
    normalized_text: str,
    script_hint: str | None,
    source_document_id: str,
    candidate_results: list[CandidateSentenceResult],
    sentences: list[SentenceResult],
    uuid_to_candidate: dict[str, tuple[str, CandidateObject]],
) -> None:
    """Write all rows for one ingest call.

    Order of operations (FK constraints require this sequence):
      1. SourceDocument
      2. ParsedText
      3. Sentences
      4. CanonicalObjects (upsert)
      5. UserKnowledge (seed / update last_seen)
      6. SentenceObjects (join table)
      7. ObjectRelations (upsert)
      8. SourceChunk (links SourceDocument → ParsedText)
    """
    now = datetime.now(UTC)

    # 1. Source document — metadata about where this text came from.
    source_doc = SourceDocumentRow(
        id=source_document_id,
        language=payload.language,
        content_type=payload.content_type.value,
        title=payload.title,
        author=payload.author,
        source_url=payload.source_url,
        filename=payload.filename,
        char_count=len(normalized_text),
        script_hint=script_hint,
    )
    db.add(source_doc)
    await db.flush()

    # 2. ParsedText — audit row for this parse run.
    parsed = ParsedText(
        language=payload.language,
        source_text=normalized_text,
        source_url=payload.source_url,
    )
    db.add(parsed)
    await db.flush()  # materialise parsed.id before FK references

    # 3. Sentence rows.
    sentence_rows: list[Sentence] = []
    for pos, result in enumerate(sentences):
        row = Sentence(parsed_text_id=parsed.id, position=pos, text=result.text)
        db.add(row)
        sentence_rows.append(row)
    await db.flush()

    # 4. Upsert canonical objects.
    all_ids = list(uuid_to_candidate.keys())
    if all_ids:
        result_q = await db.execute(
            select(CanonicalObjectRow).where(CanonicalObjectRow.id.in_(all_ids))
        )
        existing: dict[str, CanonicalObjectRow] = {
            row.id: row for row in result_q.scalars()
        }
    else:
        existing = {}

    for obj_id, (canonical_form, cand) in uuid_to_candidate.items():
        if obj_id in existing:
            row = existing[obj_id]
            row.display_label = cand.label
            row.lesson_data = cand.lesson_data
            row.confidence = cand.confidence
            if cand.surface_form:
                current = list(row.surface_forms or [])
                if cand.surface_form not in current:
                    row.surface_forms = current + [cand.surface_form]
        else:
            db.add(CanonicalObjectRow(
                id=obj_id,
                language=payload.language,
                type=cand.type,
                canonical_form=canonical_form,
                display_label=cand.label,
                surface_forms=[cand.surface_form] if cand.surface_form else [],
                lesson_data=cand.lesson_data,
                confidence=cand.confidence,
            ))
    await db.flush()

    # 5. Seed user knowledge for new objects; update last_seen for existing.
    if all_ids:
        uk_result = await db.execute(
            select(UserKnowledgeRow).where(
                UserKnowledgeRow.user_id == DEFAULT_USER_ID,
                UserKnowledgeRow.object_id.in_(all_ids),
            )
        )
        existing_uk: dict[str, UserKnowledgeRow] = {
            row.object_id: row for row in uk_result.scalars()
        }
        for obj_id in all_ids:
            if obj_id in existing_uk:
                existing_uk[obj_id].last_seen = now
            else:
                db.add(UserKnowledgeRow(
                    user_id=DEFAULT_USER_ID,
                    object_id=obj_id,
                    language=payload.language,
                    fsrs_state=None,
                    mastery_score=0.0,
                    first_seen=now,
                    last_seen=now,
                    total_reviews=0,
                    due_at=now,
                ))

    # 6. Sentence–object join rows.
    for sent_row, sent_result in zip(sentence_rows, sentences):
        for pos, lo in enumerate(sent_result.learnable_objects):
            db.add(SentenceObjectRow(
                sentence_id=sent_row.id,
                object_id=lo.id,
                position=pos,
            ))

    # 7. Upsert object relations.
    desired_relations: list[tuple[str, str, str]] = []
    for cand_result in candidate_results:
        for cand in cand_result.candidates:
            src_id = canonical_object_id(payload.language, cand.type, cand.canonical_form)
            for hint in cand.relation_hints:
                tgt_id = canonical_object_id(
                    payload.language, hint.target_type, hint.target_canonical_form
                )
                if tgt_id not in uuid_to_candidate:
                    continue
                desired_relations.append((src_id, tgt_id, hint.relation_type))

    if desired_relations:
        src_ids = list({r[0] for r in desired_relations})
        rel_q = await db.execute(
            select(ObjectRelationRow).where(ObjectRelationRow.source_id.in_(src_ids))
        )
        existing_rels: set[tuple[str, str, str]] = {
            (r.source_id, r.target_id, r.relation_type) for r in rel_q.scalars()
        }
        for triple in desired_relations:
            if triple not in existing_rels:
                db.add(ObjectRelationRow(
                    source_id=triple[0],
                    target_id=triple[1],
                    relation_type=triple[2],
                ))

    # 8. SourceChunk — link the source document to this parse run.
    db.add(SourceChunkRow(
        source_document_id=source_document_id,
        parsed_text_id=parsed.id,
        chunk_index=0,
        char_start=0,
        char_end=len(normalized_text),
    ))

    await db.commit()


def _cache_key(text: str, language: str) -> str:
    digest = hashlib.sha256(f"{language}:{text}".encode("utf-8")).hexdigest()
    return f"parse:{digest}"
