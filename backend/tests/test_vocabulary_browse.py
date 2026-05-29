"""Tests for GET /users/me/vocabulary (paginated vocabulary browser)."""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.dependencies import get_current_user, get_db_session
from backend.main import app
from backend.models import Base, CanonicalObjectRow, UserKnowledgeRow
from backend.parsing.canonical import canonical_object_id
from backend.srs.knowledge import DEFAULT_USER_ID


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_client(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        # Spanish vocabulary with varying mastery
        items = [
            ("es", "vocabulary", "gato",    "cat",  0.9, 10, "A1", "production"),
            ("es", "vocabulary", "perro",   "dog",  0.5,  3, "A1", "recognition"),
            ("es", "vocabulary", "empresa", "firm", 0.3,  1, "B1", "recognition"),
            # French item
            ("fr", "vocabulary", "chat",    "cat",  0.7,  5, "A1", "recognition"),
            # Spanish conjugation (different type)
            ("es", "conjugation", "hablar", None,   0.2,  1, None, None),
        ]
        for lang, type_, word, gloss, mastery, reviews, cefr, stage in items:
            obj_id = canonical_object_id(lang, type_, word)
            ld: dict = {}
            if gloss:
                ld["gloss"] = gloss
            if cefr:
                ld["cefr_level"] = cefr
            session.add(CanonicalObjectRow(
                id=obj_id, language=lang, type=type_,
                canonical_form=word, display_label=word,
                lesson_data=ld,
            ))
            session.add(UserKnowledgeRow(
                user_id=DEFAULT_USER_ID, object_id=obj_id,
                language=lang, mastery_score=mastery, total_reviews=reviews,
                progression_stage=stage,
            ))
        await session.commit()

    async def _override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = lambda: DEFAULT_USER_ID
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_current_user, None)


# ── Response shape ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_response_shape(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data


@pytest.mark.asyncio
async def test_items_have_required_fields(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary")
    data = resp.json()
    for item in data["items"]:
        assert "canonical_form" in item
        assert "display_label" in item
        assert "language" in item
        assert "mastery_score" in item
        assert "total_reviews" in item


# ── Default filters ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_default_returns_vocabulary_type_only(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary")
    data = resp.json()
    types = {i["type"] for i in data["items"]}
    assert "conjugation" not in types
    assert "vocabulary" in types


@pytest.mark.asyncio
async def test_type_all_includes_conjugations(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary?type=all")
    data = resp.json()
    types = {i["type"] for i in data["items"]}
    assert "conjugation" in types
    assert "vocabulary" in types


# ── Language filter ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_language_filter(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary?language=fr")
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["canonical_form"] == "chat"
    assert data["items"][0]["language"] == "fr"


@pytest.mark.asyncio
async def test_spanish_only(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary?language=es")
    data = resp.json()
    words = {i["canonical_form"] for i in data["items"]}
    assert "gato" in words
    assert "perro" in words
    assert "chat" not in words


# ── Sort ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sort_mastery_default(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary?language=es")
    data = resp.json()
    scores = [i["mastery_score"] for i in data["items"]]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_sort_alpha(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary?language=es&sort=alpha")
    data = resp.json()
    words = [i["canonical_form"] for i in data["items"]]
    assert words == sorted(words)


# ── Search ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_q(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary?q=gat")
    data = resp.json()
    words = {i["canonical_form"] for i in data["items"]}
    assert "gato" in words
    assert "perro" not in words


@pytest.mark.asyncio
async def test_search_no_match(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary?q=zzznomatch")
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


# ── Gloss and CEFR fields ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gloss_populated(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary?language=es&q=gato")
    data = resp.json()
    assert data["items"][0]["gloss"] == "cat"


@pytest.mark.asyncio
async def test_cefr_level_populated(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary?language=es&q=gato")
    data = resp.json()
    assert data["items"][0]["cefr_level"] == "A1"


# ── CEFR level filter ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_level_filter_single(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary?language=es&level=B1")
    data = resp.json()
    words = {i["canonical_form"] for i in data["items"]}
    assert "empresa" in words
    assert "gato" not in words
    assert "perro" not in words


@pytest.mark.asyncio
async def test_level_filter_multi(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary?language=es&level=A1,B1")
    data = resp.json()
    words = {i["canonical_form"] for i in data["items"]}
    assert "gato" in words
    assert "empresa" in words


# ── Pagination ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_limit_offset(seeded_client):
    resp1 = await seeded_client.get("/users/me/vocabulary?language=es&limit=1&offset=0&sort=alpha")
    resp2 = await seeded_client.get("/users/me/vocabulary?language=es&limit=1&offset=1&sort=alpha")
    w1 = resp1.json()["items"][0]["canonical_form"]
    w2 = resp2.json()["items"][0]["canonical_form"]
    assert w1 != w2


@pytest.mark.asyncio
async def test_total_reflects_unfiltered_count(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary?language=es&limit=1")
    data = resp.json()
    assert data["total"] == 3  # gato, perro, empresa (all es vocabulary)
    assert len(data["items"]) == 1


# ── Empty user ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_user_returns_empty_list(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = lambda: "nobody"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/users/me/vocabulary")
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_current_user, None)
