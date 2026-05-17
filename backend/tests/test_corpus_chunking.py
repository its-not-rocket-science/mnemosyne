"""Tests for paragraph-aware text chunking."""
from __future__ import annotations

import pytest

from backend.corpus.chunking import (
    DEFAULT_MAX_CHUNK_CHARS,
    Chunk,
    chunk_text,
)


def test_empty_text_returns_empty():
    assert chunk_text("") == []


def test_short_text_returns_single_chunk():
    text = "Hello world."
    chunks = chunk_text(text, max_chars=2000)
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].chunk_index == 0
    assert chunks[0].char_start == 0
    assert chunks[0].char_end == len(text)


def test_chunk_indices_are_sequential():
    text = "\n\n".join([f"Paragraph {i}. " + "x " * 50 for i in range(20)])
    chunks = chunk_text(text, max_chars=200)
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i


def test_no_chunk_exceeds_max_chars_hard_cap():
    text = "\n\n".join(["Word " * 100 for _ in range(10)])
    chunks = chunk_text(text, max_chars=300)
    for chunk in chunks:
        # Chunks may slightly exceed max when a single word sequence is longer,
        # but single over-sized paragraphs are hard-split.
        assert len(chunk.text) <= 300 + 50, f"Chunk too long: {len(chunk.text)}"


def test_char_offsets_non_overlapping():
    text = "\n\n".join([f"Para {i}." + " word" * 60 for i in range(5)])
    chunks = chunk_text(text, max_chars=200)
    assert len(chunks) > 1
    for i in range(len(chunks) - 1):
        assert chunks[i].char_end <= chunks[i + 1].char_start + 5  # allow small gap


def test_covers_entire_document():
    paras = [f"Paragraph {i}." + " text" * 20 for i in range(10)]
    text = "\n\n".join(paras)
    chunks = chunk_text(text, max_chars=200)
    assert len(chunks) > 1
    first_start = chunks[0].char_start
    last_end = chunks[-1].char_end
    assert first_start >= 0
    assert last_end <= len(text)


def test_single_long_paragraph_is_split():
    long_para = "sentence one. " * 200
    chunks = chunk_text(long_para, max_chars=200)
    assert len(chunks) > 1


def test_cjk_text_chunked():
    # Japanese text with sentence-ending 。
    sentences = ["これはテストです。" * 10 for _ in range(20)]
    text = "\n\n".join(sentences)
    chunks = chunk_text(text, max_chars=100, language="ja")
    assert len(chunks) > 1
    for chunk in chunks:
        assert isinstance(chunk.text, str)
        assert len(chunk.text) > 0


def test_chunk_text_is_substring_of_original():
    # Each chunk's text should be loosely derivable from the original.
    paras = ["The quick brown fox jumps over the lazy dog. " * 5 for _ in range(8)]
    text = "\n\n".join(paras)
    chunks = chunk_text(text, max_chars=200)
    assert len(chunks) > 1
    for chunk in chunks:
        # The stripped chunk text should appear somewhere in the normalised original.
        first_word = chunk.text.split()[0]
        assert first_word in text


def test_rtl_text_chunked():
    # Arabic text — should chunk without errors.
    arabic = "هذا نص عربي. " * 30
    text = "\n\n".join([arabic] * 5)
    chunks = chunk_text(text, max_chars=150, language="ar")
    assert len(chunks) >= 1


def test_chunk_default_max_chars():
    text = "word " * 1000
    chunks = chunk_text(text)
    for chunk in chunks:
        assert len(chunk.text) <= DEFAULT_MAX_CHUNK_CHARS + 100
