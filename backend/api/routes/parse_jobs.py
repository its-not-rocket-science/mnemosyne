"""POST /parse/jobs — async large-text parse endpoint.

Accepts texts up to ``MAX_JOB_CHARS`` characters (default 100 000).  The NLP
pipeline runs in a thread-pool executor so the event loop is not blocked.
Progress is broadcast as Server-Sent Events on ``GET /parse/jobs/{id}/events``.

Endpoints
─────────
  POST /parse/jobs                  Submit a text; returns job_id immediately.
  GET  /parse/jobs/{id}             Poll job status / result.
  GET  /parse/jobs/{id}/events      SSE stream of progress events.

Multi-worker note
─────────────────
The job store is in-process.  In a multi-worker deployment clients must be
directed to the same worker for the lifetime of the job (sticky sessions or a
load balancer routing on the job-id cookie).  Replacing ``job_store`` with a
Redis-backed implementation would remove this constraint.
"""

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.api.dependencies import get_current_user, get_plugin_registry
from backend.core.config import Settings, get_settings
from backend.core.database import get_session_factory
from backend.core.jobs import ParseJob, job_store
from backend.core.limiter import limiter
from backend.parsing.canonical import canonical_object_id
from backend.parsing.plugin_loader import PluginRegistry
from backend.schemas.jobs import ParseJobCreated, ParseJobStatus
from backend.schemas.parse import (
    CandidateObject,
    CandidateSentenceResult,
    LearnableObject,
    ParseRequest,
    ParseResponse,
    SentenceResult,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["parse"])

# Keep-alive ping interval for SSE connections (seconds).
_SSE_PING_INTERVAL = 20


# ── POST /parse/jobs ──────────────────────────────────────────────────────────

@router.post("/parse/jobs", response_model=ParseJobCreated, status_code=202)
@limiter.limit(lambda: get_settings().rate_limit_parse)
async def create_parse_job(
    request: Request,
    payload: ParseRequest,
    background_tasks: BackgroundTasks,
    registry: PluginRegistry = Depends(get_plugin_registry),
    current_user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    session_factory=Depends(get_session_factory),
) -> ParseJobCreated:
    """Accept a large text for async NLP processing.

    Returns ``202 Accepted`` with a ``job_id``.  The client should then either
    poll ``GET /parse/jobs/{job_id}`` or subscribe to
    ``GET /parse/jobs/{job_id}/events`` (SSE) to receive progress and the final
    ``ParseResponse`` result.

    Texts up to ``max_parse_chars`` should use ``POST /parse`` instead (sync,
    lower latency).  Texts above ``max_job_chars`` are rejected with 413.
    """
    if len(payload.text) > settings.max_job_chars:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Text is {len(payload.text):,} characters; "
                f"the maximum for async jobs is {settings.max_job_chars:,}. "
                "Split the text into smaller passages."
            ),
        )

    try:
        plugin = registry.get(payload.language)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    job_id = uuid.uuid4().hex
    job = job_store.create(job_id, current_user)

    background_tasks.add_task(
        _run_parse_job,
        job_id,
        payload,
        plugin,
        session_factory,
        current_user,
        settings,
    )

    logger.info(
        "parse_job created job_id=%s lang=%s chars=%d user=%s",
        job_id, payload.language, len(payload.text), current_user,
    )
    return ParseJobCreated(job_id=job_id, status="pending")


# ── GET /parse/jobs/{job_id} ──────────────────────────────────────────────────

@router.get("/parse/jobs/{job_id}", response_model=ParseJobStatus)
async def get_parse_job(
    job_id: str,
    current_user: str = Depends(get_current_user),
) -> ParseJobStatus:
    """Return the current status (and result when done) for a parse job."""
    job = _get_owned_job(job_id, current_user)
    return _job_to_schema(job)


# ── GET /parse/jobs/{job_id}/events ──────────────────────────────────────────

@router.get("/parse/jobs/{job_id}/events")
async def parse_job_events(
    job_id: str,
    current_user: str = Depends(get_current_user),
) -> StreamingResponse:
    """SSE stream of progress events for a parse job.

    Each event is a JSON object with at minimum:
      ``job_id``, ``status``, ``progress``, ``stage``,
      ``sentences_done``, ``sentences_total``

    The ``done`` event additionally carries the full ``result`` (ParseResponse).
    The ``failed`` event carries ``error``.

    The stream ends automatically when status reaches ``done`` or ``failed``.
    Periodic ``ping`` events keep the connection alive through proxies.
    """
    job = _get_owned_job(job_id, current_user)
    return StreamingResponse(
        _event_generator(job),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Disable Nginx buffering for SSE
            "Connection": "keep-alive",
        },
    )


# ── SSE helpers ───────────────────────────────────────────────────────────────

async def _event_generator(job: ParseJob):
    """Async generator that yields SSE-formatted bytes for *job* updates."""
    q = job_store.subscribe(job)
    try:
        # Send the current snapshot immediately so the client gets state even
        # if it subscribes after the job has already made progress.
        snapshot = job.public_dict()
        if job.status == "done" and job.result is not None:
            snapshot["result"] = job.result
        yield _sse(snapshot)

        if job.status in ("done", "failed"):
            return

        while True:
            try:
                data = await asyncio.wait_for(q.get(), timeout=_SSE_PING_INTERVAL)
                yield _sse(data)
                if data.get("status") in ("done", "failed"):
                    break
            except asyncio.TimeoutError:
                # Send a keepalive comment so proxies don't close the connection.
                yield b": ping\n\n"
    finally:
        job_store.unsubscribe(job, q)


def _sse(data: dict) -> bytes:
    return f"data: {json.dumps(data)}\n\n".encode()


# ── Background job runner ─────────────────────────────────────────────────────

async def _run_parse_job(
    job_id: str,
    payload: ParseRequest,
    plugin,
    session_factory,
    user_id: str,
    settings: Settings,
) -> None:
    """Execute the full parse pipeline for a job, updating progress along the way.

    Runs NLP in a thread-pool executor so the event loop is not blocked by
    CPU-bound spaCy processing.  DB persistence reuses the same logic as the
    sync ``/parse`` endpoint.
    """
    from backend.api.routes.parse import _persist_parse

    job = job_store.get(job_id)
    if job is None:
        return

    job_store.update(job, status="running", stage="nlp", progress=0.05)

    try:
        # ── NLP (CPU-bound — run in thread pool) ──────────────────────────────
        loop = asyncio.get_event_loop()
        candidate_results: list[CandidateSentenceResult] = await loop.run_in_executor(
            None, plugin.analyze_text, payload.text
        )

        sentences_total = len(candidate_results)
        job_store.update(
            job, stage="nlp", progress=0.40,
            sentences_total=sentences_total,
        )

        # ── Resolve candidates → LearnableObjects ─────────────────────────────
        uuid_to_candidate: dict[str, tuple[str, CandidateObject]] = {}
        sentences: list[SentenceResult] = []

        for cand_result in candidate_results:
            resolved: list[LearnableObject] = []
            for cand in cand_result.candidates:
                obj_id = canonical_object_id(
                    payload.language, cand.type, cand.canonical_form
                )
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
            sentences.append(
                SentenceResult(text=cand_result.text, learnable_objects=resolved)
            )

        # Populate in-session lesson store for fallback when DB is unavailable.
        for obj_id, (_, cand) in uuid_to_candidate.items():
            plugin.lesson_store[obj_id] = cand

        job_store.update(job, stage="persist", progress=0.50)

        # ── DB persistence ────────────────────────────────────────────────────
        async with session_factory() as db:
            await _persist_parse(
                db, payload, candidate_results, sentences, uuid_to_candidate, user_id
            )

        job_store.update(
            job,
            stage="persist",
            progress=0.90,
            sentences_done=sentences_total,
        )

        # ── Dictionary / translation enrichment ───────────────────────────────
        if settings.enable_dictionary_lookup or settings.enable_translation_enrichment:
            from backend.dictionary.enrichment import enrich_objects
            object_ids = list(uuid_to_candidate.keys())
            try:
                async with session_factory() as db:
                    await enrich_objects(
                        db,
                        object_ids,
                        enable_gloss=settings.enable_dictionary_lookup,
                        translation_provider=(
                            settings.translation_provider
                            if settings.enable_translation_enrichment else "none"
                        ),
                        translation_api_url=settings.translation_api_url,
                        translation_api_key=settings.translation_api_key,
                    )
            except Exception:
                logger.warning(
                    "Enrichment failed for parse_job=%s", job_id, exc_info=True
                )

        # ── Done ──────────────────────────────────────────────────────────────
        response = ParseResponse(sentences=sentences)
        job_store.finish(job, response.model_dump(mode="json"))
        logger.info(
            "parse_job done job_id=%s sentences=%d objects=%d",
            job_id, sentences_total, len(uuid_to_candidate),
        )

    except Exception as exc:
        logger.error("parse_job failed job_id=%s: %s", job_id, exc, exc_info=True)
        job_store.fail(job, str(exc))


# ── Utility ───────────────────────────────────────────────────────────────────

def _get_owned_job(job_id: str, user_id: str) -> ParseJob:
    """Return the job or raise 404.  Prevents one user from seeing another's job."""
    job = job_store.get(job_id)
    if job is None or job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


def _job_to_schema(job: ParseJob) -> ParseJobStatus:
    result = None
    if job.status == "done" and job.result is not None:
        result = ParseResponse.model_validate(job.result)
    return ParseJobStatus(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        stage=job.stage,
        sentences_done=job.sentences_done,
        sentences_total=job.sentences_total,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
        result=result,
    )
