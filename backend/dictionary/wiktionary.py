"""Wiktionary REST API client for dictionary gloss lookup.

Fetches the first definition of a lemma from the English-language Wiktionary
using the public REST v1 API.  No API key is required; the endpoint is free
for reasonable usage.

API endpoint
────────────
    GET https://en.wiktionary.org/api/rest_v1/page/definition/{lemma}

Response structure (simplified):
    {
      "<lang_code>": [
        {
          "partOfSpeech": "Noun",
          "definitions": [
            {
              "definition": "HTML-formatted definition string.",
              "examples": [...],
              "parsedExamples": [{"example": "..."}]
            }
          ]
        }
      ],
      ...
    }

The top-level language code keys use Wiktionary's own codes, which mostly
match BCP-47 but have exceptions (see BCP47_TO_WIKTIONARY).

Graceful degradation
────────────────────
- 404 → word not in Wiktionary → return None.
- Network / timeout errors → raise so the caller can decide whether to retry.
- Language not in mapping → return None without making an HTTP request.
- Empty language section → return None.

HTML stripping
──────────────
Wiktionary definitions contain inline HTML (<b>, <i>, <a>, <span>, …).  They
are stripped with a minimal regex; the result is plain UTF-8 text suitable for
storing in ``lesson_data["gloss"]``.  No external HTML-parsing library is used.
"""
from __future__ import annotations

import logging
import re
import urllib.parse

import httpx

logger = logging.getLogger(__name__)

# ── Language code mapping ─────────────────────────────────────────────────────
# Maps BCP-47 codes used by Mnemosyne plugins to the Wiktionary section keys
# returned by the REST API.  Most match exactly; Latin is handled separately
# because Wiktionary uses "la" while the Mnemosyne plugin also uses "la".

BCP47_TO_WIKTIONARY: dict[str, str] = {
    "ar": "ar",
    "de": "de",
    "en": "en",
    "es": "es",
    "fr": "fr",
    "he": "he",
    "ja": "ja",
    "la": "la",
    "ru": "ru",
    "zh": "zh",
}

#: Base URL for the Wiktionary REST API (override in tests via WIKTIONARY_BASE_URL).
WIKTIONARY_BASE_URL = "https://en.wiktionary.org/api/rest_v1"

#: HTTP timeout in seconds for Wiktionary requests.
WIKTIONARY_TIMEOUT_S = 6.0

#: User-Agent sent with every Wiktionary request (Wiktionary policy requires one).
_USER_AGENT = "Mnemosyne/1.0 (language learning app; https://github.com/mnemosyne)"


# ── Public API ────────────────────────────────────────────────────────────────

async def fetch_definition(
    lemma: str,
    language_code: str,
    *,
    base_url: str = WIKTIONARY_BASE_URL,
) -> str | None:
    """Return the first Wiktionary English gloss for *lemma* in *language_code*.

    Parameters
    ----------
    lemma:
        The dictionary headword to look up.  May contain non-ASCII characters
        (e.g. Cyrillic, CJK); URL-encoding is handled internally.
    language_code:
        BCP-47 code (e.g. ``"es"``, ``"ru"``, ``"zh"``).  Unknown codes
        return ``None`` without making a network request.
    base_url:
        Override the Wiktionary REST base URL.  Used in tests to point at a
        local mock server via respx.

    Returns
    -------
    str or None
        Plain-text English definition, or ``None`` when:
        - language_code is not in BCP47_TO_WIKTIONARY,
        - the word is not found on Wiktionary (HTTP 404),
        - no definition text can be extracted from the response.

    Raises
    ------
    httpx.RequestError
        On network-level failures (timeout, DNS, connection refused).
    httpx.HTTPStatusError
        On unexpected HTTP error responses (not 404).
    """
    wikt_lang = BCP47_TO_WIKTIONARY.get(language_code)
    if wikt_lang is None:
        return None

    encoded = urllib.parse.quote(lemma, safe="")
    url = f"{base_url}/page/definition/{encoded}"

    async with httpx.AsyncClient(
        timeout=WIKTIONARY_TIMEOUT_S,
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
    ) as client:
        resp = await client.get(url)

    if resp.status_code == 404:
        logger.debug("wiktionary 404 lemma=%r lang=%s", lemma, language_code)
        return None

    resp.raise_for_status()

    try:
        data: dict = resp.json()
    except ValueError:
        logger.warning("wiktionary invalid JSON for lemma=%r", lemma)
        return None

    return _extract_first_definition(data, wikt_lang)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _extract_first_definition(data: dict, wikt_lang: str) -> str | None:
    """Find the first non-empty definition for *wikt_lang* in an API response.

    Iterates over all part-of-speech sections for the target language and
    returns the first definition string that survives HTML stripping.
    """
    lang_entries = data.get(wikt_lang, [])
    if not lang_entries:
        return None

    for entry in lang_entries:
        for defn in entry.get("definitions", []):
            raw = defn.get("definition", "")
            clean = strip_html(raw).strip()
            if clean:
                return clean

    return None


# Compiled once — strips all HTML tags and normalises whitespace.
_TAG_RE     = re.compile(r"<[^>]+>")
_SPACE_RE   = re.compile(r"\s+")


def strip_html(html: str) -> str:
    """Remove HTML tags and normalise whitespace from a Wiktionary definition.

    Wiktionary definitions use tags like ``<b>``, ``<i>``, ``<a href="...">``,
    ``<span class="...">`` inline.  This function strips all of them and
    collapses any resulting whitespace runs to a single space.

    Does not use an HTML parser — the patterns are simple enough that a regex
    is safe and avoids an extra dependency.
    """
    no_tags = _TAG_RE.sub("", html)
    return _SPACE_RE.sub(" ", no_tags)
