from __future__ import annotations

import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_db_session, get_plugin_registry
from backend.core.cache import get_json, set_json
from backend.models import LearnableObjectRow, ParsedText, Sentence
from backend.parsing.plugin_loader import PluginRegistry
from backend.schemas.parse import ParseRequest, ParseResponse, SentenceResult

logger = logging.getLogger(__name__)
router = APIRouter(tags=["parse"])


@router.post("/parse", response_model=ParseResponse)
async def parse_text(
    payload: ParseRequest,
    registry: PluginRegistry = Depends(get_plugin_registry),
    db: AsyncSession = Depends(get_db_session),
) -> ParseResponse:
    try:
        plugin = registry.get(payload.language)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    cache_key = _cache_key(payload.text, payload.language)
    try:
        cached = await get_json(cache_key)
        if cached is not None:
            return ParseResponse.model_validate(cached)
    except Exception:
        pass  # Redis unavailable — continue without cache

    sentences: list[SentenceResult] = [
        plugin.analyze_sentence(s) for s in plugin.split_sentences(payload.text)
    ]
    response = ParseResponse(sentences=sentences)

    try:
        await _persist_parse(db, payload, sentences)
    except Exception:
        logger.warning("DB persistence failed for /parse", exc_info=True)

    try:
        await set_json(cache_key, response.model_dump(mode="json"))
    except Exception:
        pass  # Redis unavailable — return result uncached

    return response


async def _persist_parse(
    db: AsyncSession,
    payload: ParseRequest,
    sentences: list[SentenceResult],
) -> None:
    """Write ParsedText, Sentences, and upsert LearnableObjects to the DB."""
    parsed = ParsedText(
        language=payload.language,
        source_text=payload.text,
        source_url=payload.source_url,
    )
    db.add(parsed)
    await db.flush()  # materialise parsed.id before FK references

    for pos, sentence in enumerate(sentences):
        db.add(Sentence(parsed_text_id=parsed.id, position=pos, text=sentence.text))

    # Upsert learnable objects — one SELECT to find existing IDs, then
    # add new rows and refresh lesson_data on existing ones.
    all_ids = list({obj.id for s in sentences for obj in s.learnable_objects})
    if all_ids:
        result = await db.execute(
            select(LearnableObjectRow).where(LearnableObjectRow.id.in_(all_ids))
        )
        existing: dict[str, LearnableObjectRow] = {
            row.id: row for row in result.scalars()
        }
    else:
        existing = {}

    seen: set[str] = set()
    for sentence in sentences:
        for obj in sentence.learnable_objects:
            if obj.id in seen:
                continue
            seen.add(obj.id)
            if obj.id in existing:
                row = existing[obj.id]
                row.lesson_data = obj.lesson_data
                row.confidence = obj.confidence
            else:
                db.add(
                    LearnableObjectRow(
                        id=obj.id,
                        language=payload.language,
                        type=obj.type,
                        label=obj.label,
                        lesson_data=obj.lesson_data,
                        confidence=obj.confidence,
                    )
                )

    await db.commit()


def _cache_key(text: str, language: str) -> str:
    digest = hashlib.sha256(f"{language}:{text}".encode("utf-8")).hexdigest()
    return f"parse:{digest}"
