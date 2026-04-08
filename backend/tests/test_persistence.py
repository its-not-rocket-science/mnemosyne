"""Persistence integration tests.

Uses an in-memory SQLite database (via aiosqlite) so no real PostgreSQL
instance is required.  The FastAPI dependency ``get_db_session`` is
overridden per-test-session with one backed by the SQLite engine.

Redis is absent; /parse falls through to the plugin as expected.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.database import get_db_session
from backend.main import app
from backend.models import Base, LearnableObjectRow, ParsedText, ReviewStateRow

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_engine():
    """Fresh in-memory SQLite engine with all tables created."""
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_client(db_engine):
    """AsyncClient wired to the app with the SQLite DB override in place."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db_session, None)


# ── /parse persistence ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_parse_persists_parsed_text(async_client, db_engine) -> None:
    resp = await async_client.post(
        "/parse",
        json={"text": "La casa es grande.", "language": "es"},
    )
    assert resp.status_code == 200

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        rows = (await db.execute(select(ParsedText))).scalars().all()

    assert len(rows) == 1
    assert rows[0].source_text == "La casa es grande."
    assert rows[0].language == "es"
    assert rows[0].source_url is None


@pytest.mark.asyncio
async def test_parse_persists_source_url(async_client, db_engine) -> None:
    resp = await async_client.post(
        "/parse",
        json={
            "text": "Hola.",
            "language": "es",
            "source_url": "https://example.com/article",
        },
    )
    assert resp.status_code == 200

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        rows = (await db.execute(select(ParsedText))).scalars().all()

    assert rows[0].source_url == "https://example.com/article"


@pytest.mark.asyncio
async def test_parse_persists_learnable_objects(async_client, db_engine) -> None:
    resp = await async_client.post(
        "/parse",
        json={"text": "Yo hablo español.", "language": "es"},
    )
    assert resp.status_code == 200
    # The response must still carry learnable_objects.
    sentences = resp.json()["sentences"]
    assert any(s["learnable_objects"] for s in sentences)

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        rows = (await db.execute(select(LearnableObjectRow))).scalars().all()

    assert len(rows) > 0
    ids_in_db = {r.id for r in rows}
    ids_in_response = {
        obj["id"]
        for s in sentences
        for obj in s["learnable_objects"]
    }
    assert ids_in_response.issubset(ids_in_db)


@pytest.mark.asyncio
async def test_parse_upserts_learnable_objects(async_client, db_engine) -> None:
    """Parsing the same text twice must not create duplicate object rows."""
    payload = {"text": "Hola amigo.", "language": "es"}
    await async_client.post("/parse", json=payload)
    await async_client.post("/parse", json=payload)

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        rows = (await db.execute(select(LearnableObjectRow))).scalars().all()

    ids = [r.id for r in rows]
    assert len(ids) == len(set(ids)), "Duplicate learnable object rows after re-parse"


# ── /lesson DB lookup ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lesson_served_from_db(async_client, db_engine) -> None:
    """A learnable object pre-loaded in the DB should be returned directly."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        db.add(
            LearnableObjectRow(
                id="es:vocab:prueba",
                language="es",
                type="vocabulary",
                label="prueba",
                lesson_data={"lemma": "prueba", "gloss": "test / trial"},
                confidence=0.9,
            )
        )
        await db.commit()

    resp = await async_client.get("/lesson/es%3Avocab%3Aprueba?language=es")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "es:vocab:prueba"
    assert "prueba" in data["title"]
    assert "prueba" in data["content_markdown"]


@pytest.mark.asyncio
async def test_lesson_db_then_fallback(async_client) -> None:
    """With no DB row and no in-memory lesson, the endpoint returns 404."""
    resp = await async_client.get("/lesson/es%3Avocab%3Adoesnotexist?language=es")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_lesson_available_after_parse(async_client) -> None:
    """A lesson should be retrievable via the DB after a /parse call."""
    parse_resp = await async_client.post(
        "/parse",
        json={"text": "Hola.", "language": "es"},
    )
    assert parse_resp.status_code == 200
    sentences = parse_resp.json()["sentences"]
    objects = [obj for s in sentences for obj in s["learnable_objects"]]
    assert objects, "Expected at least one learnable object from 'Hola.'"

    obj_id = objects[0]["id"]
    lesson_resp = await async_client.get(
        f"/lesson/{obj_id}?language=es"
    )
    assert lesson_resp.status_code == 200
    assert lesson_resp.json()["id"] == obj_id


# ── /review persistence ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_review_persists_state(async_client, db_engine) -> None:
    resp = await async_client.post(
        "/review",
        json={"object_id": "es:vocab:hola", "quality": 3},
    )
    assert resp.status_code == 200
    assert resp.json()["next_interval_days"] >= 1

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        rows = (await db.execute(select(ReviewStateRow))).scalars().all()

    assert len(rows) == 1
    assert rows[0].object_id == "es:vocab:hola"
    assert rows[0].state["reviews"] == 1


@pytest.mark.asyncio
async def test_review_loads_prior_state_from_db(async_client) -> None:
    """Second review must pick up the DB state, not start from scratch."""
    await async_client.post(
        "/review",
        json={"object_id": "es:vocab:mundo", "quality": 3},
    )
    resp2 = await async_client.post(
        "/review",
        json={"object_id": "es:vocab:mundo", "quality": 3},
    )
    assert resp2.status_code == 200
    assert resp2.json()["review_state"]["reviews"] == 2


@pytest.mark.asyncio
async def test_review_payload_state_used_when_no_db_row(async_client) -> None:
    """If no DB row exists, the payload review_state should be honoured."""
    from backend.srs.fsrs import default_state
    from datetime import UTC, datetime

    prior = default_state(datetime(2024, 1, 1, tzinfo=UTC)).to_dict()
    prior["reviews"] = 5  # simulate a card with history

    resp = await async_client.post(
        "/review",
        json={
            "object_id": "es:vocab:nuevo",
            "quality": 3,
            "review_state": prior,
        },
    )
    assert resp.status_code == 200
    # reviews should now be 6 (payload state was used as the base)
    assert resp.json()["review_state"]["reviews"] == 6


@pytest.mark.asyncio
async def test_review_db_state_takes_precedence_over_payload(async_client) -> None:
    """DB state must win over any review_state supplied in the payload."""
    # Establish DB state (reviews=1)
    await async_client.post(
        "/review",
        json={"object_id": "es:vocab:conflict", "quality": 3},
    )

    # Submit a second review with a stale payload state (reviews=0)
    from backend.srs.fsrs import default_state
    from datetime import UTC, datetime

    stale = default_state(datetime(2024, 1, 1, tzinfo=UTC)).to_dict()
    resp = await async_client.post(
        "/review",
        json={
            "object_id": "es:vocab:conflict",
            "quality": 3,
            "review_state": stale,  # stale — should be ignored
        },
    )
    assert resp.status_code == 200
    # DB had reviews=1; after this review it should be 2, not 1
    assert resp.json()["review_state"]["reviews"] == 2
