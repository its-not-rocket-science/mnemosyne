"""Machine translation client for Mnemosyne.

Provides a thin async layer over two free translation backends:

LibreTranslate (default)
────────────────────────
Open-source, self-hostable, Apache 2.0.  Can be pointed at:
  - Your own instance  (TRANSLATION_API_URL=http://localhost:5000)
  - libretranslate.com (TRANSLATION_API_URL=https://libretranslate.com)

API call:
    POST {TRANSLATION_API_URL}/translate
    Body: {"q": text, "source": lang, "target": "en", "api_key": "..."}
    Response: {"translatedText": "..."}

LibreTranslate.com offers a free tier (rate-limited without a key).
API keys are optional for self-hosted instances.
Attribution: the engine is FOSS; for hosted service see libretranslate.com/terms.

MyMemory (fallback)
───────────────────
Free up to 1 000 words/day per IP without a key; 10 000/day with a registered
email (set TRANSLATION_API_KEY to the email address for the higher quota).
Attribution required: "Powered by MyMemory — <https://mymemory.translated.net>"

API call:
    GET https://api.mymemory.translated.net/get
        ?q={text}&langpair={source}|{target}&de={email_or_empty}
    Response: {"responseData": {"translatedText": "..."}, "responseStatus": 200}

Selecting a provider
─────────────────────
Set ``TRANSLATION_PROVIDER`` in ``.env``:
  TRANSLATION_PROVIDER=libretranslate   (default)
  TRANSLATION_PROVIDER=mymemory
  TRANSLATION_PROVIDER=none             (disables translation globally)

When no provider is configured (``"none"``), ``translate()`` always returns
``None`` without making any HTTP request.

Cost / attribution summary
──────────────────────────
  Provider          Cost            Attribution required
  ──────────────── ─────────────── ──────────────────────────────────────────
  LibreTranslate   Free (self)     None (you run it); see terms if using
                   ~paid (hosted)  libretranslate.com hosted tier.
  MyMemory         Free ≤1000/day  "Powered by MyMemory"
                   Free ≤10k/day   + email key
"""
from __future__ import annotations

import logging
import urllib.parse

import httpx

logger = logging.getLogger(__name__)

#: Timeout in seconds for translation requests.
TRANSLATION_TIMEOUT_S = 8.0

_USER_AGENT = "Mnemosyne/1.0 (language learning app)"

# ── LibreTranslate ────────────────────────────────────────────────────────────

#: Default LibreTranslate API endpoint.  Override with TRANSLATION_API_URL.
LIBRETRANSLATE_DEFAULT_URL = "https://libretranslate.com"


async def translate_libretranslate(
    text: str,
    source: str,
    target: str = "en",
    *,
    base_url: str = LIBRETRANSLATE_DEFAULT_URL,
    api_key: str | None = None,
) -> str | None:
    """Translate *text* using a LibreTranslate-compatible endpoint.

    Parameters
    ----------
    text:
        Source text (word or short phrase).
    source:
        BCP-47 source language code (e.g. ``"es"``).
    target:
        BCP-47 target language code.  Default ``"en"`` (English).
    base_url:
        LibreTranslate instance URL.  Override in tests via this parameter.
    api_key:
        Optional API key.  Required for libretranslate.com; not needed for
        most self-hosted instances.

    Returns
    -------
    Translated string, or None on 400/404/language-not-supported.

    Raises
    ------
    httpx.RequestError
        On network-level failures.
    httpx.HTTPStatusError
        On unexpected server errors (5xx).
    """
    payload: dict = {"q": text, "source": source, "target": target, "format": "text"}
    if api_key:
        payload["api_key"] = api_key

    url = f"{base_url.rstrip('/')}/translate"
    async with httpx.AsyncClient(
        timeout=TRANSLATION_TIMEOUT_S,
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
    ) as client:
        resp = await client.post(url, json=payload)

    if resp.status_code in (400, 404):
        # Language pair not supported or text rejected.
        logger.debug(
            "libretranslate %d for text=%r source=%s", resp.status_code, text[:30], source
        )
        return None

    resp.raise_for_status()

    try:
        data = resp.json()
    except ValueError:
        logger.warning("libretranslate invalid JSON response for text=%r", text[:30])
        return None

    result = data.get("translatedText", "").strip()
    return result or None


# ── MyMemory ──────────────────────────────────────────────────────────────────

MYMEMORY_URL = "https://api.mymemory.translated.net/get"


async def translate_mymemory(
    text: str,
    source: str,
    target: str = "en",
    *,
    api_key: str | None = None,
    base_url: str = MYMEMORY_URL,
) -> str | None:
    """Translate *text* using MyMemory (no API key required for free tier).

    Attribution: translations are powered by MyMemory
    (https://mymemory.translated.net).  Commercial use requires a paid plan.
    Free tier: 1 000 words/day per IP; 10 000 words/day with a registered email
    (pass email as api_key).

    Returns
    -------
    Translated string, or None when the response status is not 200 or the
    translation is empty.

    Raises
    ------
    httpx.RequestError
        On network-level failures.
    httpx.HTTPStatusError
        On HTTP error responses.
    """
    params: dict[str, str] = {
        "q": text,
        "langpair": f"{source}|{target}",
    }
    if api_key:
        params["de"] = api_key   # MyMemory uses "de" for email/key

    async with httpx.AsyncClient(
        timeout=TRANSLATION_TIMEOUT_S,
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
    ) as client:
        resp = await client.get(base_url, params=params)

    resp.raise_for_status()

    try:
        data = resp.json()
    except ValueError:
        logger.warning("mymemory invalid JSON response for text=%r", text[:30])
        return None

    if data.get("responseStatus") != 200:
        logger.debug(
            "mymemory status %s for text=%r", data.get("responseStatus"), text[:30]
        )
        return None

    result = (data.get("responseData") or {}).get("translatedText", "").strip()
    # MyMemory sometimes returns "PLEASE SELECT TWO DISTINCT LANGUAGES" when
    # the source and target are the same or the pair is unsupported.
    if not result or result.startswith("PLEASE SELECT"):
        return None
    return result


# ── Provider dispatcher ───────────────────────────────────────────────────────

async def translate(
    text: str,
    source: str,
    target: str = "en",
    *,
    provider: str = "none",
    api_url: str | None = None,
    api_key: str | None = None,
) -> str | None:
    """Translate *text* using the configured provider.

    Parameters
    ----------
    text:
        Text to translate (typically a lemma or short phrase).
    source:
        BCP-47 source language code.
    target:
        BCP-47 target language code.  Defaults to ``"en"``.
    provider:
        Backend to use: ``"libretranslate"``, ``"mymemory"``, or ``"none"``.
        ``"none"`` returns ``None`` immediately without any network call.
    api_url:
        Override the default API endpoint (useful for self-hosted instances).
    api_key:
        Provider-specific API key.  Optional for LibreTranslate (required on
        libretranslate.com paid plans); optional email for MyMemory free tier.

    Returns
    -------
    Translated string, or None when the provider is ``"none"``, the language
    pair is unsupported, or the result is empty.
    """
    if provider == "none" or not text.strip():
        return None

    if provider == "libretranslate":
        return await translate_libretranslate(
            text, source, target,
            base_url=api_url or LIBRETRANSLATE_DEFAULT_URL,
            api_key=api_key,
        )

    if provider == "mymemory":
        return await translate_mymemory(
            text, source, target,
            api_key=api_key,
            base_url=api_url or MYMEMORY_URL,
        )

    logger.warning("Unknown translation provider %r — returning None", provider)
    return None
