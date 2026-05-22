"""Integration tests for the sentence-level spaced-retrieval review API.

Uses an in-memory SQLite database (same pattern as test_review_events.py).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.dependencies import get_current_user, get_db_session
from backend.core.database import get_session_factory
from backend.main import app
from backend.models import (
    Base,
    CanonicalObjectRow,
    ParsedText,
    Sentence,
    SentenceObjectRow,
    SentenceReviewItemRow,
    UserSentenceReviewRow,
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


# ── DB seeding helpers ────────────────────────────────────────────────────────


async def _seed_parsed_text(db: AsyncSession, *, user_id: str = "test-user", language: str = "es") -> ParsedText:
    pt = ParsedText(language=language, source_text="seed text", user_id=user_id)
    db.add(pt)
    await db.commit()
    await db.refresh(pt)
    return pt


async def _seed_sentence(db: AsyncSession, pt_id: str, text: str) -> Sentence:
    s = Sentence(parsed_text_id=pt_id, position=0, text=text)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def _seed_canonical_object(
    db: AsyncSession,
    *,
    language: str = "es",
    obj_type: str = "vocabulary",
    label: str = "casa",
    surface_forms: list[str] | None = None,
    confidence: float = 0.85,
) -> CanonicalObjectRow:
    import uuid as _uuid
    obj = CanonicalObjectRow(
        id=str(_uuid.uuid4()),
        language=language,
        type=obj_type,
        canonical_form=label,
        display_label=label,
        surface_forms=surface_forms or [label],
        lesson_data={},
        confidence=confidence,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def _seed_sentence_object(db: AsyncSession, sentence_id: str, object_id: str, position: int = 0):
    so = SentenceObjectRow(sentence_id=sentence_id, object_id=object_id, position=position)
    db.add(so)
    await db.commit()


async def _seed_review_item(
    db: AsyncSession,
    sentence_id: str,
    *,
    language: str = "es",
    item_type: str = "cloze",
    target_span: str = "casa",
    answer: str = "casa",
    prompt: str = "La ___ es grande.",
    due_offset_days: int = 0,
) -> SentenceReviewItemRow:
    row = SentenceReviewItemRow(
        sentence_id=sentence_id,
        language=language,
        item_type=item_type,
        prompt=prompt,
        target_span=target_span,
        answer=answer,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    due_at = datetime.now(UTC) + timedelta(days=due_offset_days)
    ur = UserSentenceReviewRow(
        user_id="test-user",
        item_id=row.id,
        due_at=due_at,
    )
    db.add(ur)
    await db.commit()
    return row


# ── GET /review/sentence-items ────────────────────────────────────────────────


class TestGetDueItems:
    async def test_empty_queue(self, client):
        resp = await client.get("/review/sentence-items")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_due_item(self, client, db_session):
        pt = await _seed_parsed_text(db_session)
        s = await _seed_sentence(db_session, pt.id, "La casa es muy grande aquí.")
        await _seed_review_item(db_session, s.id, due_offset_days=0)

        resp = await client.get("/review/sentence-items")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["item_type"] == "cloze"
        assert items[0]["sentence_text"] == "La casa es muy grande aquí."

    async def test_future_item_not_returned(self, client, db_session):
        pt = await _seed_parsed_text(db_session)
        s = await _seed_sentence(db_session, pt.id, "Ella trabaja mucho en casa.")
        await _seed_review_item(db_session, s.id, due_offset_days=5)  # due in future

        resp = await client.get("/review/sentence-items")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_language_filter(self, client, db_session):
        pt_es = await _seed_parsed_text(db_session, language="es")
        pt_fr = await _seed_parsed_text(db_session, language="fr")

        s_es = await _seed_sentence(db_session, pt_es.id, "El niño juega en el parque.")
        s_fr = await _seed_sentence(db_session, pt_fr.id, "Le garçon joue dans le parc.")

        await _seed_review_item(db_session, s_es.id, language="es")
        await _seed_review_item(db_session, s_fr.id, language="fr")

        resp = await client.get("/review/sentence-items?language=es")
        assert resp.status_code == 200
        items = resp.json()
        assert all(i["language"] == "es" for i in items)
        assert len(items) == 1

    async def test_limit_respected(self, client, db_session):
        pt = await _seed_parsed_text(db_session)
        for i in range(5):
            s = await _seed_sentence(db_session, pt.id, f"La frase número {i} tiene palabras.")
            await _seed_review_item(
                db_session, s.id, target_span=f"frase{i}", answer=f"frase{i}",
                prompt=f"La ___ número {i} tiene palabras."
            )

        resp = await client.get("/review/sentence-items?limit=3")
        assert resp.status_code == 200
        assert len(resp.json()) <= 3

    async def test_item_without_user_row_is_due(self, client, db_session):
        pt = await _seed_parsed_text(db_session)
        s = await _seed_sentence(db_session, pt.id, "Los estudiantes aprenden mucho.")
        # Seed item row without a user_sentence_review row
        row = SentenceReviewItemRow(
            sentence_id=s.id,
            language="es",
            item_type="cloze",
            prompt="Los ___ aprenden mucho.",
            target_span="estudiantes",
            answer="estudiantes",
        )
        db_session.add(row)
        await db_session.commit()

        resp = await client.get("/review/sentence-items")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["total_reviews"] == 0


# ── GET /review/sentence-items/stats ─────────────────────────────────────────


class TestStats:
    async def test_empty_stats(self, client):
        resp = await client.get("/review/sentence-items/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["due_now"] == 0
        assert data["total_items"] == 0

    async def test_stats_reflect_items(self, client, db_session):
        pt = await _seed_parsed_text(db_session)
        s1 = await _seed_sentence(db_session, pt.id, "La ciudad tiene muchos edificios altos.")
        s2 = await _seed_sentence(db_session, pt.id, "El hombre trabaja en la oficina principal.")
        await _seed_review_item(db_session, s1.id, item_type="cloze", target_span="ciudad")
        await _seed_review_item(db_session, s2.id, item_type="grammar_transform", target_span="trabaja")

        resp = await client.get("/review/sentence-items/stats")
        data = resp.json()
        assert data["total_items"] == 2
        assert data["per_type"]["cloze"] == 1
        assert data["per_type"]["grammar_transform"] == 1


# ── POST /review/sentence-items/mine ─────────────────────────────────────────


class TestMine:
    async def test_mine_empty_history(self, client):
        resp = await client.post("/review/sentence-items/mine")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mined"] == 0
        assert data["sentences_processed"] == 0

    async def test_mine_seeds_items_from_parsed_text(self, client, db_session):
        pt = await _seed_parsed_text(db_session)
        s = await _seed_sentence(
            db_session, pt.id,
            "La maestra enseña español con mucha paciencia cada día."
        )
        obj = await _seed_canonical_object(db_session, label="maestra", surface_forms=["maestra"])
        await _seed_sentence_object(db_session, s.id, obj.id)

        resp = await client.post("/review/sentence-items/mine")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mined"] >= 1
        assert data["sentences_processed"] >= 1

    async def test_mine_idempotent(self, client, db_session):
        pt = await _seed_parsed_text(db_session)
        s = await _seed_sentence(
            db_session, pt.id,
            "El director habla con los estudiantes frecuentemente."
        )
        obj = await _seed_canonical_object(db_session, label="director", surface_forms=["director"])
        await _seed_sentence_object(db_session, s.id, obj.id)

        resp1 = await client.post("/review/sentence-items/mine")
        mined_first = resp1.json()["mined"]

        resp2 = await client.post("/review/sentence-items/mine")
        mined_second = resp2.json()["mined"]
        skipped_second = resp2.json()["skipped_duplicate"]

        assert mined_first >= 1
        assert mined_second == 0
        assert skipped_second >= 1

    async def test_mine_language_filter(self, client, db_session):
        pt_es = await _seed_parsed_text(db_session, language="es")
        pt_fr = await _seed_parsed_text(db_session, language="fr")

        s_es = await _seed_sentence(db_session, pt_es.id, "La niña canta una canción bonita.")
        s_fr = await _seed_sentence(db_session, pt_fr.id, "La fille chante une belle chanson.")

        obj_es = await _seed_canonical_object(db_session, language="es", label="niña", surface_forms=["niña"])
        obj_fr = await _seed_canonical_object(db_session, language="fr", label="fille", surface_forms=["fille"])
        await _seed_sentence_object(db_session, s_es.id, obj_es.id)
        await _seed_sentence_object(db_session, s_fr.id, obj_fr.id)

        resp = await client.post("/review/sentence-items/mine?language=es")
        data = resp.json()
        assert data["mined"] >= 1

        # Check that only Spanish items were created
        stats_resp = await client.get("/review/sentence-items/stats?language=fr")
        assert stats_resp.json()["total_items"] == 0


# ── POST /review/sentence-items/{id}/submit ──────────────────────────────────


class TestSubmitReview:
    async def test_submit_quality_3(self, client, db_session):
        pt = await _seed_parsed_text(db_session)
        s = await _seed_sentence(db_session, pt.id, "El gato duerme en el sofá grande.")
        item = await _seed_review_item(db_session, s.id)

        resp = await client.post(
            f"/review/sentence-items/{item.id}/submit",
            json={"quality": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["item_id"] == item.id
        assert data["next_interval_days"] >= 1
        assert 0.0 <= data["mastery_score"] <= 1.0
        assert data["total_reviews"] == 1
        assert data["streak"] == 1

    async def test_submit_quality_1_resets_streak(self, client, db_session):
        pt = await _seed_parsed_text(db_session)
        s = await _seed_sentence(db_session, pt.id, "La profesora explica bien la gramática.")
        item = await _seed_review_item(db_session, s.id)

        # First: quality 3 (builds streak)
        await client.post(f"/review/sentence-items/{item.id}/submit", json={"quality": 3})
        await client.post(f"/review/sentence-items/{item.id}/submit", json={"quality": 3})

        # Then: quality 1 (resets streak)
        resp = await client.post(f"/review/sentence-items/{item.id}/submit", json={"quality": 1})
        data = resp.json()
        assert data["streak"] == 0

    async def test_submit_quality_2_preserves_streak(self, client, db_session):
        pt = await _seed_parsed_text(db_session)
        s = await _seed_sentence(db_session, pt.id, "El médico trabaja en el hospital central.")
        item = await _seed_review_item(db_session, s.id)

        await client.post(f"/review/sentence-items/{item.id}/submit", json={"quality": 3})
        resp = await client.post(f"/review/sentence-items/{item.id}/submit", json={"quality": 2})
        data = resp.json()
        # streak should be preserved (quality 2 = hard, not a failure)
        assert data["streak"] >= 1

    async def test_submit_quality_4_builds_streak(self, client, db_session):
        pt = await _seed_parsed_text(db_session)
        s = await _seed_sentence(db_session, pt.id, "Los alumnos estudian en la biblioteca.")
        item = await _seed_review_item(db_session, s.id)

        for _ in range(3):
            await client.post(f"/review/sentence-items/{item.id}/submit", json={"quality": 4})

        resp = await client.post(f"/review/sentence-items/{item.id}/submit", json={"quality": 4})
        assert resp.json()["streak"] == 4

    async def test_submit_increases_total_reviews(self, client, db_session):
        pt = await _seed_parsed_text(db_session)
        s = await _seed_sentence(db_session, pt.id, "Las flores crecen en el jardín primaveral.")
        item = await _seed_review_item(db_session, s.id)

        for i in range(1, 4):
            resp = await client.post(
                f"/review/sentence-items/{item.id}/submit", json={"quality": 3}
            )
            assert resp.json()["total_reviews"] == i

    async def test_submit_invalid_quality(self, client, db_session):
        pt = await _seed_parsed_text(db_session)
        s = await _seed_sentence(db_session, pt.id, "El perro corre muy rápido en el parque.")
        item = await _seed_review_item(db_session, s.id)

        resp = await client.post(
            f"/review/sentence-items/{item.id}/submit", json={"quality": 5}
        )
        assert resp.status_code == 422

    async def test_mastery_score_before_is_zero_for_new_item(self, client, db_session):
        pt = await _seed_parsed_text(db_session)
        s = await _seed_sentence(db_session, pt.id, "La luna brilla mucho en el cielo.")
        # Seed item without a user review row
        row = SentenceReviewItemRow(
            sentence_id=s.id,
            language="es",
            item_type="cloze",
            prompt="La ___ brilla mucho en el cielo.",
            target_span="luna",
            answer="luna",
        )
        db_session.add(row)
        await db_session.commit()
        await db_session.refresh(row)

        resp = await client.post(
            f"/review/sentence-items/{row.id}/submit", json={"quality": 3}
        )
        assert resp.status_code == 200
        assert resp.json()["mastery_score_before"] == 0.0

    async def test_next_interval_at_least_1_day(self, client, db_session):
        pt = await _seed_parsed_text(db_session)
        s = await _seed_sentence(db_session, pt.id, "El río fluye hacia el mar lejano.")
        item = await _seed_review_item(db_session, s.id)

        for q in (1, 2, 3, 4):
            item2 = await _seed_review_item(
                db_session, s.id,
                target_span=f"río-q{q}",
                answer=f"río",
                prompt=f"El ___ q{q} fluye.",
            )
            resp = await client.post(
                f"/review/sentence-items/{item2.id}/submit", json={"quality": q}
            )
            assert resp.json()["next_interval_days"] >= 1
