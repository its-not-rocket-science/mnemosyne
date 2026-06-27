"""Integration tests for GET /review/sentence-items/{item_id}/context."""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.dependencies import get_current_user, get_db_session
from backend.core.database import get_session_factory
from backend.main import app
from backend.models import (
    Base,
    ParsedText,
    Sentence,
    SentenceReviewItemRow,
    SourceChunkRow,
    SourceDocumentRow,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_current_user] = lambda: "test-user"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _seed_parsed_text(db: AsyncSession, language: str = "es") -> ParsedText:
    pt = ParsedText(language=language, source_text="seed", user_id="test-user")
    db.add(pt)
    await db.commit()
    await db.refresh(pt)
    return pt


async def _seed_sentence(db: AsyncSession, pt_id: str, position: int, text: str) -> Sentence:
    s = Sentence(parsed_text_id=pt_id, position=position, text=text)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def _seed_item(db: AsyncSession, sentence_id: str, language: str = "es") -> SentenceReviewItemRow:
    row = SentenceReviewItemRow(
        sentence_id=sentence_id,
        language=language,
        item_type="cloze",
        prompt="La ___ es grande.",
        target_span="casa",
        answer="casa",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_context_returns_before_target_after(client, db_session):
    """Middle sentence returns surrounding sentences correctly split."""
    pt = await _seed_parsed_text(db_session)
    s0 = await _seed_sentence(db_session, pt.id, 0, "Sentence zero.")
    s1 = await _seed_sentence(db_session, pt.id, 1, "Sentence one.")
    s2 = await _seed_sentence(db_session, pt.id, 2, "Sentence two.")
    s3 = await _seed_sentence(db_session, pt.id, 3, "Sentence three.")
    s4 = await _seed_sentence(db_session, pt.id, 4, "Sentence four.")

    item = await _seed_item(db_session, s2.id)

    resp = await client.get(f"/review/sentence-items/{item.id}/context")
    assert resp.status_code == 200
    data = resp.json()

    assert data["target"] == "Sentence two."
    assert data["before"] == ["Sentence zero.", "Sentence one."]
    assert data["after"] == ["Sentence three.", "Sentence four."]


@pytest.mark.asyncio
async def test_context_window_capped_at_two(client, db_session):
    """Window is exactly 2 sentences each side — no more."""
    pt = await _seed_parsed_text(db_session)
    texts = [f"S{i}." for i in range(8)]
    sentences = []
    for i, t in enumerate(texts):
        s = await _seed_sentence(db_session, pt.id, i, t)
        sentences.append(s)

    # Target at position 4 — full 2-sentence window available on both sides.
    item = await _seed_item(db_session, sentences[4].id)

    resp = await client.get(f"/review/sentence-items/{item.id}/context")
    assert resp.status_code == 200
    data = resp.json()

    assert data["before"] == ["S2.", "S3."]
    assert data["target"] == "S4."
    assert data["after"] == ["S5.", "S6."]


@pytest.mark.asyncio
async def test_context_at_start_has_empty_before(client, db_session):
    """Sentence at position 0 returns empty before list."""
    pt = await _seed_parsed_text(db_session)
    s0 = await _seed_sentence(db_session, pt.id, 0, "First.")
    s1 = await _seed_sentence(db_session, pt.id, 1, "Second.")
    s2 = await _seed_sentence(db_session, pt.id, 2, "Third.")

    item = await _seed_item(db_session, s0.id)

    resp = await client.get(f"/review/sentence-items/{item.id}/context")
    assert resp.status_code == 200
    data = resp.json()

    assert data["before"] == []
    assert data["target"] == "First."
    assert data["after"] == ["Second.", "Third."]


@pytest.mark.asyncio
async def test_context_at_end_has_empty_after(client, db_session):
    """Sentence at final position returns empty after list."""
    pt = await _seed_parsed_text(db_session)
    s0 = await _seed_sentence(db_session, pt.id, 0, "A.")
    s1 = await _seed_sentence(db_session, pt.id, 1, "B.")
    s2 = await _seed_sentence(db_session, pt.id, 2, "C.")

    item = await _seed_item(db_session, s2.id)

    resp = await client.get(f"/review/sentence-items/{item.id}/context")
    assert resp.status_code == 200
    data = resp.json()

    assert data["before"] == ["A.", "B."]
    assert data["target"] == "C."
    assert data["after"] == []


@pytest.mark.asyncio
async def test_context_only_sentence_empty_neighbors(client, db_session):
    """Single sentence in a parsed text returns empty before and after."""
    pt = await _seed_parsed_text(db_session)
    s = await _seed_sentence(db_session, pt.id, 0, "Alone.")

    item = await _seed_item(db_session, s.id)

    resp = await client.get(f"/review/sentence-items/{item.id}/context")
    assert resp.status_code == 200
    data = resp.json()

    assert data["before"] == []
    assert data["target"] == "Alone."
    assert data["after"] == []


@pytest.mark.asyncio
async def test_context_source_title_returned(client, db_session):
    """source_title populated from SourceChunkRow → SourceDocumentRow chain."""
    pt = await _seed_parsed_text(db_session)
    s = await _seed_sentence(db_session, pt.id, 0, "Test sentence.")
    item = await _seed_item(db_session, s.id)

    doc = SourceDocumentRow(title="Don Quijote", language="es", content_type="book")
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)

    chunk = SourceChunkRow(
        source_document_id=doc.id,
        parsed_text_id=pt.id,
        chunk_index=0,
    )
    db_session.add(chunk)
    await db_session.commit()

    resp = await client.get(f"/review/sentence-items/{item.id}/context")
    assert resp.status_code == 200
    assert resp.json()["source_title"] == "Don Quijote"


@pytest.mark.asyncio
async def test_context_source_title_none_without_chunk(client, db_session):
    """source_title is None when no SourceChunkRow links the parsed_text."""
    pt = await _seed_parsed_text(db_session)
    s = await _seed_sentence(db_session, pt.id, 0, "Orphan sentence.")
    item = await _seed_item(db_session, s.id)

    resp = await client.get(f"/review/sentence-items/{item.id}/context")
    assert resp.status_code == 200
    assert resp.json()["source_title"] is None


@pytest.mark.asyncio
async def test_context_404_unknown_item(client, db_session):
    """Unknown item_id returns 404."""
    resp = await client.get("/review/sentence-items/no-such-id/context")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_context_neighbors_from_same_parsed_text_only(client, db_session):
    """Context window does not bleed into other parsed texts."""
    pt1 = await _seed_parsed_text(db_session)
    pt2 = await _seed_parsed_text(db_session)

    # pt1: only one sentence
    s_target = await _seed_sentence(db_session, pt1.id, 0, "Target.")

    # pt2: several sentences at overlapping positions
    for i in range(5):
        await _seed_sentence(db_session, pt2.id, i, f"Other {i}.")

    item = await _seed_item(db_session, s_target.id)

    resp = await client.get(f"/review/sentence-items/{item.id}/context")
    assert resp.status_code == 200
    data = resp.json()

    assert data["before"] == []
    assert data["target"] == "Target."
    assert data["after"] == []
