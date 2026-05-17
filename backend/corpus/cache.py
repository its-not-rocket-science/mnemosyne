"""Local file cache for acquired corpus texts.

Cached files are stored under ``data/corpus_cache/{language}/{slug}.txt``.
The slug is derived from the entry's title (ASCII-safe, lower-cased, with
non-alphanumeric characters replaced by underscores).

A cached file is considered valid if it is non-empty.  To force a re-download,
delete the file or pass ``force=True`` to the acquisition functions.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

DEFAULT_CACHE_DIR = Path("data/corpus_cache")


def _slugify(text: str) -> str:
    """Convert *text* to a safe ASCII filename slug.

    Non-ASCII titles (CJK, Arabic, Hebrew, Greek, Cyrillic that fully drops out)
    fall back to a SHA-1 prefix so entries never collide on an empty slug.
    """
    import hashlib  # stdlib, lazy import fine here

    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")[:80]
    if not slug:
        slug = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
    return slug


def cache_path(language: str, title: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> Path:
    """Return the local cache path for a corpus entry."""
    return cache_dir / language / f"{_slugify(title)}.txt"


def is_cached(language: str, title: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> bool:
    """Return True if a non-empty cache file exists for this entry."""
    path = cache_path(language, title, cache_dir)
    return path.exists() and path.stat().st_size > 0


def read_cache(language: str, title: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> str:
    """Read and return cached text. Raises FileNotFoundError if not cached."""
    return cache_path(language, title, cache_dir).read_text(encoding="utf-8")


def write_cache(
    language: str,
    title: str,
    text: str,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> Path:
    """Write *text* to the local cache and return the path written."""
    path = cache_path(language, title, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
