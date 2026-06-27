"""Tests for GET /reading — reading history list endpoint."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.dependencies import get_current_user, get_db_session
from backend.main import app
from backend.models import Base, SourceDocumentRow, SourceProgressionRow

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
_USER_ID = "test-history-user"


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


@pytest_asyncio.fixture
async def seeded_db(db_engine):
    """Insert two source docs and progression rows for the test user."""
    async with async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)() as session:
        doc1 = SourceDocumentRow(
            id="doc-hist-1",
            language="es",
            content_type="text",
            title="El Quijote",
        )
        doc2 = SourceDocumentRow(
            id="doc-hist-2",
            language="fr",
            content_type="text",
            title=None,
            filename="article.txt",
        )
        session.add_all([doc1, doc2])
        await session.flush()

        prog1 = SourceProgressionRow(
            source_document_id="doc-hist-1",
            user_id=_USER_ID,
            next_position=10,
            sentences_total=50,
            completion_fraction=0.2,
            avg_comprehension=0.5,
            last_read_at=datetime(2026, 5, 28, 12, 0, tzinfo=UTC),
        )
        prog2 = SourceProgressionRow(
            source_document_id="doc-hist-2",
            user_id=_USER_ID,
            next_position=50,
            sentences_total=50,
            completion_fraction=1.0,
            avg_comprehension=0.8,
            last_read_at=datetime(2026, 5, 29, 8, 0, tzinfo=UTC),
        )
        session.add_all([prog1, prog2])
        await session.commit()


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_history_returns_items(client, seeded_db):
    """GET /reading returns items for the authenticated user."""
    resp = await client.get("/reading")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "count" in data
    assert data["count"] == len(data["items"])
    assert data["count"] == 2


@pytest.mark.asyncio
async def test_history_ordered_by_last_read_desc(client, seeded_db):
    """Items returned most-recently-read first."""
    resp = await client.get("/reading")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["source_document_id"] == "doc-hist-2"
    assert items[1]["source_document_id"] == "doc-hist-1"


@pytest.mark.asyncio
async def test_history_item_schema(client, seeded_db):
    """Each item has required fields."""
    resp = await client.get("/reading")
    items = resp.json()["items"]
    item = next(i for i in items if i["source_document_id"] == "doc-hist-1")
    for field in ("source_document_id", "title", "language", "completion_fraction",
                  "next_position", "sentences_total", "last_read_at", "is_complete"):
        assert field in item, f"Missing field: {field}"
    assert item["title"] == "El Quijote"
    assert item["language"] == "es"
    assert item["completion_fraction"] == pytest.approx(0.2)
    assert item["is_complete"] is False


@pytest.mark.asyncio
async def test_history_fallback_title_uses_filename(client, seeded_db):
    """When title is None, filename is used as display title."""
    resp = await client.get("/reading")
    items = resp.json()["items"]
    item = next(i for i in items if i["source_document_id"] == "doc-hist-2")
    assert item["title"] == "article.txt"


@pytest.mark.asyncio
async def test_history_is_complete_flag(client, seeded_db):
    """is_complete is True when next_position >= sentences_total."""
    resp = await client.get("/reading")
    items = resp.json()["items"]
    item = next(i for i in items if i["source_document_id"] == "doc-hist-2")
    assert item["is_complete"] is True


@pytest.mark.asyncio
async def test_history_limit_param(client, seeded_db):
    """limit param caps the number of items returned."""
    resp = await client.get("/reading", params={"limit": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_history_empty_when_no_docs(client):
    """Returns 200 with empty items when user has no reading history."""
    resp = await client.get("/reading")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["count"] == 0
