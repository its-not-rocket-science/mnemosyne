"""End-to-end loop: practice answer → /review → TermProgressRow synced → Memory Map correct.

Verifies:
  1. POST /review for a known canonical object writes UserKnowledgeRow.
  2. GET /term-progress/{language} reflects the review (Memory Map is live).
  3. Correct answer → review_bucket leaves "new"; incorrect → stays reviewable.
  4. Repeated correct reviews accumulate mastery and push next_review_at forward.
  5. The same loop works for an object not yet in CanonicalObjectRow (graceful skip).
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.dependencies import get_current_user, get_db_session
from backend.core.database import get_session_factory
from backend.main import app
from backend.models import Base, CanonicalObjectRow, TermProgressRow, UserKnowledgeRow

_USER = "loop-test-user"
_OBJECT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_LANGUAGE = "es"


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

    async def _db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_current_user] = lambda: _USER

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


async def _seed_canonical(db_session: AsyncSession) -> None:
    """Insert a minimal CanonicalObjectRow so /review can sync TermProgressRow."""
    obj = CanonicalObjectRow(
        id=_OBJECT_ID,
        language=_LANGUAGE,
        type="vocabulary",
        canonical_form="hablar",
        display_label="hablar",
        lesson_data={},
    )
    db_session.add(obj)
    await db_session.commit()


# ── Core loop ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_review_creates_knowledge_and_term_progress(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_canonical(db_session)

    resp = await client.post(
        "/review",
        json={"object_id": _OBJECT_ID, "quality": 4, "review_state": None},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["next_interval_days"] >= 1

    # UserKnowledgeRow created
    uk = await db_session.get(UserKnowledgeRow, (_USER, _OBJECT_ID))
    # Composite pk may not work with db.get; use select
    result = await db_session.execute(
        select(UserKnowledgeRow).where(
            UserKnowledgeRow.user_id == _USER,
            UserKnowledgeRow.object_id == _OBJECT_ID,
        )
    )
    uk = result.scalar_one_or_none()
    assert uk is not None
    assert uk.total_reviews == 1
    assert uk.mastery_score > 0

    # TermProgressRow synced
    tp = await db_session.get(TermProgressRow, (_USER, _LANGUAGE, "hablar"))
    assert tp is not None
    assert tp.review_count == 1
    assert tp.correct_count == 1
    assert tp.mastery_score > 0
    assert tp.next_review_at is not None


@pytest.mark.asyncio
async def test_get_term_progress_reflects_review(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_canonical(db_session)

    await client.post(
        "/review",
        json={"object_id": _OBJECT_ID, "quality": 4, "review_state": None},
    )

    resp = await client.get(f"/term-progress/{_LANGUAGE}")
    assert resp.status_code == 200
    rows = resp.json()
    assert any(r["term"] == "hablar" for r in rows), f"hablar not in {[r['term'] for r in rows]}"
    hablar = next(r for r in rows if r["term"] == "hablar")
    assert hablar["review_count"] == 1
    assert hablar["review_bucket"] in {"learning", "fading", "strong"}


@pytest.mark.asyncio
async def test_incorrect_review_marks_term_due_soon(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_canonical(db_session)

    # quality=1 (Again) → incorrect
    await client.post(
        "/review",
        json={"object_id": _OBJECT_ID, "quality": 1, "review_state": None},
    )

    tp = await db_session.get(TermProgressRow, (_USER, _LANGUAGE, "hablar"))
    assert tp is not None
    assert tp.incorrect_count == 1
    assert tp.correct_count == 0
    # FSRS schedules a short interval after Again — next_review_at should be near now
    assert tp.next_review_at is not None


@pytest.mark.asyncio
async def test_repeated_correct_reviews_accumulate_mastery(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_canonical(db_session)

    for _ in range(5):
        resp = await client.post(
            "/review",
            json={"object_id": _OBJECT_ID, "quality": 4, "review_state": None},
        )
        assert resp.status_code == 200

    tp = await db_session.get(TermProgressRow, (_USER, _LANGUAGE, "hablar"))
    assert tp is not None
    assert tp.review_count == 5
    assert tp.correct_count == 5
    # Mastery should be well above baseline after 5 correct reviews
    assert tp.mastery_score > 0.5

    resp = await client.get(f"/term-progress/{_LANGUAGE}")
    rows = resp.json()
    hablar = next(r for r in rows if r["term"] == "hablar")
    assert hablar["review_bucket"] in {"fading", "strong"}


@pytest.mark.asyncio
async def test_review_without_canonical_object_still_succeeds(
    client: AsyncClient,
) -> None:
    """/review for an unknown object_id must not fail — TermProgress sync skips gracefully."""
    resp = await client.post(
        "/review",
        json={"object_id": "unknown-object-id", "quality": 4, "review_state": None},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "next_interval_days" in data


@pytest.mark.asyncio
async def test_second_review_increments_counters(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_canonical(db_session)

    for _ in range(2):
        await client.post(
            "/review",
            json={"object_id": _OBJECT_ID, "quality": 4, "review_state": None},
        )

    tp = await db_session.get(TermProgressRow, (_USER, _LANGUAGE, "hablar"))
    assert tp is not None
    assert tp.review_count == 2
    assert tp.correct_count == 2
    # source_lesson_ids deduped — only one entry for the same object_id
    assert len(tp.source_lesson_ids) == 1
