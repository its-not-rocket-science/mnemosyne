"""Tests for the Logeion dictionary client."""
from __future__ import annotations

import pytest
import respx
import httpx

from backend.dictionary.logeion import (
    LOGEION_LEXICON,
    _extract_gloss,
    fetch_definition,
)

MOCK_BASE = "https://mock-logeion.test"


# ── _extract_gloss ────────────────────────────────────────────────────────────

class TestExtractGloss:
    def test_latin_returns_ls_key(self):
        data = {"ls": "<b>amor</b>, -oris, m. <i>love</i>, affection."}
        result = _extract_gloss(data, "ls", "amor")
        assert result is not None
        assert "love" in result

    def test_greek_returns_lsj_key(self):
        data = {"lsj": "<b>λόγος</b>, ὁ, <i>word</i>, reason."}
        result = _extract_gloss(data, "lsj", "λόγος")
        assert result is not None
        assert "word" in result

    def test_missing_key_returns_none(self):
        assert _extract_gloss({}, "ls", "amor") is None

    def test_empty_value_returns_none(self):
        assert _extract_gloss({"ls": ""}, "ls", "amor") is None
        assert _extract_gloss({"ls": "none"}, "ls", "amor") is None

    def test_strips_html_tags(self):
        data = {"ls": "<b>love</b>, warm affection."}
        result = _extract_gloss(data, "ls", "amor")
        assert "<b>" not in (result or "")

    def test_truncates_at_200_chars(self):
        long_text = "a" * 250
        data = {"ls": long_text}
        result = _extract_gloss(data, "ls", "amor")
        assert result is not None
        assert len(result) <= 200

    def test_very_short_gloss_returns_none(self):
        # 4 chars or fewer → None (not a useful gloss)
        data = {"ls": "foo"}
        assert _extract_gloss(data, "ls", "foo") is None


# ── fetch_definition ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unknown_language_returns_none_no_request():
    # No respx mock → would raise if request were made
    result = await fetch_definition("test", "es", base_url=MOCK_BASE)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_latin_returns_ls_gloss():
    respx.get(f"{MOCK_BASE}/lexica/amor").mock(
        return_value=httpx.Response(
            200,
            json={
                "ls": "<b>amor</b>, -oris, m. <i>love</i>, affection.",
                "lsj": "",
            },
        )
    )
    result = await fetch_definition("amor", "la", base_url=MOCK_BASE)
    assert result is not None
    assert "love" in result


@pytest.mark.asyncio
@respx.mock
async def test_greek_returns_lsj_gloss():
    respx.get(f"{MOCK_BASE}/lexica/%CE%BB%CF%8C%CE%B3%CE%BF%CF%82").mock(
        return_value=httpx.Response(
            200,
            json={
                "ls": "",
                "lsj": "<b>λόγος</b>, ὁ, <i>word</i>, reason.",
            },
        )
    )
    result = await fetch_definition("λόγος", "grc", base_url=MOCK_BASE)
    assert result is not None
    assert "word" in result


@pytest.mark.asyncio
@respx.mock
async def test_404_returns_none():
    respx.get(f"{MOCK_BASE}/lexica/xyzzy").mock(
        return_value=httpx.Response(404, json={"detail": "not found"})
    )
    result = await fetch_definition("xyzzy", "la", base_url=MOCK_BASE)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_empty_entry_returns_none():
    respx.get(f"{MOCK_BASE}/lexica/rarus").mock(
        return_value=httpx.Response(200, json={"ls": "", "lsj": ""})
    )
    result = await fetch_definition("rarus", "la", base_url=MOCK_BASE)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_raises_on_server_error():
    respx.get(f"{MOCK_BASE}/lexica/fail").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )
    with pytest.raises(httpx.HTTPStatusError):
        await fetch_definition("fail", "la", base_url=MOCK_BASE)


@pytest.mark.asyncio
@respx.mock
async def test_non_ascii_lemma_url_encoded():
    # ἀγαθός URL-encoded → %E1%BC%80%CE%B3%CE%B1%CE%B8%CF%8C%CF%82
    respx.get(f"{MOCK_BASE}/lexica/%E1%BC%80%CE%B3%CE%B1%CE%B8%CF%8C%CF%82").mock(
        return_value=httpx.Response(
            200,
            json={"lsj": "good, noble, brave."},
        )
    )
    result = await fetch_definition("ἀγαθός", "grc", base_url=MOCK_BASE)
    assert result is not None
    assert "good" in result


# ── LOGEION_LEXICON coverage ──────────────────────────────────────────────────

def test_logeion_covers_latin_and_greek():
    assert "la" in LOGEION_LEXICON
    assert "grc" in LOGEION_LEXICON
    assert LOGEION_LEXICON["la"] == "ls"
    assert LOGEION_LEXICON["grc"] == "lsj"
