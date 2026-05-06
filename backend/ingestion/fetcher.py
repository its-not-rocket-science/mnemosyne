"""Server-side URL fetcher and HTML text extractor.

Fetches a URL with httpx and extracts readable plain text using BeautifulSoup4.
This is the backend of the ``POST /fetch-url`` endpoint — the browser never
makes a cross-origin request for the remote page.

Security notes
--------------
Only http and https schemes are accepted.  A hard connect+read timeout and a
response-size cap prevent DoS via slow or enormous responses.

SSRF protection is implemented in :mod:`backend.ingestion.ssrf`.  Every
outbound request (including requests following redirects) is validated against
blocked address ranges (loopback, RFC-1918 private, link-local, multicast,
CGNAT, and the IPv6 equivalents) before the TCP connection is opened.  The
guard runs both on the initial URL and on every redirect destination, so a
redirect chain cannot be used to pivot to an internal address.

See ``ssrf.py`` for the known limitation regarding DNS-rebinding attacks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from backend.ingestion.ssrf import SSRFBlockedError, validate_url_ssrf  # noqa: F401 — re-exported

# Maximum raw response body accepted; larger responses are sliced before parsing.
_MAX_RESPONSE_BYTES: int = 2 * 1024 * 1024  # 2 MiB

# Seconds to wait for connect + first byte + full read.
_FETCH_TIMEOUT: float = 12.0

# Tags whose entire subtree is never useful for article text extraction.
_DISCARD_TAGS: frozenset[str] = frozenset({
    "script", "style", "noscript", "nav", "header", "footer",
    "aside", "figure", "figcaption", "form", "iframe", "svg",
    "button", "select", "option", "input", "textarea",
    "meta", "link", "picture", "video", "audio", "canvas",
})

# CSS selectors tried in order; first match is the extraction root.
# Falls back to <body> when none match.
_CONTENT_SELECTORS: list[str] = [
    "article",
    "[role='main']",
    "main",
    ".article-body",
    ".article-content",
    ".article__body",
    ".post-content",
    ".entry-content",
    ".story-body",
    "#article-body",
    "#content",
    "#main-content",
]


@dataclass(slots=True)
class FetchResult:
    title: str | None
    text: str
    final_url: str


async def fetch_and_extract(url: str) -> FetchResult:
    """Fetch *url* and return its extracted plain text and title.

    Args:
        url: The URL to fetch.  Must use the http or https scheme.

    Returns:
        A :class:`FetchResult` with the page title, extracted text, and the
        final URL after any redirects.

    Raises:
        ValueError: The URL scheme is not http or https.
        SSRFBlockedError: The URL (or a redirect destination) resolves to a
            blocked private or reserved address.
        httpx.HTTPStatusError: The server returned a 4xx or 5xx response.
        httpx.TimeoutException: No response within ``_FETCH_TIMEOUT`` seconds.
        httpx.RequestError: Any other network-level error.
    """
    # Pre-flight SSRF check on the initial URL.
    await validate_url_ssrf(url)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; Mnemosyne/0.1; +language-learning-tool)"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en,*;q=0.5",
    }

    async def _guard_request(request: httpx.Request) -> None:
        """Re-validate every request httpx makes, catching redirect pivots."""
        await validate_url_ssrf(str(request.url))

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(_FETCH_TIMEOUT),
        headers=headers,
        event_hooks={"request": [_guard_request]},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        # Bail on binary / non-HTML content types to avoid parsing PDFs etc.
        if content_type and not any(
            content_type.startswith(t) for t in ("text/", "application/xhtml")
        ):
            raise ValueError(
                f"The URL returned a non-text content type ({content_type!r}). "
                "Only HTML and plain-text pages are supported."
            )

        raw: bytes = response.content[:_MAX_RESPONSE_BYTES]
        final_url: str = str(response.url)

    # Detect encoding from raw bytes; fall back to utf-8.
    encoding = "utf-8"
    try:
        import chardet
        detected = chardet.detect(raw)
        encoding = detected.get("encoding") or "utf-8"
    except Exception:
        pass

    html = raw.decode(encoding, errors="replace")
    return _extract(html, final_url)


def _extract(html: str, url: str) -> FetchResult:
    """Parse *html* and return a :class:`FetchResult` with cleaned plain text."""
    soup = BeautifulSoup(html, "html.parser")

    # ── Title ─────────────────────────────────────────────────────────────────
    title: str | None = None
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        title = str(og["content"]).strip() or None
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip() or None
    # Strip trailing site-name suffixes like " | The Guardian" or " - BBC".
    if title:
        title = re.split(r"\s[|\-–—]\s", title)[0].strip() or title

    # ── Strip noisy subtrees ──────────────────────────────────────────────────
    for tag in soup.find_all(_DISCARD_TAGS):
        tag.decompose()

    # ── Locate the primary content region ────────────────────────────────────
    content_root = None
    for selector in _CONTENT_SELECTORS:
        content_root = soup.select_one(selector)
        if content_root:
            break
    if content_root is None:
        content_root = soup.body or soup

    # ── Extract and normalise plain text ─────────────────────────────────────
    raw_text = content_root.get_text(separator=" ")
    # Collapse non-newline whitespace runs into a single space.
    text = re.sub(r"[^\S\n]+", " ", raw_text)
    # Collapse three or more newlines into a paragraph break.
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return FetchResult(title=title, text=text, final_url=url)
