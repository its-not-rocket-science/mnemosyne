"""Tests for corpus cache slug generation."""
from __future__ import annotations

from backend.corpus.cache import _slugify, cache_path
from pathlib import Path


def test_ascii_title():
    assert _slugify("Alice's Adventures in Wonderland") == "alice_s_adventures_in_wonderland"


def test_latin_with_accents():
    slug = _slugify("Candide, ou l'Optimisme")
    assert slug  # non-empty
    assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in slug)


def test_cjk_title_nonempty():
    slug = _slugify("注文の多い料理店")
    assert slug, "CJK title must not produce empty slug"


def test_cjk_titles_distinct():
    """Two different CJK titles must not collide on the same slug."""
    a = _slugify("注文の多い料理店")
    b = _slugify("羅生門")
    assert a != b, f"CJK slug collision: both produced {a!r}"


def test_arabic_title_nonempty():
    slug = _slugify("ألف ليلة وليلة (الجزء الأول)")
    assert slug


def test_hebrew_title_nonempty():
    slug = _slugify("מגילת רות")
    assert slug


def test_greek_title_nonempty():
    slug = _slugify("Κατὰ Ἰωάννην")
    assert slug


def test_cyrillic_title_nonempty():
    # Cyrillic degrades to empty via ASCII-ignore — must fall back to hash.
    slug = _slugify("Дама с собачкой")
    assert slug


def test_cache_path_distinct_for_cjk(tmp_path):
    p1 = cache_path("ja", "注文の多い料理店", cache_dir=tmp_path)
    p2 = cache_path("ja", "羅生門", cache_dir=tmp_path)
    assert p1 != p2
