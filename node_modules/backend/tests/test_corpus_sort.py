"""Tests for GET /corpus?sort= — reading-progress sort/filter."""
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

_USER_ID = "test-sort-user"


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


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _doc(db: AsyncSession, *, language: str = "es", title: str = "doc") -> SourceDocumentRow:
    row = SourceDocumentRow(
        id=str(uuid.uuid4()), language=language, title=title,
        content_type="pasted_text", char_count=100,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _prog(
    db: AsyncSession,
    *,
    doc_id: str,
    next_position: int,
    sentences_total: int,
) -> None:
    frac = next_position / sentences_total if sentences_total else 0.0
    row = SourceProgressionRow(
        user_id=_USER_ID,
        source_document_id=doc_id,
        next_position=next_position,
        sentences_total=sentences_total,
        completion_fraction=frac,
    )
    db.add(row)
    await db.commit()


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sort_recent_is_default(client: AsyncClient, db: AsyncSession) -> None:
    doc = await _doc(db, title="alpha")
    resp = await client.get("/corpus")
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert doc.id in ids


@pytest.mark.asyncio
async def test_sort_not_started_returns_unstarted_only(
    client: AsyncClient, db: AsyncSession
) -> None:
    started = await _doc(db, title="started")
    unstarted = await _doc(db, title="unstarted")
    await _prog(db, doc_id=started.id, next_position=3, sentences_total=10)

    resp = await client.get("/corpus?sort=not_started")
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert unstarted.id in ids
    assert started.id not in ids


@pytest.mark.asyncio
async def test_sort_in_progress_returns_started_incomplete_only(
    client: AsyncClient, db: AsyncSession
) -> None:
    in_progress = await _doc(db, title="in_progress")
    complete = await _doc(db, title="complete")
    unstarted = await _doc(db, title="unstarted")

    await _prog(db, doc_id=in_progress.id, next_position=5, sentences_total=10)
    await _prog(db, doc_id=complete.id,    next_position=10, sentences_total=10)

    resp = await client.get("/corpus?sort=in_progress")
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert in_progress.id in ids
    assert complete.id not in ids
    assert unstarted.id not in ids


@pytest.mark.asyncio
async def test_sort_complete_returns_finished_only(
    client: AsyncClient, db: AsyncSession
) -> None:
    complete = await _doc(db, title="complete")
    in_progress = await _doc(db, title="in_progress")
    unstarted = await _doc(db, title="unstarted")

    await _prog(db, doc_id=complete.id,    next_position=10, sentences_total=10)
    await _prog(db, doc_id=in_progress.id, next_position=4,  sentences_total=10)

    resp = await client.get("/corpus?sort=complete")
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert complete.id in ids
    assert in_progress.id not in ids
    assert unstarted.id not in ids


@pytest.mark.asyncio
async def test_sort_in_progress_orders_by_completion_fraction(
    client: AsyncClient, db: AsyncSession
) -> None:
    doc_low  = await _doc(db, title="low")
    doc_high = await _doc(db, title="high")
    await _prog(db, doc_id=doc_low.id,  next_position=2, sentences_total=10)  # 20%
    await _prog(db, doc_id=doc_high.id, next_position=8, sentences_total=10)  # 80%

    resp = await client.get("/corpus?sort=in_progress")
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert ids.index(doc_high.id) < ids.index(doc_low.id)


@pytest.mark.asyncio
async def test_sort_total_reflects_filtered_count(
    client: AsyncClient, db: AsyncSession
) -> None:
    for _ in range(3):
        doc = await _doc(db)
        await _prog(db, doc_id=doc.id, next_position=5, sentences_total=10)
    for _ in range(2):
        await _doc(db)  # unstarted

    resp = await client.get("/corpus?sort=in_progress")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_unknown_sort_falls_back_to_recent(
    client: AsyncClient, db: AsyncSession
) -> None:
    await _doc(db)
    resp = await client.get("/corpus?sort=bogus")
    assert resp.status_code == 200
    assert "items" in resp.json()
