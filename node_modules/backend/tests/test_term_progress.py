from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.database import get_db_session, get_session_factory
from backend.main import app
from backend.models import Base


@pytest_asyncio.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
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
    app.dependency_overrides[get_session_factory] = lambda: factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_session_factory, None)


@pytest.mark.asyncio
async def test_term_progress_persists_and_updates(async_client) -> None:
    create = await async_client.post(
        "/term-progress",
        json={"term": "hablo", "lemma": "hablar", "language": "es", "seen": True, "source_lesson_id": "L1"},
    )
    assert create.status_code == 200
    assert create.json()["exposure_count"] == 1

    review = await async_client.post(
        "/term-progress",
        json={
            "term": "hablo",
            "lemma": "hablar",
            "language": "es",
            "seen": False,
            "reviewed": True,
            "correct": False,
            "mastery_delta": -0.2,
            "next_review_at": "2030-01-01T00:00:00Z",
        },
    )
    assert review.status_code == 200
    data = review.json()
    assert data["review_count"] == 1
    assert data["incorrect_count"] == 1
    assert data["mastery_score"] == 0.0
    assert data["next_review_at"] is not None
    assert data["review_bucket"] == "due"


@pytest.mark.asyncio
async def test_term_progress_is_language_specific(async_client) -> None:
    await async_client.post("/term-progress", json={"term": "bank", "language": "en"})
    await async_client.post("/term-progress", json={"term": "bank", "language": "de"})

    en_rows = await async_client.get("/term-progress/en")
    de_rows = await async_client.get("/term-progress/de")
    assert len(en_rows.json()) == 1
    assert len(de_rows.json()) == 1


@pytest.mark.asyncio
async def test_term_progress_correct_review_increases_mastery_and_interval(async_client) -> None:
    first = await async_client.post("/term-progress", json={"term": "hablo", "language": "es"})
    assert first.status_code == 200
    reviewed = await async_client.post(
        "/term-progress",
        json={"term": "hablo", "language": "es", "seen": False, "reviewed": True, "correct": True},
    )
    assert reviewed.status_code == 200
    data = reviewed.json()
    assert data["mastery_score"] > 0.0
    assert data["next_review_at"] is not None
    assert data["review_bucket"] in {"learning", "fading", "strong"}


@pytest.mark.asyncio
async def test_term_progress_repeated_success_can_become_strong(async_client) -> None:
    await async_client.post("/term-progress", json={"term": "être", "language": "fr"})
    last = None
    for _ in range(6):
        resp = await async_client.post(
            "/term-progress",
            json={"term": "être", "language": "fr", "seen": False, "reviewed": True, "correct": True},
        )
        assert resp.status_code == 200
        last = resp.json()
    assert last is not None
    assert last["mastery_score"] >= 0.85
    assert last["review_bucket"] == "strong"
