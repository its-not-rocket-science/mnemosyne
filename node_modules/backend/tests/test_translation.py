"""Tests for machine translation — client, enrichment, and POST /translate API.

Client tests use respx to mock HTTP.
Enrichment and API tests use the standard tmp_path SQLite fixture.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
import respx
import httpx
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.dependencies import get_current_user, get_db_session
from backend.core.database import get_session_factory
from backend.dictionary.translation import (
    translate,
    translate_libretranslate,
    translate_mymemory,
)
from backend.main import app
from backend.models import Base, CanonicalObjectRow
from backend.parsing.canonical import canonical_object_id


from backend.dictionary.enrichment import enrich_objects
import backend.dictionary.enrichment as mod

from backend.core.config import get_settings

MOCK_LT = "https://mock-lt.test"
MOCK_MM = "https://mock-mm.test/get"


# ── translate_libretranslate ──────────────────────────────────────────────────

class TestLibreTranslate:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_translation(self):
        respx.post(f"{MOCK_LT}/translate").mock(
            return_value=httpx.Response(200, json={"translatedText": "cat"})
        )
        result = await translate_libretranslate("gato", "es", base_url=MOCK_LT)
        assert result == "cat"

    @pytest.mark.asyncio
    @respx.mock
    async def test_400_returns_none(self):
        respx.post(f"{MOCK_LT}/translate").mock(
            return_value=httpx.Response(400, json={"error": "Bad pair"})
        )
        result = await translate_libretranslate("x", "xx", base_url=MOCK_LT)
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_404_returns_none(self):
        respx.post(f"{MOCK_LT}/translate").mock(
            return_value=httpx.Response(404, json={"error": "Not found"})
        )
        result = await translate_libretranslate("x", "xx", base_url=MOCK_LT)
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_500_raises(self):
        respx.post(f"{MOCK_LT}/translate").mock(
            return_value=httpx.Response(500, text="error")
        )
        with pytest.raises(httpx.HTTPStatusError):
            await translate_libretranslate("gato", "es", base_url=MOCK_LT)

    @pytest.mark.asyncio
    @respx.mock
    async def test_api_key_included_in_body(self):
        route = respx.post(f"{MOCK_LT}/translate").mock(
            return_value=httpx.Response(200, json={"translatedText": "cat"})
        )
        await translate_libretranslate("gato", "es", base_url=MOCK_LT, api_key="secret")
        body = route.calls[0].request.content
        import json
        assert json.loads(body)["api_key"] == "secret"

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_result_returns_none(self):
        respx.post(f"{MOCK_LT}/translate").mock(
            return_value=httpx.Response(200, json={"translatedText": "  "})
        )
        result = await translate_libretranslate("gato", "es", base_url=MOCK_LT)
        assert result is None


# ── translate_mymemory ────────────────────────────────────────────────────────

class TestMyMemory:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_translation(self):
        respx.get(MOCK_MM).mock(
            return_value=httpx.Response(
                200,
                json={"responseData": {"translatedText": "butterfly"}, "responseStatus": 200},
            )
        )
        result = await translate_mymemory("mariposa", "es", base_url=MOCK_MM)
        assert result == "butterfly"

    @pytest.mark.asyncio
    @respx.mock
    async def test_non_200_status_returns_none(self):
        respx.get(MOCK_MM).mock(
            return_value=httpx.Response(
                200,
                json={"responseData": {"translatedText": ""}, "responseStatus": 429},
            )
        )
        result = await translate_mymemory("x", "es", base_url=MOCK_MM)
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_rejects_please_select_message(self):
        respx.get(MOCK_MM).mock(
            return_value=httpx.Response(
                200,
                json={
                    "responseData": {"translatedText": "PLEASE SELECT TWO DISTINCT LANGUAGES"},
                    "responseStatus": 200,
                },
            )
        )
        result = await translate_mymemory("x", "en", base_url=MOCK_MM)
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error_raises(self):
        respx.get(MOCK_MM).mock(return_value=httpx.Response(500, text="error"))
        with pytest.raises(httpx.HTTPStatusError):
            await translate_mymemory("x", "es", base_url=MOCK_MM)


# ── translate() dispatcher ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_translate_none_provider():
    result = await translate("gato", "es", provider="none")
    assert result is None


@pytest.mark.asyncio
async def test_translate_empty_text():
    result = await translate("  ", "es", provider="libretranslate")
    assert result is None


@pytest.mark.asyncio
async def test_translate_unknown_provider():
    result = await translate("gato", "es", provider="unknown_provider")
    assert result is None


# ── DB fixture ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            yield session

    class _NoTranslationSettings:
        rate_limit_parse = "1000/minute"
        translation_provider = "none"
        translation_api_url = None
        translation_api_key = None

    # important: clear leaked overrides from previous tests first
    app.dependency_overrides.clear()

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_current_user] = lambda: "test-user"
    app.dependency_overrides[get_settings] = lambda: _NoTranslationSettings()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── POST /translate ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_translate_endpoint_none_provider(client):
    resp = await client.post(
        "/translate",
        json={"text": "gato", "source_language": "es"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["translation"] is None
    assert data["provider"] == "none"
    assert data["attribution"] == ""
    assert data["cached"] is False


@pytest.mark.asyncio
async def test_translate_endpoint_validation_empty_text(client):
    resp = await client.post(
        "/translate",
        json={"text": "", "source_language": "es"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_translate_endpoint_serves_cached_translation(client, db_session):
    obj_id = canonical_object_id("es", "vocabulary", "gato")
    db_session.add(CanonicalObjectRow(
        id=obj_id,
        language="es",
        type="vocabulary",
        canonical_form="gato",
        display_label="gato",
        lesson_data={
            "translation": "cat",
            "translation_provider": "mymemory",
            "translation_cache_version": 2,
            "gloss_attempted": True,
        },
    ))
    await db_session.commit()

    resp = await client.post(
        "/translate",
        json={"text": "gato", "source_language": "es", "object_id": obj_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["translation"] == "cat"
    assert data["cached"] is True
    assert data["provider"] == "mymemory"


@pytest.mark.asyncio
@respx.mock
async def test_translate_endpoint_calls_provider_and_caches(client, db_session):
    """When provider != none and result is returned, it is stored in lesson_data."""
    from backend.core.config import get_settings

    class _FakeSettings:
        rate_limit_parse = "1000/minute"
        translation_provider = "libretranslate"
        translation_api_url = MOCK_LT
        translation_api_key = None

    app.dependency_overrides[get_settings] = lambda: _FakeSettings()

    respx.post(f"{MOCK_LT}/translate").mock(
        return_value=httpx.Response(200, json={"translatedText": "cat"})
    )

    obj_id = canonical_object_id("es", "vocabulary", "gato2")
    db_session.add(CanonicalObjectRow(
        id=obj_id,
        language="es",
        type="vocabulary",
        canonical_form="gato2",
        display_label="gato2",
        lesson_data={},
    ))
    await db_session.commit()

    try:
        resp = await client.post(
            "/translate",
            json={"text": "gato2", "source_language": "es", "object_id": obj_id},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["translation"] == "cat"
    assert data["cached"] is False


# ── enrichment with translation ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enrichment_stores_translation(db_session):
    obj_id = canonical_object_id("es", "vocabulary", "perro")
    db_session.add(CanonicalObjectRow(
        id=obj_id,
        language="es",
        type="vocabulary",
        canonical_form="perro",
        display_label="perro",
        lesson_data={},
    ))
    await db_session.commit()

    orig = mod.fetch_definition
    mod.fetch_definition = lambda lemma, lang, **kw: _async_return(None)

    from backend.dictionary import translation as tr_mod
    orig_tr = tr_mod.translate
    tr_mod.translate = lambda text, source, **kw: _async_return("dog")

    await enrich_objects(
        db_session,
        [obj_id],
        enable_gloss=False,
        translation_provider="libretranslate",
    )

    mod.fetch_definition = orig
    tr_mod.translate = orig_tr

    from sqlalchemy import select
    result = await db_session.get(CanonicalObjectRow, obj_id)
    assert result is not None
    assert result.lesson_data.get("translation") == "dog"
    assert result.lesson_data.get("translation_provider") == "libretranslate"
    assert result.lesson_data.get("translation_attempted") is True


# ── attribution coverage ──────────────────────────────────────────────────────

def test_attribution_text_covers_all_providers():
    from backend.api.routes.translate import ATTRIBUTION_TEXT
    assert "libretranslate" in ATTRIBUTION_TEXT
    assert "mymemory" in ATTRIBUTION_TEXT
    assert ATTRIBUTION_TEXT["mymemory"] != ""  # MyMemory requires attribution


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _async_return(value):
    return value
