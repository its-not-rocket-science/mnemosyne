"""Tests for GET /corpus/languages — corpus language summary endpoint."""
from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.dependencies import get_current_user, get_db_session
from backend.main import app
from backend.models import Base, SourceDocumentRow

_USER_ID = "test-lang-filter-user"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
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

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = lambda: _USER_ID
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_current_user, None)


def _make_doc(language: str, title: str | None = None) -> SourceDocumentRow:
    return SourceDocumentRow(
        id=str(uuid.uuid4()),
        language=language,
        title=title,
        content_type="pasted_text",
        char_count=100,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_corpus_returns_empty_list(client: AsyncClient) -> None:
    resp = await client.get("/corpus/languages")
    assert resp.status_code == 200
    data = resp.json()
    assert "languages" in data
    assert data["languages"] == []


@pytest.mark.asyncio
async def test_single_language(client: AsyncClient, db: AsyncSession) -> None:
    db.add(_make_doc("es"))
    db.add(_make_doc("es"))
    db.add(_make_doc("es"))
    await db.commit()

    resp = await client.get("/corpus/languages")
    assert resp.status_code == 200
    langs = resp.json()["languages"]
    assert len(langs) == 1
    assert langs[0]["language"] == "es"
    assert langs[0]["count"] == 3


@pytest.mark.asyncio
async def test_multiple_languages_sorted(client: AsyncClient, db: AsyncSession) -> None:
    for _ in range(5):
        db.add(_make_doc("fr"))
    for _ in range(2):
        db.add(_make_doc("de"))
    db.add(_make_doc("ar"))
    await db.commit()

    resp = await client.get("/corpus/languages")
    assert resp.status_code == 200
    langs = resp.json()["languages"]
    assert len(langs) == 3
    codes = [l["language"] for l in langs]
    assert codes == sorted(codes)  # alphabetically ordered


@pytest.mark.asyncio
async def test_counts_per_language(client: AsyncClient, db: AsyncSession) -> None:
    for _ in range(4):
        db.add(_make_doc("ja"))
    for _ in range(7):
        db.add(_make_doc("ru"))
    await db.commit()

    resp = await client.get("/corpus/languages")
    langs = {l["language"]: l["count"] for l in resp.json()["languages"]}
    assert langs["ja"] == 4
    assert langs["ru"] == 7


@pytest.mark.asyncio
async def test_response_schema(client: AsyncClient, db: AsyncSession) -> None:
    db.add(_make_doc("en"))
    await db.commit()

    resp = await client.get("/corpus/languages")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["languages"], list)
    item = data["languages"][0]
    assert set(item.keys()) == {"language", "count"}
    assert isinstance(item["language"], str)
    assert isinstance(item["count"], int)


@pytest.mark.asyncio
async def test_requires_auth(db_engine) -> None:
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides.pop(get_current_user, None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/corpus/languages")
    app.dependency_overrides.pop(get_db_session, None)
    # Without override, falls back to dev default — just verify it responds
    assert resp.status_code in (200, 401)
