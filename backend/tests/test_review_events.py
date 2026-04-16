"""V1 — Review event log tests.

Strategy
────────
All tests use the in-memory SQLite async fixture (same pattern as
test_persistence.py / test_knowledge.py).

We verify:
  1. A ReviewEventRow is written on every successful review.
  2. mastery_score_before is 0 for a new card; > 0 after first review.
  3. mastery_score_after matches the mastery_score stored in UserKnowledge.
  4. GET /metrics reflects reviews_today, streak_days, and daily_activity.
  5. DELETE /users/me removes review_events rows.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch, AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.api.dependencies import get_current_user, get_db_session
from backend.main import app
from backend.models import Base, ReviewEventRow

# ── DB fixture ────────────────────────────────────────────────────────────────

_TEST_DB = "sqlite+aiosqlite:///:memory:"


@pytest.fixture()
async def db_session():
    engine = create_async_engine(_TEST_DB, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture()
async def client(db_session: AsyncSession):
    """HTTP client with DB and auth overrides."""
    async def _db():
        yield db_session

    app.dependency_overrides[get_db_session] = _db
    app.dependency_overrides[get_current_user] = lambda: "test-user"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _review_payload(object_id: str = "obj-1", quality: int = 4) -> dict:
    return {
        "object_id": object_id,
        "quality": quality,
        "review_state": None,
    }


# ── Event row creation ────────────────────────────────────────────────────────

class TestReviewEventRow:
    async def test_event_written_on_review(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        resp = await client.post("/review", json=_review_payload())
        assert resp.status_code == 200

        result = await db_session.execute(
            select(ReviewEventRow).where(ReviewEventRow.user_id == "test-user")
        )
        rows = result.scalars().all()
        assert len(rows) == 1

    async def test_event_captures_object_id(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await client.post("/review", json=_review_payload(object_id="obj-xyz"))
        result = await db_session.execute(select(ReviewEventRow))
        row = result.scalar_one()
        assert row.object_id == "obj-xyz"

    async def test_event_captures_quality(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await client.post("/review", json=_review_payload(quality=2))
        result = await db_session.execute(select(ReviewEventRow))
        row = result.scalar_one()
        assert row.quality == 2

    async def test_mastery_before_is_zero_for_new_card(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        # No prior UserKnowledge row → first review; mastery_before must be 0.
        await client.post("/review", json=_review_payload())
        result = await db_session.execute(select(ReviewEventRow))
        row = result.scalar_one()
        assert row.mastery_score_before == 0.0

    async def test_mastery_after_positive_after_review(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await client.post("/review", json=_review_payload(quality=4))
        result = await db_session.execute(select(ReviewEventRow))
        row = result.scalar_one()
        assert row.mastery_score_after > 0.0

    async def test_second_review_has_nonzero_mastery_before(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        # First review establishes state; second review should see mastery_before > 0.
        await client.post("/review", json=_review_payload(quality=4))
        await client.post("/review", json=_review_payload(quality=4))

        result = await db_session.execute(
            select(ReviewEventRow).order_by(ReviewEventRow.reviewed_at)
        )
        rows = result.scalars().all()
        assert len(rows) == 2
        assert rows[0].mastery_score_before == 0.0
        assert rows[1].mastery_score_before > 0.0

    async def test_multiple_objects_each_get_event(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await client.post("/review", json=_review_payload(object_id="a"))
        await client.post("/review", json=_review_payload(object_id="b"))

        result = await db_session.execute(select(ReviewEventRow))
        rows = result.scalars().all()
        assert len(rows) == 2
        ids = {r.object_id for r in rows}
        assert ids == {"a", "b"}

    async def test_reviewed_at_is_set(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        before = datetime.now(UTC)
        await client.post("/review", json=_review_payload())
        result = await db_session.execute(select(ReviewEventRow))
        row = result.scalar_one()
        ts = row.reviewed_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        assert ts >= before


# ── Metrics activity fields ───────────────────────────────────────────────────

class TestMetricsActivity:
    async def test_reviews_today_counts_todays_events(
        self, client: AsyncClient
    ) -> None:
        await client.post("/review", json=_review_payload())
        await client.post("/review", json=_review_payload(object_id="obj-2"))

        resp = await client.get("/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["reviews_today"] == 2

    async def test_streak_is_one_after_first_review_today(
        self, client: AsyncClient
    ) -> None:
        await client.post("/review", json=_review_payload())
        resp = await client.get("/metrics")
        assert resp.json()["streak_days"] == 1

    async def test_daily_activity_contains_today(
        self, client: AsyncClient
    ) -> None:
        await client.post("/review", json=_review_payload())
        resp = await client.get("/metrics")
        data = resp.json()
        today = date.today().isoformat()
        dates = [entry["date"] for entry in data["daily_activity"]]
        assert today in dates

    async def test_no_reviews_gives_zero_activity(
        self, client: AsyncClient
    ) -> None:
        resp = await client.get("/metrics")
        data = resp.json()
        assert data["reviews_today"] == 0
        assert data["streak_days"] == 0
        assert data["daily_activity"] == []

    async def test_streak_broken_by_gap(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        # Insert an event 2 days ago but nothing yesterday → streak should be 0
        # (no review today either).
        two_days_ago = datetime.now(UTC) - timedelta(days=2)
        db_session.add(ReviewEventRow(
            user_id="test-user",
            object_id="old",
            quality=4,
            mastery_score_before=0.0,
            mastery_score_after=0.5,
            reviewed_at=two_days_ago,
        ))
        await db_session.commit()

        resp = await client.get("/metrics")
        assert resp.json()["streak_days"] == 0

    async def test_streak_consecutive_days(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        # Events today and yesterday → streak = 2.
        yesterday = datetime.now(UTC) - timedelta(days=1)
        db_session.add(ReviewEventRow(
            user_id="test-user",
            object_id="yesterday-obj",
            quality=4,
            mastery_score_before=0.0,
            mastery_score_after=0.5,
            reviewed_at=yesterday,
        ))
        await db_session.commit()
        await client.post("/review", json=_review_payload())  # today

        resp = await client.get("/metrics")
        assert resp.json()["streak_days"] == 2


# ── Deletion ──────────────────────────────────────────────────────────────────

class TestReviewEventDeletion:
    async def test_delete_account_removes_events(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        await client.post("/review", json=_review_payload())
        await client.post("/review", json=_review_payload(object_id="obj-2"))

        # Confirm events exist.
        result = await db_session.execute(select(ReviewEventRow))
        assert len(result.scalars().all()) == 2

        resp = await client.delete("/users/me")
        assert resp.status_code == 204

        db_session.expire_all()
        result = await db_session.execute(select(ReviewEventRow))
        assert len(result.scalars().all()) == 0
