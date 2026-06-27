"""Tests for corpus tag CRUD and GET /corpus?tag= filter.

Study endpoint (POST /corpus/{doc_id}/study) is smoke-tested only — it
delegates to mine_sentence which has its own unit tests.
"""
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
from backend.models import Base, CorpusDocumentTagRow, SourceDocumentRow

_USER_ID = "test-tags-user"


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

async def _doc(db: AsyncSession, *, title: str = "doc") -> SourceDocumentRow:
    row = SourceDocumentRow(
        id=str(uuid.uuid4()), language="es", title=title,
        content_type="pasted_text", char_count=100,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ── GET /corpus/{doc_id}/tags ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_tags_empty(client: AsyncClient, db: AsyncSession) -> None:
    doc = await _doc(db)
    resp = await client.get(f"/corpus/{doc.id}/tags")
    assert resp.status_code == 200
    assert resp.json()["tags"] == []


# ── POST /corpus/{doc_id}/tags ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_tag(client: AsyncClient, db: AsyncSession) -> None:
    doc = await _doc(db)
    resp = await client.post(f"/corpus/{doc.id}/tags", json={"tag": "classic"})
    assert resp.status_code == 201
    assert "classic" in resp.json()["tags"]


@pytest.mark.asyncio
async def test_add_tag_idempotent(client: AsyncClient, db: AsyncSession) -> None:
    doc = await _doc(db)
    await client.post(f"/corpus/{doc.id}/tags", json={"tag": "classic"})
    resp = await client.post(f"/corpus/{doc.id}/tags", json={"tag": "classic"})
    assert resp.status_code == 201
    assert resp.json()["tags"].count("classic") == 1


@pytest.mark.asyncio
async def test_add_tag_strips_whitespace(client: AsyncClient, db: AsyncSession) -> None:
    doc = await _doc(db)
    resp = await client.post(f"/corpus/{doc.id}/tags", json={"tag": "  history  "})
    assert resp.status_code == 201
    assert "history" in resp.json()["tags"]


@pytest.mark.asyncio
async def test_add_blank_tag_rejected(client: AsyncClient, db: AsyncSession) -> None:
    doc = await _doc(db)
    resp = await client.post(f"/corpus/{doc.id}/tags", json={"tag": "   "})
    assert resp.status_code == 422


# ── DELETE /corpus/{doc_id}/tags/{tag} ───────────────────────────────────────

@pytest.mark.asyncio
async def test_remove_tag(client: AsyncClient, db: AsyncSession) -> None:
    doc = await _doc(db)
    await client.post(f"/corpus/{doc.id}/tags", json={"tag": "fiction"})
    resp = await client.delete(f"/corpus/{doc.id}/tags/fiction")
    assert resp.status_code == 204
    check = await client.get(f"/corpus/{doc.id}/tags")
    assert "fiction" not in check.json()["tags"]


@pytest.mark.asyncio
async def test_remove_nonexistent_tag_is_204(client: AsyncClient, db: AsyncSession) -> None:
    doc = await _doc(db)
    resp = await client.delete(f"/corpus/{doc.id}/tags/nonexistent")
    assert resp.status_code == 204


# ── GET /corpus/all-tags ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_tags_empty(client: AsyncClient) -> None:
    resp = await client.get("/corpus/all-tags")
    assert resp.status_code == 200
    assert resp.json()["tags"] == []


@pytest.mark.asyncio
async def test_all_tags_deduplicates(client: AsyncClient, db: AsyncSession) -> None:
    doc1 = await _doc(db, title="doc1")
    doc2 = await _doc(db, title="doc2")
    await client.post(f"/corpus/{doc1.id}/tags", json={"tag": "history"})
    await client.post(f"/corpus/{doc2.id}/tags", json={"tag": "history"})
    await client.post(f"/corpus/{doc1.id}/tags", json={"tag": "fiction"})

    resp = await client.get("/corpus/all-tags")
    tags = resp.json()["tags"]
    assert tags.count("history") == 1
    assert "fiction" in tags


# ── GET /corpus?tag= filter ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_filter_by_tag(client: AsyncClient, db: AsyncSession) -> None:
    tagged = await _doc(db, title="tagged")
    untagged = await _doc(db, title="untagged")
    await client.post(f"/corpus/{tagged.id}/tags", json={"tag": "grammar"})

    resp = await client.get("/corpus?tag=grammar")
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert tagged.id in ids
    assert untagged.id not in ids


@pytest.mark.asyncio
async def test_browse_items_include_tags(client: AsyncClient, db: AsyncSession) -> None:
    doc = await _doc(db)
    await client.post(f"/corpus/{doc.id}/tags", json={"tag": "vocab"})
    await client.post(f"/corpus/{doc.id}/tags", json={"tag": "grammar"})

    resp = await client.get("/corpus")
    item = next(i for i in resp.json()["items"] if i["id"] == doc.id)
    assert "vocab" in item["tags"]
    assert "grammar" in item["tags"]


# ── POST /corpus/{doc_id}/study (smoke test) ──────────────────────────────────

@pytest.mark.asyncio
async def test_study_missing_doc_returns_404(client: AsyncClient) -> None:
    resp = await client.post("/corpus/nonexistent-id/study")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_study_doc_no_chunks_returns_zero(client: AsyncClient, db: AsyncSession) -> None:
    doc = await _doc(db)
    resp = await client.post(f"/corpus/{doc.id}/study")
    assert resp.status_code == 200
    d = resp.json()
    assert d["mined"] == 0
    assert d["sentences_processed"] == 0
