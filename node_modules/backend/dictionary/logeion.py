"""Logeion lexicon API client for classical Latin and Greek glosses.

Fetches dictionary definitions from the Logeion aggregation service
(University of Chicago), which serves Lewis & Short (Latin) and
Liddell-Scott-Jones (Greek) entries via a single JSON endpoint.

API endpoint
────────────
    GET https://logeion.uchicago.edu/lexica/{lemma}

Response structure (simplified):
    {
      "ls":  "<html-fragment>",   # Lewis & Short — Latin
      "lsj": "<html-fragment>",   # Liddell-Scott-Jones — Greek
      "slater": "...",            # Slater — Pindar (Greek)
      ...
    }

For Latin we read ``ls``; for Koine Greek (``grc``) we read ``lsj``.
HTML is stripped to plain text; only the first sentence is returned so
the gloss stays short enough to display inline.

Graceful degradation
────────────────────
- 404 / empty entry → return None.
- Language not supported → return None without HTTP request.
- Network / timeout → raise so caller can decide whether to retry.
"""
from __future__ import annotations

import logging
import urllib.parse

import httpx

from backend.dictionary.wiktionary import strip_html

logger = logging.getLogger(__name__)

#: Languages handled by this module.  Maps Mnemosyne BCP-47 code → lexicon key
#: in the Logeion JSON response.
LOGEION_LEXICON: dict[str, str] = {
    "la":  "ls",   # Lewis & Short
    "grc": "lsj",  # Liddell-Scott-Jones
}

#: Base URL for the Logeion API (override in tests).
LOGEION_BASE_URL = "https://logeion.uchicago.edu"

#: HTTP timeout in seconds.
LOGEION_TIMEOUT_S = 8.0

#: Maximum plain-text characters returned as a gloss.
_MAX_GLOSS_CHARS = 200

_USER_AGENT = "Mnemosyne/1.0 (language learning app; https://github.com/mnemosyne)"


async def fetch_definition(
    lemma: str,
    language_code: str,
    *,
    base_url: str = LOGEION_BASE_URL,
) -> str | None:
    """Return a short English gloss for *lemma* from Logeion (Lewis & Short or LSJ).

    Parameters
    ----------
    lemma:
        Dictionary headword.  Should be the lemma form (nominative for nouns,
        first-person singular present for verbs).
    language_code:
        BCP-47 code: ``"la"`` for Latin, ``"grc"`` for Koine Greek.
        Other codes return ``None`` without a network request.
    base_url:
        Override the Logeion API base URL (used in tests).

    Returns
    -------
    str or None
        First sentence of the plain-text definition, or ``None`` when:
        - language is not Latin/Greek,
        - lemma not found (HTTP 404),
        - relevant lexicon key absent or empty in response.

    Raises
    ------
    httpx.RequestError
        On network-level failures (timeout, DNS, connection refused).
    httpx.HTTPStatusError
        On unexpected HTTP error responses (not 404).
    """
    lexicon_key = LOGEION_LEXICON.get(language_code)
    if lexicon_key is None:
        return None

    encoded = urllib.parse.quote(lemma, safe="")
    url = f"{base_url}/lexica/{encoded}"

    async with httpx.AsyncClient(
        timeout=LOGEION_TIMEOUT_S,
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
    ) as client:
        resp = await client.get(url)

    if resp.status_code == 404:
        logger.debug("logeion 404 lemma=%r lang=%s", lemma, language_code)
        return None

    resp.raise_for_status()

    try:
        data: dict = resp.json()
    except ValueError:
        logger.warning("logeion invalid JSON for lemma=%r", lemma)
        return None

    return _extract_gloss(data, lexicon_key, lemma)


def _extract_gloss(data: dict, lexicon_key: str, lemma: str) -> str | None:
    """Extract a short plain-text gloss from a Logeion API response dict."""
    raw_html = data.get(lexicon_key) or ""
    if not raw_html or raw_html.strip() in ("", "none", "null"):
        return None

    plain = strip_html(raw_html).strip()
    if not plain or len(plain) <= 4:
        return None

    return plain[:_MAX_GLOSS_CHARS]
