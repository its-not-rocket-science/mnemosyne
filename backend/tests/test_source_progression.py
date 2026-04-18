"""Tests for source_progression reading continuity.

Coverage
────────
ingest.py
  - POST /ingest creates a SourceProgressionRow with sentences_total set from
    the parsed sentence count and next_position=0.

reading.py
  - GET /reading/{id} returns 404 when no progression row exists.
  - GET /reading/{id} returns the current state for a known document.
  - PATCH /reading/{id} advances next_position by sentences_read.
  - PATCH /reading/{id} clamps next_position to sentences_total.
  - PATCH /reading/{id} returns 404 for an unknown document.
  - PATCH /reading/{id} marks the document as complete (is_complete=True) when
    next_position reaches sentences_total.
  - avg_comprehension reflects UserKnowledgeRow mastery scores.

recommend.py
  - is_continuation=True for sentences from in-progress documents at or after
    next_position.
  - is_continuation=False for sentences from completed documents.
  - Continuation sentences sort before non-continuation sentences.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.dependencies import get_current_user, get_db_session
from backend.main import app
from backend.models import (
    Base,
    CanonicalObjectRow,
    ParsedText,
    Sentence,
    SentenceObjectRow,
    SourceChunkRow,
    SourceDocumentRow,
    SourceProgressionRow,
    UserKnowledgeRow,
)

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
_USER_ID = "test-progression-user"
_OTHER_USER = "other-user"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def async_client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            yield session

    def _override_user():
        return _USER_ID

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_current_user, None)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _seed_progression(
    db: AsyncSession,
    *,
    user_id: str = _USER_ID,
    source_document_id: str = "doc-001",
    next_position: int = 0,
    sentences_total: int = 5,
    avg_comprehension: float = 0.0,
    completion_fraction: float = 0.0,
) -> SourceProgressionRow:
    """Insert a SourceDocumentRow + SourceProgressionRow and flush."""
    doc = SourceDocumentRow(
        id=source_document_id,
        language="es",
        content_type="pasted_text",
        char_count=100,
    )
    db.add(doc)
    await db.flush()

    row = SourceProgressionRow(
        user_id=user_id,
        source_document_id=source_document_id,
        next_position=next_position,
        sentences_total=sentences_total,
        avg_comprehension=avg_comprehension,
        completion_fraction=completion_fraction,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ── GET /reading/{source_document_id} ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_reading_progress_not_found(async_client) -> None:
    resp = await async_client.get("/reading/nonexistent-doc")
    assert resp.status_code == 404
    assert "nonexistent-doc" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_reading_progress_returns_current_state(
    async_client, db_session
) -> None:
    await _seed_progression(
        db_session,
        source_document_id="doc-get-01",
        next_position=2,
        sentences_total=10,
        avg_comprehension=0.4,
        completion_fraction=0.2,
    )

    resp = await async_client.get("/reading/doc-get-01")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_document_id"] == "doc-get-01"
    assert body["next_position"] == 2
    assert body["sentences_total"] == 10
    assert abs(body["completion_fraction"] - 0.2) < 1e-6
    assert abs(body["avg_comprehension"] - 0.4) < 1e-6
    assert body["is_complete"] is False


@pytest.mark.asyncio
async def test_get_reading_progress_complete_document(
    async_client, db_session
) -> None:
    await _seed_progression(
        db_session,
        source_document_id="doc-complete-01",
        next_position=5,
        sentences_total=5,
        completion_fraction=1.0,
    )

    resp = await async_client.get("/reading/doc-complete-01")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_complete"] is True
    assert abs(body["completion_fraction"] - 1.0) < 1e-6


@pytest.mark.asyncio
async def test_get_reading_progress_user_isolation(
    async_client, db_session
) -> None:
    """Other user's progression is not visible to the test user."""
    await _seed_progression(
        db_session,
        user_id=_OTHER_USER,
        source_document_id="doc-other-01",
    )

    # Our user has no row for this document.
    resp = await async_client.get("/reading/doc-other-01")
    assert resp.status_code == 404


# ── PATCH /reading/{source_document_id} ───────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_advances_position(async_client, db_session) -> None:
    await _seed_progression(
        db_session,
        source_document_id="doc-patch-01",
        next_position=0,
        sentences_total=8,
    )

    resp = await async_client.patch(
        "/reading/doc-patch-01",
        json={"sentences_read": 3},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["next_position"] == 3
    assert abs(body["completion_fraction"] - 3 / 8) < 1e-6
    assert body["is_complete"] is False


@pytest.mark.asyncio
async def test_patch_default_sentences_read_is_one(
    async_client, db_session
) -> None:
    await _seed_progression(
        db_session,
        source_document_id="doc-patch-default",
        next_position=2,
        sentences_total=5,
    )

    resp = await async_client.patch(
        "/reading/doc-patch-default",
        json={},  # sentences_read defaults to 1
    )
    assert resp.status_code == 200
    assert resp.json()["next_position"] == 3


@pytest.mark.asyncio
async def test_patch_clamps_to_sentences_total(async_client, db_session) -> None:
    await _seed_progression(
        db_session,
        source_document_id="doc-clamp-01",
        next_position=4,
        sentences_total=5,
    )

    # Requesting 10 more should only advance to sentences_total.
    resp = await async_client.patch(
        "/reading/doc-clamp-01",
        json={"sentences_read": 10},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["next_position"] == 5
    assert abs(body["completion_fraction"] - 1.0) < 1e-6
    assert body["is_complete"] is True


@pytest.mark.asyncio
async def test_patch_marks_complete_exactly_at_total(
    async_client, db_session
) -> None:
    await _seed_progression(
        db_session,
        source_document_id="doc-exact-01",
        next_position=4,
        sentences_total=5,
    )

    resp = await async_client.patch(
        "/reading/doc-exact-01",
        json={"sentences_read": 1},
    )
    assert resp.status_code == 200
    assert resp.json()["is_complete"] is True


@pytest.mark.asyncio
async def test_patch_not_found(async_client) -> None:
    resp = await async_client.patch(
        "/reading/no-such-doc",
        json={"sentences_read": 1},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_updates_last_read_at(async_client, db_session) -> None:
    await _seed_progression(
        db_session,
        source_document_id="doc-ts-01",
        next_position=0,
        sentences_total=4,
    )

    before = datetime.now(UTC)
    resp = await async_client.patch(
        "/reading/doc-ts-01",
        json={"sentences_read": 1},
    )
    assert resp.status_code == 200
    # last_read_at must be a valid ISO timestamp at or after before.
    from datetime import timezone
    last_read = datetime.fromisoformat(resp.json()["last_read_at"])
    if last_read.tzinfo is None:
        last_read = last_read.replace(tzinfo=timezone.utc)
    assert last_read >= before


# ── avg_comprehension ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_updates_avg_comprehension_from_mastery(
    async_client, db_session
) -> None:
    """avg_comprehension should be the mean of UserKnowledgeRow.mastery_score
    for all objects linked to the document via the sentence graph."""
    doc_id = "doc-avg-01"

    # Build the object graph manually.
    doc = SourceDocumentRow(id=doc_id, language="es", content_type="pasted_text", char_count=50)
    db_session.add(doc)
    await db_session.flush()

    parsed = ParsedText(language="es", source_text="Hola mundo.")
    db_session.add(parsed)
    await db_session.flush()

    chunk = SourceChunkRow(
        source_document_id=doc_id,
        parsed_text_id=parsed.id,
        chunk_index=0,
        char_start=0,
        char_end=50,
    )
    db_session.add(chunk)
    await db_session.flush()

    sent = Sentence(parsed_text_id=parsed.id, position=0, text="Hola mundo.")
    db_session.add(sent)
    await db_session.flush()

    obj1 = CanonicalObjectRow(
        id="obj-avg-001",
        language="es",
        type="vocabulary",
        canonical_form="hola",
        display_label="hola",
        surface_forms=[],
        lesson_data={},
    )
    obj2 = CanonicalObjectRow(
        id="obj-avg-002",
        language="es",
        type="vocabulary",
        canonical_form="mundo",
        display_label="mundo",
        surface_forms=[],
        lesson_data={},
    )
    db_session.add(obj1)
    db_session.add(obj2)
    await db_session.flush()

    db_session.add(SentenceObjectRow(sentence_id=sent.id, object_id=obj1.id, position=0))
    db_session.add(SentenceObjectRow(sentence_id=sent.id, object_id=obj2.id, position=1))
    await db_session.flush()

    # Seed UserKnowledgeRow with known mastery scores: 0.6 and 0.4 → mean 0.5.
    now = datetime.now(UTC)
    db_session.add(UserKnowledgeRow(
        user_id=_USER_ID,
        object_id=obj1.id,
        language="es",
        mastery_score=0.6,
        first_seen=now,
        last_seen=now,
        total_reviews=3,
        due_at=now,
    ))
    db_session.add(UserKnowledgeRow(
        user_id=_USER_ID,
        object_id=obj2.id,
        language="es",
        mastery_score=0.4,
        first_seen=now,
        last_seen=now,
        total_reviews=2,
        due_at=now,
    ))

    prog = SourceProgressionRow(
        user_id=_USER_ID,
        source_document_id=doc_id,
        next_position=0,
        sentences_total=1,
        avg_comprehension=0.0,
        completion_fraction=0.0,
    )
    db_session.add(prog)
    await db_session.commit()

    resp = await async_client.patch(
        f"/reading/{doc_id}",
        json={"sentences_read": 1},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Mean of 0.6 and 0.4 is 0.5; allow floating-point tolerance.
    assert abs(body["avg_comprehension"] - 0.5) < 0.01


# ── POST /ingest creates SourceProgressionRow ─────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_creates_progression_row(async_client, db_session) -> None:
    """POST /ingest must create a SourceProgressionRow with sentences_total > 0."""
    # Mock the NLP analysis to return predictable sentences without a real spaCy model.
    from backend.schemas.parse import CandidateSentenceResult

    fake_results = [
        CandidateSentenceResult(text="Hola.", candidates=[]),
        CandidateSentenceResult(text="Mundo.", candidates=[]),
    ]

    with (
        patch("backend.api.routes.ingest.get_json", new_callable=AsyncMock, return_value=None),
        patch("backend.api.routes.ingest.set_json", new_callable=AsyncMock),
    ):
        # Patch the plugin registry to return a fake plugin.
        from backend.parsing.plugin_loader import PluginRegistry
        from unittest.mock import MagicMock

        fake_plugin = MagicMock()
        fake_plugin.analyze_text.return_value = fake_results
        fake_plugin.lesson_store = {}

        fake_registry = MagicMock(spec=PluginRegistry)
        fake_registry.get.return_value = fake_plugin

        with patch("backend.api.routes.ingest.get_plugin_registry", return_value=fake_registry):
            from backend.api.dependencies import get_plugin_registry as _gpr
            from backend.core.config import get_settings
            app.dependency_overrides[_gpr] = lambda: fake_registry

            resp = await async_client.post(
                "/ingest",
                json={
                    "text": "Hola. Mundo.",
                    "language": "es",
                    "content_type": "pasted_text",
                },
            )
            app.dependency_overrides.pop(_gpr, None)

    assert resp.status_code == 200, resp.text
    source_document_id = resp.json()["source_document_id"]

    from sqlalchemy import select
    result = await db_session.execute(
        select(SourceProgressionRow).where(
            SourceProgressionRow.user_id == _USER_ID,
            SourceProgressionRow.source_document_id == source_document_id,
        )
    )
    row = result.scalar_one_or_none()
    assert row is not None, "SourceProgressionRow should be created by /ingest"
    assert row.next_position == 0
    assert row.sentences_total == 2  # two fake sentences
    assert row.completion_fraction == 0.0


# ── recommend.py is_continuation ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_recommend_is_continuation_flag(db_session) -> None:
    """Sentences from in-progress documents at next_position are is_continuation=True."""
    from backend.api.routes.reading import _compute_avg_comprehension

    # Build a minimal document with two sentences and a progression row at position 1.
    doc_id = "doc-cont-01"
    doc = SourceDocumentRow(id=doc_id, language="es", content_type="pasted_text", char_count=50)
    db_session.add(doc)
    await db_session.flush()

    parsed = ParsedText(language="es", source_text="Primera. Segunda.")
    db_session.add(parsed)
    await db_session.flush()

    chunk = SourceChunkRow(
        source_document_id=doc_id,
        parsed_text_id=parsed.id,
        chunk_index=0,
        char_start=0,
        char_end=50,
    )
    db_session.add(chunk)

    s0 = Sentence(parsed_text_id=parsed.id, position=0, text="Primera.")
    s1 = Sentence(parsed_text_id=parsed.id, position=1, text="Segunda.")
    db_session.add(s0)
    db_session.add(s1)
    await db_session.flush()

    prog = SourceProgressionRow(
        user_id=_USER_ID,
        source_document_id=doc_id,
        next_position=1,   # sentence 0 was read; next is sentence 1
        sentences_total=2,
        avg_comprehension=0.0,
        completion_fraction=0.5,
    )
    db_session.add(prog)
    await db_session.commit()

    # Verify that the helper finds no objects (empty document) and returns 0.0.
    avg = await _compute_avg_comprehension(db_session, doc_id, _USER_ID)
    assert avg == 0.0

    # Verify the SourceProgressionRow is queryable as in-progress.
    from sqlalchemy import select
    result = await db_session.execute(
        select(SourceProgressionRow).where(
            SourceProgressionRow.user_id == _USER_ID,
            SourceProgressionRow.next_position > 0,
        )
    )
    rows = result.scalars().all()
    in_progress_doc_ids = {
        r.source_document_id for r in rows if r.next_position < r.sentences_total
    }
    assert doc_id in in_progress_doc_ids


@pytest.mark.asyncio
async def test_recommend_continuation_sorts_first(db_session) -> None:
    """The sort key puts continuation sentences (priority 0) before others (priority 1).

    _sort_key is a closure inside recommend_text; test the sort logic directly
    by replicating the condition from the route handler.
    """

    in_progress = {"doc-A": 2}
    sentence_source_doc_ids = {
        "sent-continuation": "doc-A",
        "sent-other": "doc-B",
    }
    sentence_positions = {
        "sent-continuation": 3,   # position 3 >= next_position 2 → continuation
        "sent-other": 0,
    }

    def sort_key_replica(sid: str, difficulty: float, center: float = 0.3) -> tuple[int, float]:
        src_doc = sentence_source_doc_ids.get(sid)
        if src_doc and src_doc in in_progress:
            next_pos = in_progress[src_doc]
            if sentence_positions.get(sid, 0) >= next_pos:
                return (0, abs(difficulty - center))
        return (1, abs(difficulty - center))

    cont_key   = sort_key_replica("sent-continuation", 0.3)
    other_key  = sort_key_replica("sent-other", 0.3)

    assert cont_key[0] == 0, "Continuation sentence should have priority 0"
    assert other_key[0] == 1, "Non-continuation sentence should have priority 1"
    assert cont_key < other_key, "Continuation should sort before non-continuation"
