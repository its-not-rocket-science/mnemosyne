from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import get_plugin_registry
from backend.core.cache import get_json, set_json
from backend.parsing.plugin_loader import PluginRegistry
from backend.schemas.parse import ParseRequest, ParseResponse, SentenceResult

router = APIRouter(tags=["parse"])


@router.post("/parse", response_model=ParseResponse)
async def parse_text(
    payload: ParseRequest,
    registry: PluginRegistry = Depends(get_plugin_registry),
) -> ParseResponse:
    try:
        plugin = registry.get(payload.language)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    cache_key = _cache_key(payload.text, payload.language)
    cached = await get_json(cache_key)
    if cached is not None:
        return ParseResponse.model_validate(cached)

    sentences: list[SentenceResult] = [
        plugin.analyze_sentence(sentence) for sentence in plugin.split_sentences(payload.text)
    ]
    response = ParseResponse(sentences=sentences)
    await set_json(cache_key, response.model_dump(mode="json"))
    return response


def _cache_key(text: str, language: str) -> str:
    digest = hashlib.sha256(f"{language}:{text}".encode("utf-8")).hexdigest()
    return f"parse:{digest}"
