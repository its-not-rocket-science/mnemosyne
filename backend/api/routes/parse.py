from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db_session, get_plugin_registry
from backend.core.cache import get_json, set_json
from backend.models import CanonicalObjectRow, ObjectRelationRow, ParsedText, Sentence, SentenceObjectRow, UserKnowledgeRow
from backend.parsing.canonical import canonical_object_id
from backend.parsing.plugin_loader import PluginRegistry
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


@router.post("/parse", response_model=ParseResponse)
async def parse_text(
    payload: ParseRequest,
    registry: PluginRegistry = Depends(get_plugin_registry),
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> ParseResponse:
    try:
        plugin = registry.get(payload.language)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    t0 = time.perf_counter()

    cache_key = _cache_key(payload.text, payload.language)
    try:
        cached = await get_json(cache_key)
        if cached is not None:
            logger.debug(
                "parse cache=HIT lang=%s chars=%d elapsed_ms=%.1f",
                payload.language, len(payload.text),
                (time.perf_counter() - t0) * 1000,
            )
            return ParseResponse.model_validate(cached)
    except Exception:
        pass  # Redis unavailable — continue without cache

    t_nlp = time.perf_counter()
    candidate_results: list[CandidateSentenceResult] = plugin.analyze_text(payload.text)
    logger.debug("parse nlp_ms=%.1f sentences=%d", (time.perf_counter() - t_nlp) * 1000, len(candidate_results))

    # Resolve candidates → LearnableObjects with stable UUIDs.
    # uuid_to_candidate tracks (canonical_form, CandidateObject) for DB persistence.
    uuid_to_candidate: dict[str, tuple[str, CandidateObject]] = {}
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

    # Populate the plugin's lesson_store for fallback when the DB is unavailable.
    # Store the CandidateObject directly — it carries canonical_form, which the
    # lesson endpoint needs to call build_lesson() correctly.
    for obj_id, (_, cand) in uuid_to_candidate.items():
        plugin.lesson_store[obj_id] = cand

    response = ParseResponse(sentences=sentences)
    response_json = response.model_dump(mode="json")

    # DB persist and cache write are independent after the response is built.
    # AsyncSession is not concurrency-safe, so persist runs first; then both
    # the cache write and the (already-done) return value are ready together.
    persist_exc: Exception | None = None
    try:
        await _persist_parse(db, payload, candidate_results, sentences, uuid_to_candidate, current_user)
    except Exception as exc:
        persist_exc = exc

    cache_task = asyncio.ensure_future(set_json(cache_key, response_json))

    if persist_exc is not None:
        logger.warning("DB persistence failed for /parse", exc_info=persist_exc)

    try:
        await cache_task
    except Exception:
        pass  # Redis unavailable — return result uncached

    logger.info(
        "parse lang=%s chars=%d sentences=%d objects=%d elapsed_ms=%.1f",
        payload.language,
        len(payload.text),
        len(sentences),
        len(uuid_to_candidate),
        (time.perf_counter() - t0) * 1000,
    )
    return response


async def _persist_parse(
    db: AsyncSession,
    payload: ParseRequest,
    candidate_results: list[CandidateSentenceResult],
    sentences: list[SentenceResult],
    uuid_to_candidate: dict[str, tuple[str, CandidateObject]],
    user_id: str,
) -> None:
    """Write ParsedText, Sentences, upsert CanonicalObjects, and record relations."""
    parsed = ParsedText(
        language=payload.language,
        source_text=payload.text,
        source_url=payload.source_url,
    )
    db.add(parsed)
    await db.flush()  # materialise parsed.id before FK references

    # Insert sentence rows and collect their IDs for the join table.
    sentence_rows: list[Sentence] = []
    for pos, result in enumerate(sentences):
        row = Sentence(parsed_text_id=parsed.id, position=pos, text=result.text)
        db.add(row)
        sentence_rows.append(row)
    await db.flush()  # materialise sentence IDs

    # ── Pass 1: upsert canonical objects ────────────────────────────────────
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
            db.add(
                CanonicalObjectRow(
                    id=obj_id,
                    language=payload.language,
                    type=cand.type,
                    canonical_form=canonical_form,
                    display_label=cand.label,
                    surface_forms=[cand.surface_form] if cand.surface_form else [],
                    lesson_data=cand.lesson_data,
                    confidence=cand.confidence,
                )
            )

    await db.flush()  # canonical objects must exist before relations and join rows

    # ── User knowledge — seed new objects as unseen ──────────────────────────
    # Creates a UserKnowledgeRow (total_reviews=0) the first time this user
    # encounters a canonical object via /parse.  Existing rows are left
    # untouched except for updating last_seen, so review history is never lost.
    uk_result = await db.execute(
        select(UserKnowledgeRow).where(
            UserKnowledgeRow.user_id == user_id,
            UserKnowledgeRow.object_id.in_(all_ids),
        )
    )
    existing_uk: dict[str, UserKnowledgeRow] = {
        row.object_id: row for row in uk_result.scalars()
    }
    now = _now_utc()
    for obj_id in all_ids:
        if obj_id in existing_uk:
            existing_uk[obj_id].last_seen = now
        else:
            db.add(UserKnowledgeRow(
                user_id=user_id,
                object_id=obj_id,
                language=payload.language,
                fsrs_state=None,
                mastery_score=0.0,
                first_seen=now,
                last_seen=now,
                total_reviews=0,
                due_at=now,
            ))

    # ── Sentence–object join rows ────────────────────────────────────────────
    for sent_row, sent_result in zip(sentence_rows, sentences):
        for pos, lo in enumerate(sent_result.learnable_objects):
            db.add(SentenceObjectRow(
                sentence_id=sent_row.id,
                object_id=lo.id,
                position=pos,
            ))

    # ── Pass 2: upsert object relations (batched) ───────────────────────────
    # Collect every (src_id, tgt_id, relation_type) triple that should exist.
    desired_relations: list[tuple[str, str, str]] = []
    for cand_result in candidate_results:
        for cand in cand_result.candidates:
            src_id = canonical_object_id(payload.language, cand.type, cand.canonical_form)
            for hint in cand.relation_hints:
                tgt_id = canonical_object_id(
                    payload.language, hint.target_type, hint.target_canonical_form
                )
                if tgt_id not in uuid_to_candidate:
                    continue  # target not extracted in this parse — skip
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

    await db.commit()


def _cache_key(text: str, language: str) -> str:
    digest = hashlib.sha256(f"{language}:{text}".encode("utf-8")).hexdigest()
    return f"parse:{digest}"


def _now_utc() -> datetime:
    return datetime.now(UTC)
