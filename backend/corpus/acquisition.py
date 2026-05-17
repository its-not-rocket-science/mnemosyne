"""Download and extract plain text from corpus source URLs.

Handles three source types automatically:
  - Project Gutenberg plain text (strips PG header/footer boilerplate)
  - Aozora Bunko HTML (strips ruby/furigana markup, extracts main_text div)
  - MediaWiki raw wikitext (strips templates, links, headings)
  - Generic HTML (BeautifulSoup get_text fallback)
  - Plain text (used as-is after encoding normalisation)

All functions are synchronous (no async I/O) and are meant to be called from
``asyncio.to_thread`` in the build pipeline.
"""
from __future__ import annotations

import logging
import re
from typing import Callable

import httpx

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 30  # seconds
_MAX_RESPONSE_BYTES = 20 * 1024 * 1024  # 20 MB hard cap

# Project Gutenberg boilerplate markers (matched case-insensitively).
_PG_START_MARKERS = (
    "*** START OF THE PROJECT GUTENBERG EBOOK",
    "***START OF THE PROJECT GUTENBERG EBOOK",
    "* START OF THIS PROJECT GUTENBERG EBOOK",
)
_PG_END_MARKERS = (
    "*** END OF THE PROJECT GUTENBERG EBOOK",
    "***END OF THE PROJECT GUTENBERG EBOOK",
    "End of the Project Gutenberg",
    "End of Project Gutenberg",
)


def _strip_gutenberg(text: str) -> str:
    """Remove PG header and footer boilerplate from a plain-text PG file."""
    upper = text.upper()
    start = 0
    for marker in _PG_START_MARKERS:
        idx = upper.find(marker.upper())
        if idx != -1:
            line_end = text.find("\n", idx)
            start = (line_end + 1) if line_end != -1 else idx + len(marker)
            break

    end = len(text)
    for marker in _PG_END_MARKERS:
        idx = upper.find(marker.upper(), start)
        if idx != -1:
            end = idx
            break

    return text[start:end].strip()


def _strip_aozora_html(html: str) -> str:
    """Extract plain text from an Aozora Bunko HTML file.

    Strips <rt> (furigana readings) and <rp> (ruby parentheses) tags so that
    only the base kanji remain.  Falls back to the full body text if the
    expected ``.main_text`` container is not found.
    """
    from bs4 import BeautifulSoup  # noqa: PLC0415  (already a project dep)

    soup = BeautifulSoup(html, "html.parser")

    # Drop all furigana readings to keep only base characters.
    for tag in soup.find_all(["rt", "rp"]):
        tag.decompose()

    main = soup.find("div", class_="main_text")
    if main:
        return main.get_text("\n", strip=True)

    body = soup.find("body")
    return (body or soup).get_text("\n", strip=True)


def _strip_mediawiki(text: str) -> str:
    """Strip common MediaWiki markup from a ``?action=raw`` response."""
    # Templates: {{...}} (non-greedy, may nest shallowly)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    # Wiki links: [[target|display]] → display, [[target]] → target
    text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", text)
    # File/Category/Image links
    text = re.sub(r"\[\[(?:File|Image|Category):[^\]]*\]\]", "", text, flags=re.IGNORECASE)
    # Headings: == text == → text
    text = re.sub(r"={2,}([^=\n]+)={2,}", r"\1", text)
    # Bold / italic
    text = re.sub(r"'{2,}", "", text)
    # External links: [http://... label] → label
    text = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", text)
    # Horizontal rules
    text = re.sub(r"^-{4,}$", "", text, flags=re.MULTILINE)
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _generic_html(html: str) -> str:
    """Extract visible text from arbitrary HTML via BeautifulSoup."""
    from bs4 import BeautifulSoup  # noqa: PLC0415

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def _detect_format(content: str, url: str, content_type_header: str) -> str:
    """Return one of: 'aozora_html', 'html', 'mediawiki', 'gutenberg', 'plain'."""
    if "aozora.gr.jp" in url and ("<html" in content[:2000].lower()):
        return "aozora_html"
    if content.lstrip().startswith("<") and "<html" in content[:1000].lower():
        return "html"
    if "{{" in content[:500] or content.lstrip().startswith("{{"):
        return "mediawiki"
    if any(m.upper() in content[:3000].upper() for m in _PG_START_MARKERS):
        return "gutenberg"
    # Some PG files have no START marker but have the END marker and a long preamble.
    if any(m.upper() in content.upper() for m in _PG_END_MARKERS):
        return "gutenberg"
    return "plain"


_EXTRACTORS: dict[str, Callable[[str], str]] = {
    "aozora_html": _strip_aozora_html,
    "html":        _generic_html,
    "mediawiki":   _strip_mediawiki,
    "gutenberg":   _strip_gutenberg,
    "plain":       lambda t: t,
}


def fetch_text(url: str) -> str:
    """Download *url* and return extracted plain text.

    Raises:
        httpx.HTTPStatusError: on 4xx/5xx responses.
        httpx.RequestError:    on connection / timeout errors.
        ValueError:            if the response body exceeds the size cap.
    """
    logger.info("corpus acquire url=%s", url)
    with httpx.Client(timeout=_REQUEST_TIMEOUT, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()

        raw_bytes = response.content
        if len(raw_bytes) > _MAX_RESPONSE_BYTES:
            raise ValueError(
                f"Response from {url} is {len(raw_bytes):,} bytes; "
                f"cap is {_MAX_RESPONSE_BYTES:,}."
            )

        # Decode — try response charset, then UTF-8, then latin-1.
        for encoding in (response.encoding, "utf-8", "latin-1"):
            if encoding:
                try:
                    raw_text = raw_bytes.decode(encoding)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
        else:
            raw_text = raw_bytes.decode("utf-8", errors="replace")

    content_type_header = response.headers.get("content-type", "")
    fmt = _detect_format(raw_text, url, content_type_header)
    logger.debug("corpus acquire format=%s url=%s", fmt, url)
    return _EXTRACTORS[fmt](raw_text)
