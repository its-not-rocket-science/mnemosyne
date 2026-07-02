"""Tests for the Logeion dictionary client."""
from __future__ import annotations

import pytest
import respx
import httpx

from backend.dictionary.logeion import (
    SUPPORTED_LANGUAGES,
    LOGEION_API_KEY,
    _extract_gloss,
    _build_url,
    fetch_definition,
)

MOCK_BASE = "https://mock-logeion.test"


def _detail_response(la_html: str = "", grc_html: str = "") -> dict:
    """Build a /detail-style JSON response for tests."""
    return {
        "detail": {
            "headword": None,
            "lewisshort": [la_html] if la_html else [],
            "dicos": [{"dname": "LSJ", "es": [grc_html]}] if grc_html else [],
            "shortdef": [],
        }
    }


def _mock_url(lemma: str, base: str = MOCK_BASE) -> str:
    return _build_url(lemma, base)


# ── _extract_gloss ────────────────────────────────────────────────────────────

class TestExtractGloss:
    def test_latin_returns_lewisshort(self):
        data = _detail_response(la_html="<b>amor</b>, -oris, m. <i>love</i>, affection.")
        result = _extract_gloss(data, "la", "amor")
        assert result is not None
        assert "love" in result

    def test_greek_returns_lsj_dico(self):
        data = _detail_response(grc_html="<b>λόγος</b>, ὁ, <i>word</i>, reason.")
        result = _extract_gloss(data, "grc", "λόγος")
        assert result is not None
        assert "word" in result

    def test_missing_data_returns_none(self):
        assert _extract_gloss({}, "la", "amor") is None

    def test_empty_lewisshort_returns_none(self):
        data = {"detail": {"lewisshort": [], "dicos": [], "shortdef": []}}
        assert _extract_gloss(data, "la", "amor") is None

    def test_strips_html_tags(self):
        data = _detail_response(la_html="<b>love</b>, warm affection.")
        result = _extract_gloss(data, "la", "amor")
        assert "<b>" not in (result or "")

    def test_truncates_at_200_chars(self):
        data = _detail_response(la_html="a" * 250)
        result = _extract_gloss(data, "la", "amor")
        assert result is not None
        assert len(result) <= 200

    def test_very_short_gloss_returns_none(self):
        data = _detail_response(la_html="foo")
        assert _extract_gloss(data, "la", "foo") is None


# ── fetch_definition ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unknown_language_returns_none_no_request():
    # No respx mock → would raise if request were made
    result = await fetch_definition("test", "es", base_url=MOCK_BASE)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_latin_returns_ls_gloss():
    url = _mock_url("amor")
    respx.get(url).mock(
        return_value=httpx.Response(200, json=_detail_response(
            la_html="<b>amor</b>, -oris, m. <i>love</i>, affection."
        ))
    )
    result = await fetch_definition("amor", "la", base_url=MOCK_BASE)
    assert result is not None
    assert "love" in result


@pytest.mark.asyncio
@respx.mock
async def test_greek_returns_lsj_gloss():
    url = _mock_url("λόγος")
    respx.get(url).mock(
        return_value=httpx.Response(200, json=_detail_response(
            grc_html="<b>λόγος</b>, ὁ, <i>word</i>, reason."
        ))
    )
    result = await fetch_definition("λόγος", "grc", base_url=MOCK_BASE)
    assert result is not None
    assert "word" in result


@pytest.mark.asyncio
@respx.mock
async def test_404_returns_none():
    url = _mock_url("xyzzy")
    respx.get(url).mock(return_value=httpx.Response(404, json={"detail": "not found"}))
    result = await fetch_definition("xyzzy", "la", base_url=MOCK_BASE)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_empty_entry_returns_none():
    url = _mock_url("rarus")
    respx.get(url).mock(
        return_value=httpx.Response(200, json=_detail_response())
    )
    result = await fetch_definition("rarus", "la", base_url=MOCK_BASE)
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_raises_on_server_error():
    url = _mock_url("fail")
    respx.get(url).mock(return_value=httpx.Response(500, text="Internal Server Error"))
    with pytest.raises(httpx.HTTPStatusError):
        await fetch_definition("fail", "la", base_url=MOCK_BASE)


@pytest.mark.asyncio
@respx.mock
async def test_non_ascii_lemma_url_encoded():
    url = _mock_url("ἀγαθός")
    respx.get(url).mock(
        return_value=httpx.Response(200, json=_detail_response(
            grc_html="good, noble, brave."
        ))
    )
    result = await fetch_definition("ἀγαθός", "grc", base_url=MOCK_BASE)
    assert result is not None
    assert "good" in result


# ── SUPPORTED_LANGUAGES coverage ──────────────────────────────────────────────

def test_supported_languages_covers_latin_and_greek():
    assert "la" in SUPPORTED_LANGUAGES
    assert "grc" in SUPPORTED_LANGUAGES
    assert "es" not in SUPPORTED_LANGUAGES
