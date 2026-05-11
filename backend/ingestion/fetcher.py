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
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag
from bs4.dammit import UnicodeDammit

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

_GUTENBERG_START_MARKERS: tuple[str, ...] = (
    "*** START OF THE PROJECT GUTENBERG EBOOK",
    "***START OF THE PROJECT GUTENBERG EBOOK",
    "START OF THE PROJECT GUTENBERG EBOOK",
)
_GUTENBERG_END_MARKERS: tuple[str, ...] = (
    "*** END OF THE PROJECT GUTENBERG EBOOK",
    "***END OF THE PROJECT GUTENBERG EBOOK",
    "END OF THE PROJECT GUTENBERG EBOOK",
    "End of the Project Gutenberg eBook",
)


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
    selector_candidates: list[Tag] = []
    for selector in _CONTENT_SELECTORS:
        node = soup.select_one(selector)
        if node:
            selector_candidates.append(node)

    best_overall = _best_content_block(soup)
    ranked_candidates = [*selector_candidates, *( [best_overall] if best_overall else [])]
    content_root = max(ranked_candidates, key=_node_content_score, default=None) or soup.body or soup

    # ── Extract and normalise plain text ─────────────────────────────────────
    text = _extract_readable_text(content_root)
    if _is_gutenberg_url(url):
        text = _clean_gutenberg_text(text)
    text = _clean_extracted_text(text)
    text = text.strip()

    return FetchResult(title=title, text=text, final_url=url)


def _best_content_block(soup: BeautifulSoup) -> Tag | None:
    candidates = soup.find_all(["article", "section", "div", "main"])
    if not candidates:
        return None

    best: tuple[float, Tag] | None = None
    for node in candidates:
        score = _node_content_score(node)
        if best is None or score > best[0]:
            best = (score, node)
    return best[1] if best else None


def _node_content_score(node: Tag) -> float:
    p_count = len(node.find_all("p"))
    text_len = len(node.get_text(" ", strip=True))
    link_len = len(" ".join(a.get_text(" ", strip=True) for a in node.find_all("a")))
    density = link_len / max(text_len, 1)
    score = (p_count * 40) + text_len - (density * 500)
    if _looks_like_footnotes(node):
        score -= 2000
    return score


def _looks_like_footnotes(node: Tag) -> bool:
    attrs = " ".join(
        str(x).lower()
        for x in [node.get("id", ""), " ".join(node.get("class", []))]
        if x
    )
    if any(k in attrs for k in ("footnote", "notes", "endnote")):
        return True
    headings = " ".join(
        h.get_text(" ", strip=True).lower() for h in node.find_all(["h1", "h2", "h3"], limit=3)
    )
    return "footnote" in headings or "notes" == headings.strip()


def _extract_readable_text(node: Tag) -> str:
    blocks: list[str] = []
    for elem in node.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote"]):
        line = elem.get_text(" ", strip=True)
        if not line:
            continue
        blocks.append(re.sub(r"[ \t]+", " ", line))
    if not blocks:
        fallback = node.get_text("\n", strip=True)
        fallback = re.sub(r"[ \t]+", " ", fallback)
        return re.sub(r"\n{3,}", "\n\n", fallback).strip()
    return "\n\n".join(blocks).strip()


def _clean_extracted_text(text: str) -> str:
    text = _decode_mojibake(text)
    text = _drop_promotional_lines(text)
    text = _normalize_reference_tokens(text)
    text = _drop_disclosure_markers(text)
    text = _dedupe_lines(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _decode_mojibake(text: str) -> str:
    # Attempt a latin-1 round-trip when we detect common UTF-8 mojibake markers.
    if not re.search(r"[ÃÂâ€]", text):
        return text
    try:
        repaired = text.encode("latin-1", errors="strict").decode("utf-8", errors="strict")
        if "�" not in repaired:
            return UnicodeDammit(repaired).unicode_markup
    except UnicodeError:
        pass
    return UnicodeDammit(text).unicode_markup


def _drop_promotional_lines(text: str) -> str:
    blocked_patterns = (
        r"^advertisement$",
        r"^receive a weekly dose of discovery in your inbox",
        r"^sign up to our .*newsletter",
        r"^subscribe to .*new scientist",
    )
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            kept.append("")
            continue
        if any(re.search(p, stripped, flags=re.IGNORECASE) for p in blocked_patterns):
            continue
        kept.append(line)
    return "\n".join(kept)


def _normalize_reference_tokens(text: str) -> str:
    text = re.sub(r"(10)\s*\.\s*(\d{4,9})\s*/\s*([A-Za-z0-9._;()/:+-]+)", r"\1.\2/\3", text)
    text = re.sub(r"(arXiv)\s*\.\s*(\d{4}\.\d{4,5})", r"\1.\2", text, flags=re.IGNORECASE)
    text = re.sub(r"(arXiv)\s*:\s*(\d{4}\.\d{4,5})", r"\1:\2", text, flags=re.IGNORECASE)
    text = re.sub(r"(10\.\d{4,9}/arXiv)\s*[\s.]+\s*(\d{4}\.\d{4,5})", r"\1.\2", text, flags=re.IGNORECASE)
    return text


def _drop_disclosure_markers(text: str) -> str:
    lines = []
    for line in text.splitlines():
        cleaned = re.sub(r"(^|\s)[▶►▸]\s*", " ", line).strip()
        lines.append(re.sub(r"\s{2,}", " ", cleaned))
    return "\n".join(lines)


def _dedupe_lines(text: str) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for line in text.splitlines():
        key = line.strip()
        if not key:
            out.append("")
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
    return "\n".join(out)


def _is_gutenberg_url(url: str) -> bool:
    return "gutenberg.org" in (urlparse(url).netloc or "").lower()


def _clean_gutenberg_text(text: str) -> str:
    start_idx = 0
    for marker in _GUTENBERG_START_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            nl = text.find("\n", idx)
            start_idx = nl + 1 if nl != -1 else idx + len(marker)
            break
    if start_idx:
        text = text[start_idx:]

    end_positions = [text.find(marker) for marker in _GUTENBERG_END_MARKERS if text.find(marker) != -1]
    if end_positions:
        text = text[: min(end_positions)]
    return text.strip()
