"""POST /translate — on-demand machine translation endpoint.

Translates arbitrary text from a source language to English (or another
target language).  Results for canonical objects are cached back to
``lesson_data["translation"]`` to avoid redundant API calls on repeated
requests.

Rate limiting
─────────────
Shares ``RATE_LIMIT_PARSE`` with ``/parse`` so translation calls cannot be
used to bypass the parse rate limit.

Attribution
───────────
The response always includes a ``provider`` field and a human-readable
``attribution`` string so frontends can comply with provider terms of service.
MyMemory in particular requires "Powered by MyMemory" to be displayed.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db_session
from backend.core.config import Settings, get_settings
from backend.core.limiter import limiter
from backend.models import CanonicalObjectRow
from backend.schemas.translate import TranslateRequest, TranslateResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["translate"])

ATTRIBUTION_TEXT: dict[str, str] = {
    "libretranslate": "Powered by LibreTranslate (https://libretranslate.com)",
    "mymemory": "Powered by MyMemory (https://mymemory.translated.net)",
    "none": "",
}


@router.post("/translate", response_model=TranslateResponse)
@limiter.limit(lambda: get_settings().rate_limit_parse)
async def translate_text(
    request: Request,
    payload: TranslateRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> TranslateResponse:
    """Translate text from *source_language* to *target_language*.

    When ``TRANSLATION_PROVIDER=none`` (the default) returns
    ``translation: null`` without any external call.

    If ``object_id`` is supplied and the object already has
    ``lesson_data["translation"]``, the stored value is returned immediately
    (``cached: true``) without hitting the translation API.

    The ``attribution`` string in the response must be displayed when showing
    translated text to comply with provider terms of service.
    """
    provider = (settings.translation_provider or "none").strip().lower()

    # ── Check stored translation first ────────────────────────────────────────
    if payload.object_id:
        try:
            row = await db.get(CanonicalObjectRow, payload.object_id)
            if row is not None:
                ld = row.lesson_data or {}
                # Support both legacy "translation" and new "translations" format
                existing = None

                # New format (preferred)
                translations: dict = ld.get("translations") or {}
                existing = translations.get(payload.target_language)

                # Legacy format (used in tests + existing DB rows)
                if not existing:
                    existing = ld.get("translation")

                if existing:
                    stored_provider = (ld.get("translation_provider") or provider or "none").strip().lower()
                    return TranslateResponse(
                        text=payload.text,
                        translation=existing,
                        source_language=payload.source_language,
                        target_language=payload.target_language,
                        provider=stored_provider,
                        attribution=ATTRIBUTION_TEXT.get(stored_provider, ""),
                        cached=True,
                    )
        except Exception:
            logger.warning(
                "DB lookup failed for object_id=%r during translate",
                payload.object_id,
                exc_info=True,
            )

    # ── Provider disabled ─────────────────────────────────────────────────────
    if provider in {"none", "", "disabled", "off"}:
        return TranslateResponse(
            text=payload.text,
            translation=None,
            source_language=payload.source_language,
            target_language=payload.target_language,
            provider="none",
            attribution="",
        )

    # ── Live translation ───────────────────────────────────────────────────────
    import httpx
    from backend.dictionary.translation import translate

    try:
        result = await translate(
            payload.text,
            payload.source_language,
            payload.target_language,
            provider=provider,
            api_url=settings.translation_api_url,
            api_key=settings.translation_api_key,
        )
    except httpx.RequestError as exc:
        logger.warning("Translation network error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Translation service unavailable. Try again later.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Translation HTTP %d for text=%r",
            exc.response.status_code, payload.text[:30],
        )
        raise HTTPException(
            status_code=502,
            detail=f"Translation service returned HTTP {exc.response.status_code}.",
        ) from exc

    # ── Cache result on the canonical object ──────────────────────────────────
    if result and payload.object_id:
        try:
            row = await db.get(CanonicalObjectRow, payload.object_id)
            if row is not None:
                updated = dict(row.lesson_data or {})
                translations = dict(updated.get("translations") or {})
                translations[payload.target_language] = result
                updated["translations"] = translations
                updated["translation_provider"] = provider
                row.lesson_data = updated
                await db.commit()
        except Exception:
            logger.warning(
                "Failed to cache translation for object_id=%r",
                payload.object_id,
                exc_info=True,
            )

    return TranslateResponse(
        text=payload.text,
        translation=result,
        source_language=payload.source_language,
        target_language=payload.target_language,
        provider=provider,
        attribution=ATTRIBUTION_TEXT.get(provider, ""),
    )
