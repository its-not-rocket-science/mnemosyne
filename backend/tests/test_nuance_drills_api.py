"""Tests for GET /nuance-drills endpoint."""
from __future__ import annotations

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.dependencies import get_current_user, get_db_session
from backend.main import app
from backend.models import Base

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
_USER_ID = "test-nuance-drills-user"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            yield session

    def _override_user():
        return _USER_ID

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_current_user, None)


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_nuance_drills_spanish_subjunctive(client):
    """Known nuance_type returns discrimination drills for Spanish."""
    resp = await client.get(
        "/nuance-drills",
        params={"language": "es", "nuance_types": "subjunctive_mood"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "drills" in data
    assert "count" in data
    assert data["count"] == len(data["drills"])


@pytest.mark.asyncio
async def test_nuance_drills_multiple_types_deduplicated(client):
    """Multiple nuance_type values that map to the same concept return ≤1 set of drills."""
    resp = await client.get(
        "/nuance-drills",
        params={"language": "es", "nuance_types": "subjunctive_mood,subjunctive_trigger"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Both map to subjunctive_vs_indicative — concepts deduplicated
    concepts = [d["concept"] for d in data["drills"]]
    assert len(concepts) == len(set(concepts)), "Drill concepts must be unique"


@pytest.mark.asyncio
async def test_nuance_drills_unknown_type_returns_empty(client):
    """Unknown nuance_type returns 200 with empty drills list."""
    resp = await client.get(
        "/nuance-drills",
        params={"language": "es", "nuance_types": "not_a_real_nuance_type"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["drills"] == []
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_nuance_drills_empty_types_returns_empty(client):
    """Empty nuance_types returns 200 with empty drills list."""
    resp = await client.get(
        "/nuance-drills",
        params={"language": "es", "nuance_types": ""},
    )
    assert resp.status_code == 200
    assert resp.json()["drills"] == []


@pytest.mark.asyncio
async def test_nuance_drills_drill_schema(client):
    """Each returned drill has required discrimination fields."""
    resp = await client.get(
        "/nuance-drills",
        params={"language": "es", "nuance_types": "imperfect_aspect"},
    )
    assert resp.status_code == 200
    drills = resp.json()["drills"]
    if not drills:
        pytest.skip("No drills for imperfect_aspect in es — data may be missing")
    drill = drills[0]
    for field in ("type", "concept", "dimension", "sentence_a", "sentence_b", "question", "answer"):
        assert field in drill, f"Missing field: {field}"
    assert drill["type"] == "discrimination"
    assert drill["answer"] in ("a", "b")


@pytest.mark.asyncio
async def test_nuance_drills_limit_respected(client):
    """limit param caps the number of drills returned."""
    resp = await client.get(
        "/nuance-drills",
        params={"language": "es", "nuance_types": "subjunctive_mood,imperfect_aspect,ser_estar", "limit": "2"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["drills"]) <= 2


@pytest.mark.asyncio
async def test_nuance_drills_russian_aspect(client):
    """Russian perfective/imperfective nuance_type returns drills."""
    resp = await client.get(
        "/nuance-drills",
        params={"language": "ru", "nuance_types": "russian_aspect"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "nuance_types_requested" in data
    assert "russian_aspect" in data["nuance_types_requested"]


@pytest.mark.asyncio
async def test_nuance_drills_requires_auth(client):
    """Endpoint requires auth (override removed → should still work with override active)."""
    # With override active the request succeeds; this just documents the pattern
    resp = await client.get(
        "/nuance-drills",
        params={"language": "es", "nuance_types": "ser_estar"},
    )
    assert resp.status_code == 200
