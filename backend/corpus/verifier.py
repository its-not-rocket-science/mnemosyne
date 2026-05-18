"""URL verification for the corpus manifest.

Each URL is checked with a HEAD request (falling back to GET on 405/403).
Results are:
  ok          — HTTP 200, content-length above minimum, no disambiguation detected.
  short       — HTTP 200 but body too short (likely index or disambiguation page).
  not_found   — HTTP 404 or PG "not found" body pattern.
  error       — Other HTTP error or network failure.
  manual      — Entry is flagged manual_review=True; not auto-verified.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

import httpx

from backend.corpus.manifest import CorpusEntry

logger = logging.getLogger(__name__)

_TIMEOUT = 20
_MIN_CONTENT_BYTES = 500
_USER_AGENT = (
    "MnemosyneCorpus/0.1 "
    "(https://github.com/example/mnemosyne; corpus-pipeline bot)"
)

# Patterns that indicate an index/disambiguation Wikisource page.
_WIKISOURCE_INDEX_PATTERNS = (
    re.compile(r"Diese Seite ist eine Weiterleitungsseite", re.IGNORECASE),
    re.compile(r"disambiguation", re.IGNORECASE),
    re.compile(r"Begriffsklärung", re.IGNORECASE),
    re.compile(r"<div[^>]+class=[\"'][^\"']*mw-disambig", re.IGNORECASE),
)

# Project Gutenberg "not found" patterns.
_PG_NOT_FOUND_PATTERNS = (
    re.compile(r"No ebook by that number", re.IGNORECASE),
    re.compile(r"We're sorry, but we couldn't find", re.IGNORECASE),
)

VerifyStatus = Literal["ok", "short", "not_found", "error", "manual"]


@dataclass
class VerifyResult:
    entry: CorpusEntry
    status: VerifyStatus
    url: str
    content_bytes: int = 0
    http_status: int = 0
    message: str = ""


def _head_then_get(client: httpx.Client, url: str) -> tuple[int, bytes, str]:
    """Issue HEAD; fall back to GET if HEAD is not supported."""
    try:
        r = client.head(url, follow_redirects=True)
        if r.status_code in (405, 403):
            raise httpx.HTTPStatusError("HEAD not supported", request=r.request, response=r)
        r.raise_for_status()
        # HEAD confirmed accessible; do GET to check body.
        r2 = client.get(url, follow_redirects=True)
        r2.raise_for_status()
        return r2.status_code, r2.content, r2.text
    except httpx.HTTPStatusError:
        r2 = client.get(url, follow_redirects=True)
        r2.raise_for_status()
        return r2.status_code, r2.content, r2.text


def verify_entry(entry: CorpusEntry) -> VerifyResult:
    """Synchronously verify one manifest entry's source URL."""
    if entry.manual_review:
        return VerifyResult(
            entry=entry,
            status="manual",
            url=entry.source_url,
            message="manual_review flag set; skipping automated check",
        )

    headers = {"User-Agent": _USER_AGENT}
    try:
        with httpx.Client(timeout=_TIMEOUT, headers=headers) as client:
            status_code, body_bytes, body_text = _head_then_get(client, entry.source_url)
    except httpx.HTTPStatusError as exc:
        http_status = exc.response.status_code
        if http_status == 404:
            return VerifyResult(
                entry=entry, status="not_found",
                url=entry.source_url, http_status=http_status,
                message=f"HTTP 404",
            )
        return VerifyResult(
            entry=entry, status="error",
            url=entry.source_url, http_status=http_status,
            message=f"HTTP {http_status}",
        )
    except httpx.RequestError as exc:
        return VerifyResult(
            entry=entry, status="error",
            url=entry.source_url,
            message=f"Network error: {exc}",
        )

    n_bytes = len(body_bytes)

    # Project Gutenberg "not found" body check.
    for pat in _PG_NOT_FOUND_PATTERNS:
        if pat.search(body_text[:4000]):
            return VerifyResult(
                entry=entry, status="not_found",
                url=entry.source_url, http_status=status_code,
                content_bytes=n_bytes,
                message="PG 'not found' pattern in body",
            )

    # Wikisource disambiguation / index page check.
    for pat in _WIKISOURCE_INDEX_PATTERNS:
        if pat.search(body_text[:8000]):
            return VerifyResult(
                entry=entry, status="short",
                url=entry.source_url, http_status=status_code,
                content_bytes=n_bytes,
                message="Wikisource disambiguation/index page detected",
            )

    # Minimum content length check.
    if n_bytes < _MIN_CONTENT_BYTES:
        return VerifyResult(
            entry=entry, status="short",
            url=entry.source_url, http_status=status_code,
            content_bytes=n_bytes,
            message=f"Body only {n_bytes} bytes (min {_MIN_CONTENT_BYTES})",
        )

    return VerifyResult(
        entry=entry, status="ok",
        url=entry.source_url, http_status=status_code,
        content_bytes=n_bytes,
    )
