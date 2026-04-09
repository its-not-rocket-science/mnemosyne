"""Integration tests for GET /recommend-text.

Uses the same in-memory SQLite + async_client fixtures as test_persistence.py.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.database import get_db_session
from backend.main import app
from backend.models import Base

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ── Fixtures (same pattern as test_persistence.py) ───────────────────────────


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_client(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db_session, None)


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recommend_empty_when_no_parses(async_client) -> None:
    """Without any parsed text, the endpoint returns an empty sentence list."""
    resp = await async_client.get("/recommend-text?language=es")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sentences"] == []
    assert "user_level" in data
    assert "target_difficulty_min" in data
    assert "target_difficulty_max" in data
    assert data["total_mastered"] == 0
    assert data["total_seen"] == 0


@pytest.mark.asyncio
async def test_recommend_returns_sentences_after_parse(async_client) -> None:
    """After parsing text, the endpoint returns scored sentences."""
    await async_client.post(
        "/parse",
        json={"text": "La casa es grande. Yo hablo español.", "language": "es"},
    )
    resp = await async_client.get("/recommend-text?language=es")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["sentences"]) >= 1


@pytest.mark.asyncio
async def test_recommend_sentence_fields_present(async_client) -> None:
    """Each returned sentence must carry all required fields."""
    await async_client.post(
        "/parse",
        json={"text": "Yo hablo español.", "language": "es"},
    )
    resp = await async_client.get("/recommend-text?language=es")
    assert resp.status_code == 200
    for sent in resp.json()["sentences"]:
        assert "sentence_id" in sent
        assert "text" in sent
        assert "language" in sent
        assert "difficulty" in sent
        assert "unknown_ratio" in sent
        assert "grammar_score" in sent
        assert "length_score" in sent
        assert "known_count" in sent
        assert "unknown_count" in sent
        assert "total_objects" in sent


@pytest.mark.asyncio
async def test_recommend_language_filter(async_client) -> None:
    """Sentences returned must match the requested language."""
    await async_client.post(
        "/parse", json={"text": "Bonjour le monde.", "language": "fr"},
    )
    await async_client.post(
        "/parse", json={"text": "El perro corre.", "language": "es"},
    )
    resp = await async_client.get("/recommend-text?language=fr")
    assert resp.status_code == 200
    for sent in resp.json()["sentences"]:
        assert sent["language"] == "fr"


@pytest.mark.asyncio
async def test_recommend_limit_parameter(async_client) -> None:
    """The limit parameter caps the number of sentences returned."""
    long_text = (
        "La casa es grande. "
        "Yo hablo español. "
        "El perro corre rápido. "
        "María estudia mucho. "
        "Ellos comen pizza. "
    )
    await async_client.post("/parse", json={"text": long_text, "language": "es"})

    for limit in [1, 2, 3]:
        resp = await async_client.get(f"/recommend-text?language=es&limit={limit}")
        assert resp.status_code == 200
        assert len(resp.json()["sentences"]) <= limit


@pytest.mark.asyncio
async def test_recommend_difficulty_scores_in_range(async_client) -> None:
    """Difficulty and component scores must be in [0.0, 1.0]."""
    await async_client.post(
        "/parse",
        json={"text": "La casa es grande. Yo hablo mucho.", "language": "es"},
    )
    resp = await async_client.get("/recommend-text?language=es")
    assert resp.status_code == 200
    for sent in resp.json()["sentences"]:
        assert 0.0 <= sent["difficulty"] <= 1.0
        assert 0.0 <= sent["unknown_ratio"] <= 1.0
        assert 0.0 <= sent["grammar_score"] <= 1.0
        assert 0.0 <= sent["length_score"] <= 1.0


@pytest.mark.asyncio
async def test_recommend_counts_consistent(async_client) -> None:
    """known_count + unknown_count must equal total_objects."""
    await async_client.post(
        "/parse",
        json={"text": "Yo hablo español bien.", "language": "es"},
    )
    resp = await async_client.get("/recommend-text?language=es")
    for sent in resp.json()["sentences"]:
        assert sent["known_count"] + sent["unknown_count"] == sent["total_objects"]


@pytest.mark.asyncio
async def test_recommend_deduplicates_identical_texts(async_client) -> None:
    """Parsing the same text twice must not return duplicate sentences."""
    payload = {"text": "Hola mundo.", "language": "es"}
    await async_client.post("/parse", json=payload)
    await async_client.post("/parse", json=payload)

    resp = await async_client.get("/recommend-text?language=es&limit=50")
    assert resp.status_code == 200
    texts = [s["text"] for s in resp.json()["sentences"]]
    assert len(texts) == len(set(texts)), "Duplicate texts in recommendation"


@pytest.mark.asyncio
async def test_recommend_user_level_is_valid(async_client) -> None:
    """user_level must be one of the four known proficiency labels."""
    resp = await async_client.get("/recommend-text?language=es")
    assert resp.json()["user_level"] in {"beginner", "elementary", "intermediate", "advanced"}


@pytest.mark.asyncio
async def test_recommend_target_window_is_valid_range(async_client) -> None:
    """target_difficulty_min must be < target_difficulty_max."""
    resp = await async_client.get("/recommend-text?language=es")
    data = resp.json()
    assert data["target_difficulty_min"] < data["target_difficulty_max"]


@pytest.mark.asyncio
async def test_recommend_new_user_is_beginner(async_client) -> None:
    """With no reviews, total_mastered must be 0 and level must be beginner."""
    await async_client.post(
        "/parse", json={"text": "El libro.", "language": "es"}
    )
    resp = await async_client.get("/recommend-text?language=es")
    data = resp.json()
    assert data["total_mastered"] == 0
    assert data["user_level"] == "beginner"


@pytest.mark.asyncio
async def test_recommend_unknown_language_returns_empty(async_client) -> None:
    """A language with no stored sentences returns 200 with empty list."""
    resp = await async_client.get("/recommend-text?language=zh")
    assert resp.status_code == 200
    assert resp.json()["sentences"] == []
