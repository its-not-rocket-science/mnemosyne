"""Tests for corpus text normalisation."""
from __future__ import annotations

import pytest

from backend.corpus.normalize import normalize_corpus_text


def test_basic_normalization():
    text = "  Hello world.  "
    normalised, warnings = normalize_corpus_text(text, "en")
    assert normalised == "Hello world."
    assert isinstance(warnings, list)


def test_nfc_normalization():
    # Café with combining accent (NFD) should become NFC.
    nfd = "café"
    normalised, _ = normalize_corpus_text(nfd, "fr")
    assert normalised == "café"


def test_empty_text_raises():
    with pytest.raises(ValueError, match="empty"):
        normalize_corpus_text("   ", "en")


def test_script_mismatch_produces_warning():
    # Arabic script text submitted as English should produce a script warning.
    # (Latin text under Arabic is allowed — covers transliteration. Reverse direction warns.)
    arabic_text = "مرحبا بالعالم. هذا نص عربي طويل بما فيه الكفاية لاختبار اكتشاف الخط."
    _, warnings = normalize_corpus_text(arabic_text, "en")
    assert any("script" in w.lower() or "arabic" in w.lower() for w in warnings), (
        f"Expected script-mismatch warning, got: {warnings}"
    )


def test_no_warning_for_matching_script():
    _, warnings = normalize_corpus_text("Hola, ¿cómo estás?", "es")
    assert not warnings


def test_cyrillic_russian_no_warning():
    _, warnings = normalize_corpus_text("Привет, мир!", "ru")
    assert not warnings


def test_returns_tuple():
    result = normalize_corpus_text("Test text.", "en")
    assert len(result) == 2
    assert isinstance(result[0], str)
    assert isinstance(result[1], list)
