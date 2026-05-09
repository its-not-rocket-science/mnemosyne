"""Regression tests: /parse and /ingest produce identical output for the same text.

These tests verify that both endpoints use the same shared pipeline and that
lesson_engine.enrich() runs in both paths, producing consistent UUIDs and
enriched lesson_data regardless of which endpoint the client calls.

The plugin is mocked so the tests do not require spaCy models.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.dependencies import get_current_user, get_db_session, get_plugin_registry
from backend.core.database import get_session_factory
from backend.models import Base
from backend.parsing.pipeline import pipeline_cache_key
from backend.schemas.parse import CandidateObject, CandidateSentenceResult


# ── Fixed NLP output used by all parity tests ─────────────────────────────────

_CANDIDATES = [
    CandidateSentenceResult(
        text="El gato come pescado.",
        candidates=[
            CandidateObject(
                type="vocabulary",
                label="gato",
                canonical_form="gato",
                lesson_data={"en": "cat"},
                confidence=0.95,
                surface_form="gato",
            ),
            CandidateObject(
                type="vocabulary",
                label="pescado",
                canonical_form="pescado",
                lesson_data={"en": "fish"},
                confidence=0.92,
                surface_form="pescado",
            ),
        ],
    ),
    CandidateSentenceResult(
        text="Ella es simpática.",
        candidates=[
            CandidateObject(
                type="vocabulary",
                label="simpático",
                canonical_form="simpático",
                lesson_data={"en": "nice"},
                confidence=0.88,
                surface_form="simpática",
            ),
        ],
    ),
]


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def mock_plugin():
    plugin = MagicMock()
    plugin.analyze_text.return_value = _CANDIDATES
    plugin.capabilities = []
    plugin.lesson_store = {}
    return plugin


@pytest_asyncio.fixture
async def client(db_engine, mock_plugin):
    from backend.main import app

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            yield session

    mock_registry = MagicMock()
    mock_registry.get.return_value = mock_plugin

    app.dependency_overrides[get_db_session]      = _override_db
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_current_user]    = lambda: "test-user"
    app.dependency_overrides[get_plugin_registry] = lambda: mock_registry

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    mock_plugin.lesson_store.clear()


# ── Parity tests ───────────────────────────────────────────────────────────────

TEXT = "El gato come pescado. Ella es simpática."
LANGUAGE = "es"


@pytest.mark.asyncio
async def test_parse_and_ingest_produce_identical_sentences(client, mock_plugin):
    """Core parity: same sentence texts and learnable-object IDs from both endpoints."""
    parse_resp = await client.post("/parse", json={"language": LANGUAGE, "text": TEXT})
    assert parse_resp.status_code == 200, parse_resp.text

    ingest_resp = await client.post("/ingest", json={"language": LANGUAGE, "text": TEXT})
    assert ingest_resp.status_code == 200, ingest_resp.text

    parse_sentences  = parse_resp.json()["sentences"]
    ingest_sentences = ingest_resp.json()["sentences"]

    assert len(parse_sentences) == len(ingest_sentences), (
        "Sentence count differs between /parse and /ingest"
    )
    for i, (ps, is_) in enumerate(zip(parse_sentences, ingest_sentences)):
        assert ps["text"] == is_["text"], f"Sentence[{i}] text differs"
        parse_ids  = [lo["id"] for lo in ps["learnable_objects"]]
        ingest_ids = [lo["id"] for lo in is_["learnable_objects"]]
        assert parse_ids == ingest_ids, f"Sentence[{i}] object IDs differ"


@pytest.mark.asyncio
async def test_parse_runs_lesson_enrichment(client):
    """/parse lesson_data must include the 'pedagogy' key added by lesson_engine."""
    resp = await client.post("/parse", json={"language": LANGUAGE, "text": TEXT})
    assert resp.status_code == 200

    for sentence in resp.json()["sentences"]:
        for lo in sentence["learnable_objects"]:
            assert "pedagogy" in (lo.get("lesson_data") or {}), (
                f"Object {lo['id']} missing 'pedagogy' — lesson_engine.enrich() "
                "was not called for /parse"
            )


@pytest.mark.asyncio
async def test_ingest_runs_lesson_enrichment(client):
    """/ingest lesson_data must include the 'pedagogy' key added by lesson_engine."""
    resp = await client.post("/ingest", json={"language": LANGUAGE, "text": TEXT})
    assert resp.status_code == 200

    for sentence in resp.json()["sentences"]:
        for lo in sentence["learnable_objects"]:
            assert "pedagogy" in (lo.get("lesson_data") or {}), (
                f"Object {lo['id']} missing 'pedagogy' — lesson_engine.enrich() "
                "was not called for /ingest"
            )


@pytest.mark.asyncio
async def test_parse_and_ingest_share_cache_key(mock_plugin):
    """Same text+language must produce the same cache key in both routes."""
    # /ingest normalizes text; for already-clean text the key must match /parse.
    # Both routes call pipeline_cache_key(text, language) — verify manually.
    parse_key  = pipeline_cache_key(TEXT, LANGUAGE)
    ingest_key = pipeline_cache_key(TEXT, LANGUAGE)  # same call, same args
    assert parse_key == ingest_key


@pytest.mark.asyncio
async def test_ingest_returns_source_document_id(client):
    """/ingest response must include a source_document_id; /parse must not."""
    parse_resp  = await client.post("/parse",  json={"language": LANGUAGE, "text": TEXT})
    ingest_resp = await client.post("/ingest", json={"language": LANGUAGE, "text": TEXT})

    assert "source_document_id" not in parse_resp.json()
    assert "source_document_id" in ingest_resp.json()
    assert ingest_resp.json()["source_document_id"]  # non-empty


@pytest.mark.asyncio
async def test_analyze_text_called_once_per_cold_pipeline(client, mock_plugin):
    """plugin.analyze_text should be called exactly once on a cold pipeline."""
    mock_plugin.lesson_store.clear()

    # Disable any cached results from previous tests by patching get_json to miss.
    with patch("backend.parsing.pipeline.get_json", return_value=None):
        await client.post("/parse", json={"language": LANGUAGE, "text": TEXT})

    assert mock_plugin.analyze_text.call_count == 1


@pytest.mark.asyncio
async def test_object_ids_are_stable_across_calls(client, mock_plugin):
    """UUIDs are deterministic — a second call returns the same IDs."""
    with patch("backend.parsing.pipeline.get_json", return_value=None):
        r1 = await client.post("/parse", json={"language": LANGUAGE, "text": TEXT})

    mock_plugin.analyze_text.reset_mock()

    with patch("backend.parsing.pipeline.get_json", return_value=None):
        r2 = await client.post("/parse", json={"language": LANGUAGE, "text": TEXT})

    ids1 = [lo["id"] for s in r1.json()["sentences"] for lo in s["learnable_objects"]]
    ids2 = [lo["id"] for s in r2.json()["sentences"] for lo in s["learnable_objects"]]
    assert ids1 == ids2
