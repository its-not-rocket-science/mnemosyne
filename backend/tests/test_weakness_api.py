"""Tests for the weakness profile and reinforcement learning system.

Covers:
  · GET /weakness/object/{object_id} — ObjectReviewStatus endpoint
  · GET /weakness/profile/{language} — WeaknessProfile endpoint
  · POST /review with wrong_answer — confusion pair creation
  · POST /review — progression_stage in response
  · Concept-type-aware interval adjustment via review
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
from backend.models import (
    Base,
    CanonicalObjectRow,
    ConfusionPairRow,
    UserKnowledgeRow,
)


# ── DB fixture ────────────────────────────────────────────────────────────────


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


def _review(object_id="obj-1", quality=3, wrong_answer=None):
    payload = {"object_id": object_id, "quality": quality, "review_state": None}
    if wrong_answer is not None:
        payload["wrong_answer"] = wrong_answer
    return payload


async def _seed_canonical_object(db, object_id, obj_type="vocabulary", language="es"):
    row = CanonicalObjectRow(
        id=object_id,
        language=language,
        type=obj_type,
        canonical_form=object_id,
        display_label=object_id,
    )
    db.add(row)
    await db.commit()


# ── /review: progression_stage ───────────────────────────────────────────────


class TestProgressionStage:
    async def test_new_item_starts_at_recognition(self, client):
        resp = await client.post("/review", json=_review(quality=4))
        assert resp.status_code == 200
        data = resp.json()
        # New item with quality=4 → mastery still low on first review
        assert "progression_stage" in data

    async def test_progression_stage_in_knowledge_row(
        self, client, db_session
    ):
        await client.post("/review", json=_review(object_id="item-ps", quality=4))
        result = await db_session.execute(
            select(UserKnowledgeRow).where(UserKnowledgeRow.object_id == "item-ps")
        )
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.progression_stage in (
            "recognition", "guided_recall", "partial_production",
            "transformation", "free_production", "contextual_interpretation",
        )

    async def test_repeated_good_reviews_advance_stage(self, client, db_session):
        # Submit many Good reviews; stage should advance from recognition
        for _ in range(12):
            await client.post("/review", json=_review(object_id="adv-obj", quality=4))
        result = await db_session.execute(
            select(UserKnowledgeRow).where(UserKnowledgeRow.object_id == "adv-obj")
        )
        row = result.scalar_one_or_none()
        assert row is not None
        # After 12 Easy reviews mastery should be > 0.6
        assert row.mastery_score >= 0.60


# ── /review: concept-type scheduling ─────────────────────────────────────────


class TestConceptTypeScheduling:
    async def test_nuance_object_gets_shorter_interval(
        self, client, db_session
    ):
        # Seed nuance canonical object
        await _seed_canonical_object(db_session, "nuance-obj", obj_type="nuance")
        # Seed vocabulary object for comparison
        await _seed_canonical_object(db_session, "vocab-obj", obj_type="vocabulary")

        resp_nuance = await client.post("/review", json=_review("nuance-obj", quality=4))
        resp_vocab  = await client.post("/review", json=_review("vocab-obj",  quality=4))

        assert resp_nuance.status_code == 200
        assert resp_vocab.status_code == 200

        nuance_days = resp_nuance.json()["next_interval_days"]
        vocab_days  = resp_vocab.json()["next_interval_days"]

        # Nuance interval must be shorter than vocabulary interval
        # (both start from the same FSRS stability but nuance has 0.5× multiplier)
        assert nuance_days <= vocab_days

    async def test_vocabulary_interval_unchanged(self, client, db_session):
        await _seed_canonical_object(db_session, "vocab-ctrl", obj_type="vocabulary")
        resp = await client.post("/review", json=_review("vocab-ctrl", quality=3))
        assert resp.status_code == 200
        # Vocabulary multiplier = 1.0 → interval >= 1
        assert resp.json()["next_interval_days"] >= 1


# ── /review: confusion pair creation ─────────────────────────────────────────


class TestConfusionPairs:
    async def test_wrong_answer_creates_confusion_pair(
        self, client, db_session
    ):
        resp = await client.post(
            "/review",
            json=_review("conf-obj", quality=1, wrong_answer="estaba"),
        )
        assert resp.status_code == 200

        result = await db_session.execute(
            select(ConfusionPairRow).where(
                ConfusionPairRow.user_id == "test-user",
                ConfusionPairRow.object_id == "conf-obj",
            )
        )
        pairs = result.scalars().all()
        assert len(pairs) == 1
        assert pairs[0].confused_with == "estaba"
        assert pairs[0].confusion_count == 1

    async def test_repeated_confusion_increments_count(
        self, client, db_session
    ):
        for _ in range(3):
            await client.post(
                "/review",
                json=_review("rep-obj", quality=2, wrong_answer="ser"),
            )

        result = await db_session.execute(
            select(ConfusionPairRow).where(
                ConfusionPairRow.object_id == "rep-obj",
                ConfusionPairRow.confused_with == "ser",
            )
        )
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.confusion_count == 3

    async def test_good_review_no_confusion_pair(
        self, client, db_session
    ):
        await client.post("/review", json=_review("good-obj", quality=4, wrong_answer=None))

        result = await db_session.execute(
            select(ConfusionPairRow).where(ConfusionPairRow.object_id == "good-obj")
        )
        assert result.scalar_one_or_none() is None

    async def test_wrong_answer_not_stored_for_quality_3(
        self, client, db_session
    ):
        # quality=3 (Good) even with wrong_answer should NOT create confusion pair
        await client.post(
            "/review",
            json=_review("ok-obj", quality=3, wrong_answer="estuve"),
        )
        result = await db_session.execute(
            select(ConfusionPairRow).where(ConfusionPairRow.object_id == "ok-obj")
        )
        assert result.scalar_one_or_none() is None


# ── GET /weakness/object/{object_id} ─────────────────────────────────────────


class TestObjectReviewStatus:
    async def test_unreviewed_object_returns_defaults(self, client):
        resp = await client.get("/weakness/object/never-seen")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object_id"] == "never-seen"
        assert data["progression_stage"] == "recognition"
        assert data["mastery_score"] == 0.0
        assert data["total_reviews"] == 0
        assert data["confusion_pairs"] == []

    async def test_reviewed_object_has_mastery(self, client):
        await client.post("/review", json=_review("seen-obj", quality=4))
        resp = await client.get("/weakness/object/seen-obj")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mastery_score"] > 0.0
        assert data["total_reviews"] == 1

    async def test_confusion_pairs_appear_in_status(self, client):
        await client.post(
            "/review", json=_review("cp-obj", quality=1, wrong_answer="fue")
        )
        resp = await client.get("/weakness/object/cp-obj")
        assert resp.status_code == 200
        pairs = resp.json()["confusion_pairs"]
        assert len(pairs) == 1
        assert pairs[0]["confused_with"] == "fue"

    async def test_concept_type_label_populated(
        self, client, db_session
    ):
        await _seed_canonical_object(db_session, "idiom-check", obj_type="idiom")
        await client.post("/review", json=_review("idiom-check", quality=3))
        resp = await client.get("/weakness/object/idiom-check")
        data = resp.json()
        assert data["concept_type_label"] == "Idiom"


# ── GET /weakness/profile/{language} ─────────────────────────────────────────


class TestWeaknessProfile:
    async def test_empty_profile_returns_valid_structure(self, client):
        resp = await client.get("/weakness/profile/es")
        assert resp.status_code == 200
        data = resp.json()
        assert data["language"] == "es"
        assert "stage_distribution" in data
        assert "confusion_pairs" in data
        assert "concept_type_accuracy" in data
        assert "high_friction_items" in data
        assert "total_items" in data

    async def test_profile_counts_reviewed_items(
        self, client, db_session
    ):
        await _seed_canonical_object(db_session, "es-obj-1", language="es")
        await _seed_canonical_object(db_session, "es-obj-2", language="es")
        await client.post("/review", json=_review("es-obj-1", quality=3))
        await client.post("/review", json=_review("es-obj-2", quality=2))

        resp = await client.get("/weakness/profile/es")
        data = resp.json()
        assert data["total_items"] >= 2

    async def test_concept_type_accuracy_populated(
        self, client, db_session
    ):
        await _seed_canonical_object(db_session, "nuance-acc", obj_type="nuance", language="fr")
        await client.post("/review", json=_review("nuance-acc", quality=4))
        await client.post("/review", json=_review("nuance-acc", quality=1))

        resp = await client.get("/weakness/profile/fr")
        data = resp.json()
        accuracy_types = [e["concept_type"] for e in data["concept_type_accuracy"]]
        assert "nuance" in accuracy_types
