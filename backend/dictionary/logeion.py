"""Logeion lexicon API client for classical Latin and Greek glosses.

Fetches dictionary definitions from the Logeion aggregation service
(University of Chicago), which serves Lewis & Short (Latin) and
Liddell-Scott-Jones (Greek) entries via a JSON API.

API endpoint
────────────
    GET https://anastrophe.uchicago.edu/logeion-api/detail?w={lemma}&type=normal&key={KEY}

Response structure (simplified):
    {
      "detail": {
        "headword":   "amor",
        "lewisshort": ["<html-fragment>"],   # Lewis & Short — Latin
        "dicos":      [{"dname": "LSJ", "es": ["<html-fragment>"]}],  # Greek
        "shortdef":   ["amor, love, affection"]
      }
    }

For Latin we read ``detail.lewisshort[0]``; for Greek we read the first
``dicos`` entry where ``dname == "LSJ"``.

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

#: Languages handled by this module.
SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"la", "grc"})

#: Base URL for the Logeion API (override in tests).
LOGEION_BASE_URL = "https://anastrophe.uchicago.edu/logeion-api"

#: Firebase Web API key published in logeion.uchicago.edu JS bundle (public).
LOGEION_API_KEY = "AIzaSyCT5aVzk3Yx-m8FH8rmTpEgfVyVA3pYbqg"

#: HTTP timeout in seconds.
LOGEION_TIMEOUT_S = 8.0

#: Maximum plain-text characters returned as a gloss.
_MAX_GLOSS_CHARS = 200

_USER_AGENT = "Mnemosyne/1.0 (language learning app; https://github.com/mnemosyne)"

_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Referer": "https://logeion.uchicago.edu/",
}


def _build_url(lemma: str, base_url: str) -> str:
    encoded = urllib.parse.quote(lemma, safe="")
    return f"{base_url}/detail?w={encoded}&type=normal&key={LOGEION_API_KEY}"


def _raw_html_from_response(data: dict, language_code: str) -> str:
    """Extract raw HTML lexicon entry from a /detail response dict."""
    detail = data.get("detail") or {}
    if language_code == "la":
        ls = detail.get("lewisshort") or []
        if ls and isinstance(ls[0], str):
            return ls[0]
        # shortdef as plain-text fallback (no HTML)
        sd = detail.get("shortdef") or []
        return sd[0] if sd and isinstance(sd[0], str) else ""
    else:  # grc
        for entry in (detail.get("dicos") or []):
            if isinstance(entry, dict) and entry.get("dname") in ("LSJ", "lsj"):
                es = entry.get("es") or []
                if es and isinstance(es[0], str):
                    return es[0]
        sd = detail.get("shortdef") or []
        return sd[0] if sd and isinstance(sd[0], str) else ""


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
    if language_code not in SUPPORTED_LANGUAGES:
        return None

    url = _build_url(lemma, base_url)

    async with httpx.AsyncClient(
        timeout=LOGEION_TIMEOUT_S,
        headers=_HEADERS,
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

    raw_html = _raw_html_from_response(data, language_code)
    if not raw_html:
        return None

    plain = strip_html(raw_html).strip()
    if not plain or len(plain) <= 4:
        return None

    return plain[:_MAX_GLOSS_CHARS]


def _extract_gloss(data: dict, language_code: str, lemma: str) -> str | None:
    """Extract a short plain-text gloss from a Logeion /detail response dict."""
    raw_html = _raw_html_from_response(data, language_code)
    if not raw_html:
        return None
    plain = strip_html(raw_html).strip()
    if not plain or len(plain) <= 4:
        return None
    return plain[:_MAX_GLOSS_CHARS]


# ── Structured extraction ─────────────────────────────────────────────────────

_CITATION_ABBREVS: dict[str, str] = {
    # Latin — prose
    "Cic.": "Cicero", "Caes.": "Caesar", "Liv.": "Livy",
    "Tac.": "Tacitus", "Sal.": "Sallust", "Quint.": "Quintilian",
    "Plin.": "Pliny", "Plin. N.": "Pliny the Elder",
    "Sen.": "Seneca", "Gell.": "Aulus Gellius",
    "Varr.": "Varro", "Nep.": "Cornelius Nepos",
    "App.": "Appian", "Suet.": "Suetonius",
    "Curt.": "Curtius", "Just.": "Justinus",
    "Fest.": "Festus", "Non.": "Nonius",
    "Apul.": "Apuleius", "Aug.": "Augustine",
    "Hier.": "Jerome", "Ambr.": "Ambrose",
    "Ter.": "Terence", "Plaut.": "Plautus",
    # Latin — poetry
    "Verg.": "Virgil", "Ov.": "Ovid", "Hor.": "Horace",
    "Juv.": "Juvenal", "Mart.": "Martial", "Cat.": "Catullus",
    "Lucr.": "Lucretius", "Stat.": "Statius",
    "Prop.": "Propertius", "Tib.": "Tibullus",
    "Luc.": "Lucan", "Sil.": "Silius Italicus",
    "Val.": "Valerius Flaccus",
    # Greek
    "Thuc.": "Thucydides", "Plat.": "Plato", "Arist.": "Aristotle",
    "Hdt.": "Herodotus", "Xen.": "Xenophon", "Hom.": "Homer",
    "Soph.": "Sophocles", "Eur.": "Euripides", "Aesch.": "Aeschylus",
    "Dem.": "Demosthenes", "Pind.": "Pindar",
    "Polyb.": "Polybius", "Diod.": "Diodorus Siculus",
    "Plut.": "Plutarch", "Luc.": "Lucian",
    "Arr.": "Arrian", "App.": "Appian",
    "D.C.": "Cassius Dio", "Strab.": "Strabo",
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


# Latin POS/gender detection patterns (applied to first 200 chars of plain text)
_LA_VERB_RE = re.compile(r"\bv\.\s*(?:a|n|dep|freq|intens|inch|impers|semidep)\.")
_LA_ADJ_RE  = re.compile(r"\badj\.")
_LA_ADV_RE  = re.compile(r"\badv\.")
_LA_NOUN_GENDER_RE = re.compile(r",\s*([mfn])\.")

# Greek definite articles that mark noun gender in LSJ entries
_GRC_MASC = ("ὁ", "ὁ")   # ὁ  (with smooth breathing)
_GRC_FEM  = ("ἡ",)             # ἡ  (with rough breathing)
_GRC_NEUT = ("τό", "τό")  # τό

_GENDER_NAMES = {"m": "masculine", "f": "feminine", "n": "neuter"}


def _extract_morphology(plain: str, lang: str) -> dict:
    """Extract part_of_speech and gender from an L&S/LSJ entry header.

    Returns a (possibly empty) dict with keys ``part_of_speech`` and/or
    ``gender``.  Best-effort: returns empty dict when pattern is unclear.
    """
    header = plain[:200]
    result: dict = {}

    if lang == "la":
        if _LA_VERB_RE.search(header):
            result["part_of_speech"] = "verb"
        elif _LA_ADJ_RE.search(header):
            result["part_of_speech"] = "adjective"
        elif _LA_ADV_RE.search(header):
            result["part_of_speech"] = "adverb"
        else:
            m = _LA_NOUN_GENDER_RE.search(header)
            if m:
                result["part_of_speech"] = "noun"
                result["gender"] = _GENDER_NAMES[m.group(1)]
    elif lang == "grc":
        if any(a in header for a in _GRC_MASC):
            result["part_of_speech"] = "noun"
            result["gender"] = "masculine"
        elif any(a in header for a in _GRC_FEM):
            result["part_of_speech"] = "noun"
            result["gender"] = "feminine"
        elif any(a in header for a in _GRC_NEUT):
            result["part_of_speech"] = "noun"
            result["gender"] = "neuter"

    return result


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
    if language_code not in SUPPORTED_LANGUAGES:
        return None

    cached = _cache_get(lemma, language_code)
    if cached is not None:
        return cached

    url = _build_url(lemma, base_url)

    async with httpx.AsyncClient(
        timeout=LOGEION_TIMEOUT_S,
        headers=_HEADERS,
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
    raw_html = _raw_html_from_response(data, language_code)
    plain = strip_html(raw_html).strip() if raw_html else ""

    if not plain:
        return None

    morphology = _extract_morphology(plain, language_code)
    result: dict = {
        "gloss": plain[:_MAX_GLOSS_CHARS],
        "ls_definition": _extract_primary_definition(plain),
        "classical_citations": _extract_citations(raw_html),
        "compound_words": _extract_compounds(raw_html),
        "lexicon_source": lexicon_source,
        **morphology,
    }

    _cache_set(lemma, language_code, result)
    return result
