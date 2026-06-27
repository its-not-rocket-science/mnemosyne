"""POST /fetch-url — server-side URL fetch and text extraction.
POST /detect-language — lightweight language detection.

These two endpoints back the "Fetch" button and language auto-detection
features in the frontend.  The browser never makes a cross-origin request
for the remote URL; all network I/O happens here on the server.
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import get_plugin_registry
from backend.ingestion.fetcher import fetch_and_extract
from backend.ingestion.language_detect import MIN_CONFIDENCE, detect_language
from backend.parsing.plugin_loader import PluginRegistry
from backend.schemas.fetch_url import (
    DetectLanguageRequest,
    DetectLanguageResponse,
    FetchUrlRequest,
    FetchUrlResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ingest"])


@router.post("/fetch-url", response_model=FetchUrlResponse)
async def fetch_url(
    payload: FetchUrlRequest,
    registry: PluginRegistry = Depends(get_plugin_registry),
) -> FetchUrlResponse:
    """Fetch a URL server-side and return its readable text.

    The client never makes a cross-origin request for the remote page.
    Returns the extracted title, plain text, character count, and a
    best-effort language detection result derived from the extracted text.

    Error responses
    ---------------
    422  URL scheme is not http or https, or the page contains no readable text.
    502  Network error, timeout, or the remote server returned 4xx/5xx.
    """
    try:
        result = await fetch_and_extract(payload.source_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=502,
            detail=(
                "The page did not respond in time. "
                "Try again later, or paste the text manually."
            ),
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"The page returned an error ({exc.response.status_code}). "
                "Check the URL and try again."
            ),
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach the URL: {exc}",
        )

    if not result.text.strip():
        raise HTTPException(
            status_code=422,
            detail=(
                "No readable text could be extracted from that page. "
                "Try copying the text manually."
            ),
        )

    # Best-effort language detection; never blocks the response.
    detected: str | None = None
    conf: float = 0.0
    try:
        lang, conf = detect_language(result.text)
        if lang and conf >= MIN_CONFIDENCE:
            detected = lang
    except Exception:
        pass  # detection failure is non-fatal

    logger.info(
        "fetch-url url=%r chars=%d detected=%s conf=%.2f",
        payload.source_url, len(result.text), detected, conf,
    )

    return FetchUrlResponse(
        source_url=result.final_url,
        title=result.title,
        text=result.text,
        char_count=len(result.text),
        detected_language=detected,
    )


@router.post("/detect-language", response_model=DetectLanguageResponse)
async def detect_language_route(
    payload: DetectLanguageRequest,
    registry: PluginRegistry = Depends(get_plugin_registry),
) -> DetectLanguageResponse:
    """Detect the probable language of a text sample.

    Returns the BCP-47 language code, a 0–1 confidence score, and whether
    the detected language has a registered plugin in this deployment.
    Returns ``language: null`` when confidence is below the minimum threshold
    or the sample is too short to classify reliably.

    This endpoint never raises an error — callers treat the result as a
    best-effort hint, not a hard classification.
    """
    lang: str | None = None
    confidence: float = 0.0

    try:
        lang, confidence = detect_language(payload.text)
    except Exception:
        pass  # detection failure → return null language, zero confidence

    if confidence < MIN_CONFIDENCE:
        lang = None

    supported = bool(lang and lang in registry.all())

    return DetectLanguageResponse(
        language=lang,
        confidence=round(confidence, 2),
        supported=supported,
    )
