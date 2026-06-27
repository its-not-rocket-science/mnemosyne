"""Unit tests for the user knowledge model.

Tests cover:
  - mastery_score() pure function
  - classify() classification logic for all four bands
  - /dashboard endpoint integration
  - /review updating UserKnowledgeRow fields
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.database import get_db_session, get_session_factory
from backend.main import app
from backend.models import Base, UserKnowledgeRow
from backend.srs.fsrs import CardState, default_state, review as fsrs_review
from backend.srs.knowledge import (
    DEFAULT_USER_ID,
    FORGOTTEN_SCORE_THRESHOLD,
    KnowledgeStatus,
    MASTERY_SCORE_THRESHOLD,
    MIN_REVIEWS_FOR_MASTERY,
    classify,
    mastery_score,
)

_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


# ── DB fixtures ───────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_client(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_session_factory] = lambda: factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_session_factory, None)


# ── mastery_score() ───────────────────────────────────────────────────────────


def test_mastery_score_none_state_returns_zero():
    assert mastery_score(None, _NOW) == 0.0


def test_mastery_score_new_card_returns_zero():
    """A card with no review history has no meaningful mastery estimate."""
    state = default_state(_NOW).to_dict()
    # last_reviewed_at is None on a brand-new card
    assert mastery_score(state, _NOW) == 0.0


def test_mastery_score_just_reviewed_is_high():
    """Immediately after a review, retrievability should be close to 1.0."""
    _, state = fsrs_review(quality=3, state=None, now=_NOW)
    score = mastery_score(state, _NOW)
    assert score > 0.95


def test_mastery_score_decays_over_time():
    """Mastery score decreases as time passes since the last review."""
    _, state = fsrs_review(quality=3, state=None, now=_NOW)
    score_now = mastery_score(state, _NOW)
    score_later = mastery_score(state, _NOW + timedelta(days=30))
    assert score_later < score_now


def test_mastery_score_after_lapse_is_lower():
    """A 'Again' review followed by time should yield a lower score than 'Good'."""
    _, good_state = fsrs_review(quality=3, state=None, now=_NOW)
    _, again_state = fsrs_review(quality=1, state=None, now=_NOW)
    check_time = _NOW + timedelta(days=3)
    assert mastery_score(again_state, check_time) < mastery_score(good_state, check_time)


# ── classify() ───────────────────────────────────────────────────────────────


def test_classify_new_with_no_reviews():
    assert classify(0, None, _NOW) == KnowledgeStatus.NEW


def test_classify_new_with_zero_reviews_and_state():
    """total_reviews==0 is always NEW regardless of fsrs_state content."""
    state = default_state(_NOW).to_dict()
    assert classify(0, state, _NOW) == KnowledgeStatus.NEW


def test_classify_learning_after_first_review():
    """After one Good review, the item should be LEARNING (not MASTERED yet)."""
    _, state = fsrs_review(quality=3, state=None, now=_NOW)
    status = classify(1, state, _NOW)
    assert status == KnowledgeStatus.LEARNING


def test_classify_mastered_after_enough_reviews():
    """An item reviewed enough times with high recall should become MASTERED."""
    state = None
    for _ in range(MIN_REVIEWS_FOR_MASTERY):
        _, state = fsrs_review(quality=3, state=state, now=_NOW)
    # Check mastery immediately after review (retrievability ≈ 1.0)
    status = classify(MIN_REVIEWS_FOR_MASTERY, state, _NOW)
    assert status == KnowledgeStatus.MASTERED


def test_classify_not_mastered_with_too_few_reviews():
    """High retrievability alone is not enough — need MIN_REVIEWS_FOR_MASTERY."""
    _, state = fsrs_review(quality=4, state=None, now=_NOW)  # Easy on first review
    status = classify(1, state, _NOW)
    assert status != KnowledgeStatus.MASTERED


def test_classify_forgotten_when_decayed():
    """An item far past its due date with low stability should be FORGOTTEN."""
    _, state = fsrs_review(quality=1, state=None, now=_NOW)  # Again → very low stability
    # Move far into the future so retrievability drops below FORGOTTEN_THRESHOLD
    far_future = _NOW + timedelta(days=365)
    status = classify(1, state, far_future)
    assert status == KnowledgeStatus.FORGOTTEN


# ── /dashboard endpoint ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dashboard_empty_when_no_data(async_client) -> None:
    resp = await async_client.get("/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_objects"] == 0
    assert data["known"] == []
    assert data["weak"] == []
    assert data["new"] == []
    assert data["due_for_review"] == []


@pytest.mark.asyncio
async def test_dashboard_new_objects_appear_after_parse(async_client, db_engine) -> None:
    """Objects encountered via /parse should appear in the 'new' category."""
    resp = await async_client.post(
        "/parse",
        json={"text": "Hola amigo.", "language": "es"},
    )
    assert resp.status_code == 200

    dash = await async_client.get("/dashboard")
    assert dash.status_code == 200
    data = dash.json()
    assert data["total_objects"] > 0
    assert len(data["new"]) > 0
    assert all(obj["status"] == "new" for obj in data["new"])
    assert all(obj["total_reviews"] == 0 for obj in data["new"])


@pytest.mark.asyncio
async def test_dashboard_review_moves_object_from_new_to_weak(async_client) -> None:
    """After reviewing a new object once it should move to 'weak' (LEARNING)."""
    parse_resp = await async_client.post(
        "/parse",
        json={"text": "Hola.", "language": "es"},
    )
    obj_id = parse_resp.json()["sentences"][0]["learnable_objects"][0]["id"]

    # Review it
    await async_client.post(
        "/review",
        json={"object_id": obj_id, "quality": 3},
    )

    dash = await async_client.get("/dashboard")
    data = dash.json()

    weak_ids = {o["object_id"] for o in data["weak"]}
    new_ids = {o["object_id"] for o in data["new"]}
    assert obj_id in weak_ids
    assert obj_id not in new_ids


@pytest.mark.asyncio
async def test_dashboard_due_queue_populated_after_review(async_client) -> None:
    """After review the object should appear in due_for_review on its due date."""
    parse_resp = await async_client.post(
        "/parse",
        json={"text": "Hola.", "language": "es"},
    )
    obj_id = parse_resp.json()["sentences"][0]["learnable_objects"][0]["id"]

    review_resp = await async_client.post(
        "/review",
        json={"object_id": obj_id, "quality": 1},  # Again → very short interval
    )
    assert review_resp.json()["next_interval_days"] == 1

    # The next review is 1 day away, so the item should NOT be in today's queue
    dash = await async_client.get("/dashboard")
    due_ids = {o["object_id"] for o in dash.json()["due_for_review"]}
    assert obj_id not in due_ids


@pytest.mark.asyncio
async def test_review_persists_all_knowledge_fields(async_client, db_engine) -> None:
    """UserKnowledgeRow should have all fields correctly set after a review."""
    resp = await async_client.post(
        "/review",
        json={"object_id": "test:vocab:palabra", "quality": 3},
    )
    assert resp.status_code == 200

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        rows = (await db.execute(select(UserKnowledgeRow))).scalars().all()

    assert len(rows) >= 1
    row = next(r for r in rows if r.object_id == "test:vocab:palabra")
    assert row.user_id == DEFAULT_USER_ID
    assert row.total_reviews == 1
    assert row.mastery_score > 0.0
    assert row.fsrs_state is not None
    assert row.fsrs_state["reviews"] == 1
    assert row.due_at is not None


@pytest.mark.asyncio
async def test_review_db_state_takes_precedence_over_payload(async_client) -> None:
    """The DB UserKnowledge state must win over any review_state in the payload."""
    await async_client.post(
        "/review",
        json={"object_id": "es:vocab:conflict2", "quality": 3},
    )
    stale = default_state(datetime(2024, 1, 1, tzinfo=UTC)).to_dict()
    resp2 = await async_client.post(
        "/review",
        json={
            "object_id": "es:vocab:conflict2",
            "quality": 3,
            "review_state": stale,
        },
    )
    assert resp2.status_code == 200
    assert resp2.json()["review_state"]["reviews"] == 2


@pytest.mark.asyncio
async def test_review_payload_state_used_when_no_db_row(async_client) -> None:
    """With no DB row, the payload review_state is used as the base."""
    prior = default_state(datetime(2024, 1, 1, tzinfo=UTC)).to_dict()
    prior["reviews"] = 5

    resp = await async_client.post(
        "/review",
        json={
            "object_id": "es:vocab:nodb",
            "quality": 3,
            "review_state": prior,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["review_state"]["reviews"] == 6


# ── /dashboard?language= filter ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dashboard_language_filter_isolates_language(async_client) -> None:
    """Objects from one language must not appear in another language's dashboard."""
    await async_client.post("/parse", json={"text": "Hola amigo.", "language": "es"})
    await async_client.post("/parse", json={"text": "Bonjour monde.", "language": "fr"})

    dash_es = (await async_client.get("/dashboard?language=es")).json()
    dash_fr = (await async_client.get("/dashboard?language=fr")).json()

    es_ids = {o["object_id"] for o in dash_es["new"]}
    fr_ids = {o["object_id"] for o in dash_fr["new"]}

    assert es_ids, "Expected Spanish objects in es dashboard"
    assert fr_ids, "Expected French objects in fr dashboard"
    assert es_ids.isdisjoint(fr_ids), "Language dashboards must not share object IDs"


@pytest.mark.asyncio
async def test_dashboard_no_language_filter_returns_all(async_client) -> None:
    """Without ?language, all languages are combined."""
    await async_client.post("/parse", json={"text": "Hola.", "language": "es"})
    await async_client.post("/parse", json={"text": "Bonjour.", "language": "fr"})

    dash_all = (await async_client.get("/dashboard")).json()
    dash_es  = (await async_client.get("/dashboard?language=es")).json()
    dash_fr  = (await async_client.get("/dashboard?language=fr")).json()

    assert dash_all["total_objects"] >= dash_es["total_objects"] + dash_fr["total_objects"]


@pytest.mark.asyncio
async def test_dashboard_unknown_language_returns_empty(async_client) -> None:
    """A language with no parsed objects returns an empty dashboard, not an error."""
    await async_client.post("/parse", json={"text": "Hola.", "language": "es"})

    dash = (await async_client.get("/dashboard?language=zh")).json()
    assert dash["total_objects"] == 0
    assert dash["new"] == []
    assert dash["weak"] == []
    assert dash["known"] == []
    assert dash["due_for_review"] == []
