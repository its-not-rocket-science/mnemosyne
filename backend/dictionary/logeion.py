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

import json
import logging
import re
import sqlite3
import urllib.parse
from pathlib import Path

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


# ── Structured extraction ─────────────────────────────────────────────────────

_CITATION_ABBREVS: dict[str, str] = {
    # Latin
    "Cic.": "Cicero", "Verg.": "Virgil", "Ov.": "Ovid",
    "Hor.": "Horace", "Liv.": "Livy", "Tac.": "Tacitus",
    "Caes.": "Caesar", "Sal.": "Sallust", "Plin.": "Pliny",
    "Quint.": "Quintilian", "Sen.": "Seneca", "Juv.": "Juvenal",
    "Mart.": "Martial", "Cat.": "Catullus", "Lucr.": "Lucretius",
    # Greek
    "Thuc.": "Thucydides", "Plat.": "Plato", "Arist.": "Aristotle",
    "Hdt.": "Herodotus", "Xen.": "Xenophon", "Hom.": "Homer",
    "Soph.": "Sophocles", "Eur.": "Euripides", "Aesch.": "Aeschylus",
    "Dem.": "Demosthenes", "Pind.": "Pindar",
}

_CITATION_RE = re.compile(
    r"([A-Z][a-z]+\.(?:\s+[A-Za-z]+\.)*)\s*([\d,\.\s]+)",
    re.UNICODE,
)


def _extract_primary_definition(plain: str) -> str | None:
    if not plain:
        return None
    for sep in (";", "I.", "1.", "A."):
        if sep in plain:
            candidate = plain.split(sep)[0].strip()
            if 10 < len(candidate) < 600:
                return candidate
    return plain[:600] if len(plain) > 10 else None


def _extract_citations(html: str) -> list[dict]:
    plain = strip_html(html)
    seen: set[str] = set()
    results: list[dict] = []
    for m in _CITATION_RE.finditer(plain):
        abbr = m.group(1).strip()
        ref = m.group(2).strip().rstrip(",")
        key = abbr + ref
        if key in seen or abbr not in _CITATION_ABBREVS:
            continue
        seen.add(key)
        results.append({
            "abbreviated": f"{abbr} {ref}",
            "author": _CITATION_ABBREVS[abbr],
            "work": "",
            "ref": ref,
        })
        if len(results) >= 5:
            break
    return results


def _extract_compounds(html: str) -> list[str]:
    plain = strip_html(html)
    match = re.search(
        r"(?:COMP(?:OUNDS)?\.?|comp\.?)\s*[:–]?\s*(.+?)(?:\n|$)",
        plain,
        re.IGNORECASE,
    )
    if not match:
        return []
    compounds = [c.strip() for c in re.split(r"[,;]", match.group(1))]
    return [c for c in compounds if 2 < len(c) < 30][:8]


# ── SQLite cache ──────────────────────────────────────────────────────────────

_CACHE_PATH = (
    Path(__file__).resolve().parents[2] / "backend" / "cache" / "logeion_cache.db"
)
_cache_conn: sqlite3.Connection | None = None


def _open_cache() -> sqlite3.Connection | None:
    global _cache_conn
    if _cache_conn is not None:
        return _cache_conn
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_CACHE_PATH), check_same_thread=False, timeout=2.0)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS logeion_structured (
              language   TEXT NOT NULL,
              lemma      TEXT NOT NULL,
              payload    TEXT NOT NULL,
              fetched_at TEXT NOT NULL,
              PRIMARY KEY (language, lemma)
            )
        """)
        conn.commit()
        _cache_conn = conn
        return conn
    except Exception:
        return None


def _cache_get(lemma: str, language: str) -> dict | None:
    conn = _open_cache()
    if conn is None:
        return None
    try:
        row = conn.execute(
            "SELECT payload FROM logeion_structured WHERE language=? AND lemma=?",
            (language, lemma.lower()),
        ).fetchone()
        return json.loads(row[0]) if row else None
    except Exception:
        return None


def _cache_set(lemma: str, language: str, data: dict) -> None:
    conn = _open_cache()
    if conn is None:
        return
    try:
        conn.execute(
            """INSERT OR REPLACE INTO logeion_structured
               (language, lemma, payload, fetched_at)
               VALUES (?, ?, ?, datetime('now'))""",
            (language, lemma.lower(), json.dumps(data, ensure_ascii=False)),
        )
        conn.commit()
    except Exception:
        pass


async def fetch_structured(
    lemma: str,
    language_code: str,
    *,
    base_url: str = LOGEION_BASE_URL,
) -> dict | None:
    """Return a structured lexicon entry dict for lemma, or None.

    Keys: gloss, ls_definition, classical_citations, compound_words, lexicon_source.
    Results are cached in a SQLite DB at backend/cache/logeion_cache.db.
    """
    lexicon_key = LOGEION_LEXICON.get(language_code)
    if lexicon_key is None:
        return None

    cached = _cache_get(lemma, language_code)
    if cached is not None:
        return cached

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
        data = resp.json()
    except ValueError:
        logger.warning("logeion invalid JSON for lemma=%r", lemma)
        return None

    lexicon_source = "Lewis & Short" if language_code == "la" else "Liddell-Scott-Jones"
    raw_html = data.get(lexicon_key) or ""
    plain = strip_html(raw_html).strip()

    result: dict = {
        "gloss": plain[:_MAX_GLOSS_CHARS] if plain else None,
        "ls_definition": _extract_primary_definition(plain),
        "classical_citations": _extract_citations(raw_html),
        "compound_words": _extract_compounds(raw_html),
        "lexicon_source": lexicon_source,
    }

    _cache_set(lemma, language_code, result)
    return result
