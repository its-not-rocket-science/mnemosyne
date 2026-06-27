import logging
import time
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_plugin_registry
from backend.core.config import Settings, get_settings
from backend.services.analytics import maybe_record_event
from backend.core.database import get_session_factory
from backend.core.limiter import limiter
from backend.ingestion.validator import validate_ingest_text
from backend.models import CanonicalObjectRow, ObjectRelationRow, ParsedText, Sentence, SentenceObjectRow, UserKnowledgeRow
from backend.parsing.canonical import canonical_object_id
from backend.parsing.pipeline import PipelineResult, pipeline_cache_key, run_pipeline
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
@limiter.limit(lambda: get_settings().rate_limit_parse)
async def parse_text(
    request: Request,
    response: Response,
    payload: ParseRequest,
    background_tasks: BackgroundTasks,
    registry: PluginRegistry = Depends(get_plugin_registry),
    current_user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    session_factory=Depends(get_session_factory),
) -> ParseResponse:
    if len(payload.text) > settings.max_parse_chars:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Text is {len(payload.text):,} characters; "
                f"the limit is {settings.max_parse_chars:,}. "
                "Split the text into smaller passages and submit each separately."
            ),
        )

    try:
        plugin = registry.get(payload.language)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _, parse_warnings = validate_ingest_text(payload.text, payload.language)

    t0 = time.perf_counter()

    result: PipelineResult = await run_pipeline(
        text=payload.text,
        language=payload.language,
        plugin=plugin,
        cache_key=pipeline_cache_key(payload.text, payload.language),
    )

    debug_id = f"parse-{int(time.time() * 1000)}"
    response.headers["X-Mnemosyne-Parse-Debug-Id"] = debug_id
    if result.cache_hit:
        logger.info(
            "parse_debug id=%s cache_hit=true lang=%s chars=%d sentences=%d",
            debug_id, payload.language, len(payload.text), len(result.sentences),
        )
        return ParseResponse(sentences=result.sentences, warnings=parse_warnings)

    background_tasks.add_task(
        _persist_parse_background,
        session_factory, payload, result.candidate_results,
        result.sentences, result.uuid_to_candidate, current_user,
    )

    logger.info(
        "parse lang=%s chars=%d sentences=%d objects=%d elapsed_ms=%.1f",
        payload.language,
        len(payload.text),
        len(result.sentences),
        len(result.uuid_to_candidate),
        (time.perf_counter() - t0) * 1000,
    )
    candidate_preview = [
        {
            "sentence": c.text,
            "candidates": [{"label": o.label, "type": o.type, "canonical_form": o.canonical_form} for o in c.candidates],
        }
        for c in result.candidate_results[:3]
    ]
    logger.info(
        "parse_debug id=%s cache_hit=false tokenization=%s preview=%s",
        debug_id,
        getattr(plugin.capabilities, "tokenization_mode", "unknown"),
        candidate_preview,
    )
    return ParseResponse(sentences=result.sentences, warnings=parse_warnings)


async def _persist_parse_background(
    session_factory,
    payload: ParseRequest,
    candidate_results: list[CandidateSentenceResult],
    sentences: list[SentenceResult],
    uuid_to_candidate: dict[str, tuple[str, CandidateObject]],
    user_id: str,
) -> None:
    """Open a fresh DB session and persist the parse results.

    Called by FastAPI's BackgroundTasks after the HTTP response has been sent.
    Creating a new session here is necessary because the request-scoped session
    is closed before background tasks run.

    When ``ENABLE_DICTIONARY_LOOKUP=true``, a second pass is made in a fresh
    session to enrich vocabulary objects with Wiktionary glosses.  This runs
    after the main persist so canonical objects are guaranteed to be in the DB
    before enrichment reads them.
    """
    parsed_text_id: str | None = None
    try:
        async with session_factory() as db:
            parsed_text_id = await _persist_parse(db, payload, candidate_results, sentences, uuid_to_candidate, user_id)
            await maybe_record_event(
                db, user_id, "text_ingested",
                language=payload.language,
                count=len(sentences),
            )
    except Exception:
        logger.warning("Background DB persist failed for /parse", exc_info=True)
        return  # Don't attempt enrichment or mining if persist itself failed

    # ── Sentence mining ───────────────────────────────────────────────────────
    if parsed_text_id:
        from backend.services.sentence_mining import mine_parsed_text
        try:
            async with session_factory() as db:
                await mine_parsed_text(
                    db,
                    parsed_text_id=parsed_text_id,
                    language=payload.language,
                    user_id=user_id,
                )
        except Exception:
            logger.warning("Background sentence mining failed for /parse", exc_info=True)

    s = get_settings()
    if s.enable_dictionary_lookup or s.enable_translation_enrichment:
        from backend.dictionary.enrichment import enrich_objects
        object_ids = list(uuid_to_candidate.keys())
        try:
            async with session_factory() as db:
                await enrich_objects(
                    db,
                    object_ids,
                    enable_gloss=s.enable_dictionary_lookup,
                    translation_provider=s.translation_provider if s.enable_translation_enrichment else "none",
                    translation_api_url=s.translation_api_url,
                    translation_api_key=s.translation_api_key,
                )
        except Exception:
            logger.warning("Background enrichment failed for /parse", exc_info=True)


async def _persist_parse(
    db: AsyncSession,
    payload: ParseRequest,
    candidate_results: list[CandidateSentenceResult],
    sentences: list[SentenceResult],
    uuid_to_candidate: dict[str, tuple[str, CandidateObject]],
    user_id: str,
) -> str:
    """Write ParsedText, Sentences, upsert CanonicalObjects, and record relations.

    Returns the parsed_text_id of the newly created ParsedText row.
    """
    parsed = ParsedText(
        language=payload.language,
        source_text=payload.text,
        source_url=payload.source_url,
        user_id=user_id,
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
    desired_relations: set[tuple[str, str, str]] = set()
    for cand_result in candidate_results:
        for cand in cand_result.candidates:
            src_id = canonical_object_id(payload.language, cand.type, cand.canonical_form)
            for hint in cand.relation_hints:
                tgt_id = canonical_object_id(
                    payload.language, hint.target_type, hint.target_canonical_form
                )
                if tgt_id not in uuid_to_candidate:
                    continue  # target not extracted in this parse — skip
                desired_relations.add((src_id, tgt_id, hint.relation_type))

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
    return parsed.id


def _now_utc() -> datetime:
    return datetime.now(UTC)
