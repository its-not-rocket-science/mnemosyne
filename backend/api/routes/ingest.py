"""POST /ingest — rich text ingestion with source-document tracking.

Accepts text plus attribution/source metadata, runs the full parse pipeline,
and persists a ``SourceDocument`` + ``SourceChunk`` row alongside the
existing ``ParsedText`` / ``Sentence`` / ``CanonicalObject`` records.

The ``source_document_id`` in the response is the stable reference for
repeated-exposure tracking, recommendation, and reading-progression features.

``POST /parse`` remains unchanged for backward compatibility.  New clients
should prefer ``/ingest``.
"""
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db_session, get_plugin_registry
from backend.core.config import Settings, get_settings
from backend.core.limiter import limiter
from backend.ingestion.validator import detect_dominant_script, validate_ingest_text
from backend.models import CanonicalObjectRow
from backend.parsing.pipeline import PipelineResult, pipeline_cache_key, run_pipeline
from backend.parsing.plugin_loader import PluginRegistry
from backend.schemas.ingest import IngestRequest, IngestResponse
from backend.schemas.parse import CandidateObject
from backend.services.parse_persistence import persist_ingest

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
@limiter.limit(lambda: get_settings().rate_limit_parse)
async def ingest_text(
    request: Request,
    payload: IngestRequest,
    registry: PluginRegistry = Depends(get_plugin_registry),
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
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

    # ── 3. Shared pipeline: cache → NLP → enrich → resolve → lesson_store ────
    result: PipelineResult = await run_pipeline(
        text=normalized_text,
        language=payload.language,
        plugin=plugin,
        cache_key=pipeline_cache_key(normalized_text, payload.language),
    )

    sentences = result.sentences
    candidate_results = result.candidate_results
    uuid_to_candidate = result.uuid_to_candidate

    # ── 4. Cache-hit: lesson_store may be empty after a server restart ────────
    if result.cache_hit:
        cache_hit_ids = [lo.id for s in sentences for lo in s.learnable_objects]
        missing_ids = [oid for oid in cache_hit_ids if oid not in plugin.lesson_store]
        if missing_ids:
            try:
                result_q = await db.execute(
                    select(CanonicalObjectRow).where(CanonicalObjectRow.id.in_(missing_ids))
                )
                for row in result_q.scalars():
                    plugin.lesson_store[row.id] = CandidateObject(
                        type=row.type,
                        label=row.display_label,
                        canonical_form=row.canonical_form,
                        lesson_data=row.lesson_data or {},
                        confidence=row.confidence or 1.0,
                    )
            except Exception:
                logger.debug("lesson_store repopulation from DB failed on cache hit")

    # ── 5. Persist: source document + parse records ───────────────────────────
    source_document_id = str(uuid.uuid4())
    persist_exc: Exception | None = None
    try:
        await persist_ingest(
            db,
            language=payload.language,
            content_type=payload.content_type.value,
            normalized_text=normalized_text,
            script_hint=script_hint,
            source_document_id=source_document_id,
            candidate_results=candidate_results,
            sentences=sentences,
            uuid_to_candidate=uuid_to_candidate,
            title=payload.title,
            author=payload.author,
            source_url=payload.source_url,
            filename=payload.filename,
            user_id=current_user,
        )
    except Exception as exc:
        persist_exc = exc

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


