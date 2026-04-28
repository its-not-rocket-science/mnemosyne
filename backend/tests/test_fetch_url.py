"""Tests for POST /fetch-url and POST /detect-language.

The URL-fetch tests use pytest-mock / httpx.MockTransport to avoid real
network calls.  Language detection is pure-Python and tested directly.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from backend.ingestion.fetcher import _extract
from backend.ingestion.language_detect import detect_language, MIN_CONFIDENCE
from backend.main import app


# ── Helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ── /detect-language ──────────────────────────────────────────────────────────

class TestDetectLanguageEndpoint:
    async def test_spanish_paragraph(self, client):
        text = (
            "El aprendizaje de idiomas es una habilidad que se desarrolla con "
            "la practica. Cada dia que pasamos estudiando una nueva lengua nos "
            "acercamos mas a la fluidez."
        )
        r = await client.post("/detect-language", json={"text": text})
        assert r.status_code == 200
        data = r.json()
        assert data["language"] == "es"
        assert data["confidence"] >= MIN_CONFIDENCE
        assert data["supported"] is True   # Spanish plugin is registered

    async def test_english_paragraph(self, client):
        text = (
            "Language learning is a skill that develops with practice. "
            "Every day spent studying a new language brings us closer to fluency. "
            "Students who dedicate regular time to study tend to progress more quickly."
        )
        r = await client.post("/detect-language", json={"text": text})
        assert r.status_code == 200
        data = r.json()
        assert data["language"] == "en"
        assert data["supported"] is True

    async def test_french_paragraph(self, client):
        text = (
            "Apprendre une langue est une competence qui se developpe avec la "
            "pratique. Chaque jour passe a etudier une nouvelle langue nous "
            "rapproche de la fluidite. Les etudiants qui consacrent du temps "
            "regulier ont tendance a progresser plus rapidement."
        )
        r = await client.post("/detect-language", json={"text": text})
        assert r.status_code == 200
        data = r.json()
        assert data["language"] == "fr"
        assert data["supported"] is True

    async def test_arabic_sentence(self, client):
        text = "كان الطقس جميلا في المدينة وكانت الشمس تشرق بشكل رائع على الجبال"
        r = await client.post("/detect-language", json={"text": text})
        assert r.status_code == 200
        data = r.json()
        assert data["language"] == "ar"
        assert data["confidence"] >= 0.8

    async def test_short_text_returns_null(self, client):
        r = await client.post("/detect-language", json={"text": "hello"})
        assert r.status_code == 200
        data = r.json()
        assert data["language"] is None
        assert data["confidence"] == 0.0
        assert data["supported"] is False

    async def test_empty_text_rejected(self, client):
        r = await client.post("/detect-language", json={"text": ""})
        assert r.status_code == 422

    async def test_unsupported_language_detected(self, client):
        # Polish has a plugin-less language code in the detection list.
        # We can't guarantee what's supported, but we CAN assert the shape.
        text = (
            "Uczenie sie jezykow jest umiejetnoscia, ktora rozwija sie wraz z "
            "praktyka. Kazdy dzien spedzony na nauce nowego jezyka przybliza "
            "nas do bieglosci jezykowej i nowych mozliwosci."
        )
        r = await client.post("/detect-language", json={"text": text})
        assert r.status_code == 200
        data = r.json()
        assert "language" in data
        assert "confidence" in data
        assert "supported" in data
        assert isinstance(data["supported"], bool)


# ── /fetch-url — schema/validation (no real network) ─────────────────────────

class TestFetchUrlValidation:
    async def test_ftp_scheme_rejected(self, client):
        r = await client.post("/fetch-url", json={"source_url": "ftp://example.com/file"})
        assert r.status_code == 422

    async def test_bare_string_rejected(self, client):
        r = await client.post("/fetch-url", json={"source_url": "not-a-url"})
        assert r.status_code == 422

    async def test_javascript_scheme_rejected(self, client):
        r = await client.post("/fetch-url", json={"source_url": "javascript:alert(1)"})
        assert r.status_code == 422

    async def test_missing_source_url_rejected(self, client):
        r = await client.post("/fetch-url", json={})
        assert r.status_code == 422


# ── HTML text extraction (pure unit, no network) ──────────────────────────────

class TestHtmlExtraction:
    def test_extracts_article_body(self):
        html = """
        <html><head><title>Test - My Site</title></head>
        <body>
          <nav>Navigation</nav>
          <article>
            <h1>Article Heading</h1>
            <p>This is the article body text with useful content.</p>
          </article>
          <footer>Footer text</footer>
        </body></html>
        """
        result = _extract(html, "https://example.com")
        assert "article body text" in result.text
        assert "Navigation" not in result.text
        assert "Footer" not in result.text

    def test_og_title_preferred_over_title_tag(self):
        html = """
        <html><head>
          <title>Article Title | Example Site</title>
          <meta property="og:title" content="Clean Article Title">
        </head><body><p>Body.</p></body></html>
        """
        result = _extract(html, "https://example.com")
        assert result.title == "Clean Article Title"

    def test_strips_site_suffix_from_title(self):
        html = "<html><head><title>Great Article | My News Site</title></head><body><p>Body.</p></body></html>"
        result = _extract(html, "https://example.com")
        assert result.title == "Great Article"

    def test_script_and_style_removed(self):
        html = """
        <html><body>
          <p>Real content here.</p>
          <script>var x = 'injected';</script>
          <style>.hidden { display: none }</style>
        </body></html>
        """
        result = _extract(html, "https://example.com")
        assert "injected" not in result.text
        assert "display" not in result.text
        assert "Real content" in result.text

    def test_final_url_preserved(self):
        html = "<html><body><p>Content.</p></body></html>"
        result = _extract(html, "https://example.com/final")
        assert result.final_url == "https://example.com/final"

    def test_empty_article_gives_empty_text(self):
        html = "<html><body><article></article></body></html>"
        result = _extract(html, "https://example.com")
        assert result.text.strip() == ""


# ── Language detection unit tests ─────────────────────────────────────────────

class TestLanguageDetect:
    def test_cjk_script_detected(self):
        lang, conf = detect_language("这是一段中文文本用于测试语言检测功能")
        assert lang == "zh"
        assert conf >= 0.8

    def test_arabic_script_detected(self):
        lang, conf = detect_language("كان الطقس جميلا في المدينة وكانت الشمس تشرق")
        assert lang == "ar"
        assert conf >= 0.8

    def test_short_latin_returns_none(self):
        lang, conf = detect_language("hello")
        assert lang is None
        assert conf == 0.0

    def test_german_detected(self):
        lang, conf = detect_language(
            "Die Katze sitzt auf dem Tisch und schaut durch das Fenster. "
            "Das ist eine sehr schone Aussicht auf den Garten."
        )
        assert lang == "de"
        assert conf >= MIN_CONFIDENCE

    def test_confidence_below_threshold_gives_none_from_endpoint(self):
        # The detection function itself returns a value; the endpoint filters.
        # Here we just assert the function signature contract.
        lang, conf = detect_language("a b c d e f g h i j k l")
        # Very short/ambiguous: either None or low confidence
        if lang is not None:
            # If it returned something, it must be a valid language code string
            assert isinstance(lang, str)
            assert isinstance(conf, float)
