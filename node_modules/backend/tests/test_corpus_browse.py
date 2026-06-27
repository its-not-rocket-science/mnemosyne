"""Tests for GET /corpus — corpus text browser endpoint."""
from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.dependencies import get_current_user, get_db_session
from backend.main import app
from backend.models import Base, SourceDocumentRow, SourceProgressionRow

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
_USER_ID = "test-corpus-user"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


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


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _doc(
    db: AsyncSession,
    *,
    language: str = "es",
    title: str | None = None,
    content_type: str = "pasted_text",
) -> SourceDocumentRow:
    row = SourceDocumentRow(
        id=str(uuid.uuid4()),
        language=language,
        title=title,
        content_type=content_type,
        char_count=200,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _prog(
    db: AsyncSession,
    *,
    source_document_id: str,
    next_position: int = 0,
    sentences_total: int = 10,
) -> SourceProgressionRow:
    row = SourceProgressionRow(
        user_id=_USER_ID,
        source_document_id=source_document_id,
        next_position=next_position,
        sentences_total=sentences_total,
        completion_fraction=next_position / sentences_total if sentences_total else 0.0,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_corpus_browse_returns_all_documents(client, db):
    """GET /corpus returns all source documents regardless of progression."""
    await _doc(db, language="es", title="El Quijote")
    await _doc(db, language="fr", title="Le Petit Prince")

    resp = await client.get("/corpus")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    titles = {item["title"] for item in data["items"]}
    assert "El Quijote" in titles
    assert "Le Petit Prince" in titles


@pytest.mark.asyncio
async def test_corpus_browse_language_filter(client, db):
    """language filter returns only matching documents."""
    await _doc(db, language="es", title="Spanish Doc")
    await _doc(db, language="de", title="German Doc")

    resp = await client.get("/corpus?language=es")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["language"] == "es" for item in data["items"])


@pytest.mark.asyncio
async def test_corpus_browse_content_type_filter(client, db):
    """content_type filter returns only matching documents."""
    await _doc(db, language="es", title="Pasted", content_type="pasted_text")
    await _doc(db, language="es", title="Uploaded", content_type="uploaded_file")

    resp = await client.get("/corpus?content_type=pasted_text")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["content_type"] == "pasted_text" for item in data["items"])


@pytest.mark.asyncio
async def test_corpus_browse_title_search(client, db):
    """q param filters by title substring (case-insensitive)."""
    await _doc(db, language="es", title="Don Quijote")
    await _doc(db, language="es", title="Hamlet")

    resp = await client.get("/corpus?q=quijote")
    assert resp.status_code == 200
    data = resp.json()
    titles = [item["title"] for item in data["items"]]
    assert any("Quijote" in (t or "") for t in titles)
    assert all("Hamlet" not in (t or "") for t in titles)


@pytest.mark.asyncio
async def test_corpus_browse_pagination(client, db):
    """limit and offset paginate correctly."""
    for i in range(5):
        await _doc(db, language="es", title=f"Doc {i}")

    resp1 = await client.get("/corpus?language=es&limit=2&offset=0")
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert len(d1["items"]) == 2
    assert d1["total"] >= 5

    resp2 = await client.get("/corpus?language=es&limit=2&offset=2")
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert len(d2["items"]) == 2
    assert {i["id"] for i in d1["items"]}.isdisjoint({i["id"] for i in d2["items"]})


@pytest.mark.asyncio
async def test_corpus_browse_includes_progression(client, db):
    """Documents with user progression include progress fields."""
    doc = await _doc(db, language="es", title="Started Doc")
    await _prog(db, source_document_id=doc.id, next_position=3, sentences_total=10)

    resp = await client.get("/corpus")
    assert resp.status_code == 200
    items = resp.json()["items"]
    started = next((i for i in items if i["id"] == doc.id), None)
    assert started is not None
    assert started["started"] is True
    assert started["next_position"] == 3
    assert started["sentences_total"] == 10


@pytest.mark.asyncio
async def test_corpus_browse_unstarted_has_no_progression(client, db):
    """Documents not started by user have started=False and zero progress."""
    doc = await _doc(db, language="es", title="Unstarted Doc")

    resp = await client.get("/corpus")
    assert resp.status_code == 200
    items = resp.json()["items"]
    unstarted = next((i for i in items if i["id"] == doc.id), None)
    assert unstarted is not None
    assert unstarted["started"] is False
    assert unstarted["next_position"] == 0


@pytest.mark.asyncio
async def test_corpus_browse_response_schema(client, db):
    """Response has required fields on each item."""
    await _doc(db, language="es", title="Schema Check")

    resp = await client.get("/corpus")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data
    item = data["items"][0]
    for field in ("id", "language", "content_type", "char_count", "created_at", "started"):
        assert field in item, f"Missing field: {field}"


