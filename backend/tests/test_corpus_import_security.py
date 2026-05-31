from __future__ import annotations

import httpx
import pytest
import respx
from fastapi import HTTPException

from backend.api.routes import sources
from backend.ingestion.ssrf import SSRFBlockedError


@pytest.mark.asyncio
@respx.mock
async def test_fetch_import_url_text_validates_initial_url(monkeypatch):
    calls: list[str] = []

    async def fake_validate(url: str) -> None:
        calls.append(url)

    monkeypatch.setattr(sources, "validate_url_ssrf", fake_validate)

    respx.get("https://example.test/article").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=b"<html><head><title>T</title></head><body><article><p>Hello world.</p></article></body></html>",
        )
    )

    fetched = await sources._fetch_import_url_text("https://example.test/article")

    assert calls
    assert calls[0] == "https://example.test/article"
    assert fetched.title == "T"
    assert "Hello world." in fetched.text
    assert fetched.final_url == "https://example.test/article"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_import_url_text_validates_redirect_targets(monkeypatch):
    calls: list[str] = []

    async def fake_validate(url: str) -> None:
        calls.append(url)
        if "127.0.0.1" in url:
            raise SSRFBlockedError("blocked redirect")

    monkeypatch.setattr(sources, "validate_url_ssrf", fake_validate)

    respx.get("https://example.test/redirect").mock(
        return_value=httpx.Response(
            302,
            headers={"location": "http://127.0.0.1/admin"},
        )
    )

    with pytest.raises(SSRFBlockedError, match="blocked redirect"):
        await sources._fetch_import_url_text("https://example.test/redirect")

    assert "https://example.test/redirect" in calls
    assert "http://127.0.0.1/admin" in calls


@pytest.mark.asyncio
@respx.mock
async def test_fetch_import_url_text_rejects_non_text_content_type(monkeypatch):
    async def fake_validate(url: str) -> None:
        return None

    monkeypatch.setattr(sources, "validate_url_ssrf", fake_validate)

    respx.get("https://example.test/file.pdf").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "application/pdf"},
            content=b"%PDF-1.7",
        )
    )

    with pytest.raises(ValueError, match="HTML or text"):
        await sources._fetch_import_url_text("https://example.test/file.pdf")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_import_url_text_hard_caps_streamed_bytes(monkeypatch):
    async def fake_validate(url: str) -> None:
        return None

    monkeypatch.setattr(sources, "validate_url_ssrf", fake_validate)
    monkeypatch.setattr(sources, "_URL_FETCH_MAX_BYTES", 8)

    respx.get("https://example.test/large").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"123456789",
        )
    )

    with pytest.raises(HTTPException) as exc:
        await sources._fetch_import_url_text("https://example.test/large")

    assert exc.value.status_code == 413


@pytest.mark.asyncio
@respx.mock
async def test_fetch_import_url_text_allows_plain_text(monkeypatch):
    async def fake_validate(url: str) -> None:
        return None

    monkeypatch.setattr(sources, "validate_url_ssrf", fake_validate)

    respx.get("https://example.test/plain.txt").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/plain; charset=utf-8"},
            content=b"Line one.\nLine two.",
        )
    )

    fetched = await sources._fetch_import_url_text("https://example.test/plain.txt")

    assert "Line one." in fetched.text
    assert fetched.final_url == "https://example.test/plain.txt"
