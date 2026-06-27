"""Tests for GET /corpus/stats and DELETE /corpus/{doc_id}/progress."""
from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select

from backend.api.dependencies import get_current_user, get_db_session
from backend.main import app
from backend.models import Base, SourceDocumentRow, SourceProgressionRow

_USER_ID = "test-stats-user"


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


async def _prog(db: AsyncSession, *, doc_id: str, next_position: int, sentences_total: int) -> None:
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


# ── GET /corpus/stats ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stats_empty_corpus(client: AsyncClient) -> None:
    resp = await client.get("/corpus/stats")
    assert resp.status_code == 200
    d = resp.json()
    assert d["total"] == 0
    assert d["not_started"] == 0
    assert d["in_progress"] == 0
    assert d["complete"] == 0


@pytest.mark.asyncio
async def test_stats_counts_all_states(client: AsyncClient, db: AsyncSession) -> None:
    ns = await _doc(db, title="not_started")
    ip = await _doc(db, title="in_progress")
    done = await _doc(db, title="complete")

    await _prog(db, doc_id=ip.id,   next_position=5,  sentences_total=10)
    await _prog(db, doc_id=done.id, next_position=10, sentences_total=10)

    resp = await client.get("/corpus/stats")
    assert resp.status_code == 200
    d = resp.json()
    assert d["total"] == 3
    assert d["not_started"] == 1
    assert d["in_progress"] == 1
    assert d["complete"] == 1


@pytest.mark.asyncio
async def test_stats_not_started_includes_zero_position(client: AsyncClient, db: AsyncSession) -> None:
    doc = await _doc(db)
    await _prog(db, doc_id=doc.id, next_position=0, sentences_total=10)

    resp = await client.get("/corpus/stats")
    d = resp.json()
    assert d["not_started"] == 1
    assert d["in_progress"] == 0


@pytest.mark.asyncio
async def test_stats_sum_equals_total(client: AsyncClient, db: AsyncSession) -> None:
    for _ in range(2):
        await _doc(db)
    ip = await _doc(db, title="ip")
    done = await _doc(db, title="done")
    await _prog(db, doc_id=ip.id,   next_position=3, sentences_total=10)
    await _prog(db, doc_id=done.id, next_position=10, sentences_total=10)

    resp = await client.get("/corpus/stats")
    d = resp.json()
    assert d["not_started"] + d["in_progress"] + d["complete"] == d["total"]


# ── DELETE /corpus/{doc_id}/progress ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_reset_removes_progression(client: AsyncClient, db: AsyncSession) -> None:
    doc = await _doc(db)
    await _prog(db, doc_id=doc.id, next_position=5, sentences_total=10)

    resp = await client.delete(f"/corpus/{doc.id}/progress")
    assert resp.status_code == 204

    check = await client.get("/corpus?sort=in_progress")
    ids = [i["id"] for i in check.json()["items"]]
    assert doc.id not in ids


@pytest.mark.asyncio
async def test_reset_idempotent_when_no_progression(client: AsyncClient, db: AsyncSession) -> None:
    doc = await _doc(db)
    resp = await client.delete(f"/corpus/{doc.id}/progress")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_reset_only_affects_current_user(client: AsyncClient, db: AsyncSession) -> None:
    doc = await _doc(db)
    other = SourceProgressionRow(
        user_id="other-user",
        source_document_id=doc.id,
        next_position=5,
        sentences_total=10,
        completion_fraction=0.5,
    )
    db.add(other)
    await db.commit()

    resp = await client.delete(f"/corpus/{doc.id}/progress")
    assert resp.status_code == 204

    result = await db.execute(
        select(SourceProgressionRow).where(
            SourceProgressionRow.source_document_id == doc.id,
            SourceProgressionRow.user_id == "other-user",
        )
    )
    assert result.scalar_one_or_none() is not None
