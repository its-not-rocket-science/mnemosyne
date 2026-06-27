"""Tests for GET /users/me/vocabulary/export (CSV and Anki formats)."""
from __future__ import annotations

import csv
import io

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
async def async_client(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db_session, None)


@pytest_asyncio.fixture
async def seeded_client(db_engine):
    """Client with two vocabulary items pre-seeded in the DB."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        # Two Spanish vocabulary items
        for word, gloss in [("gato", "cat"), ("perro", "dog")]:
            obj_id = canonical_object_id("es", "vocabulary", word)
            session.add(CanonicalObjectRow(
                id=obj_id, language="es", type="vocabulary",
                canonical_form=word, display_label=word,
                lesson_data={"gloss": gloss},
            ))
            session.add(UserKnowledgeRow(
                user_id=DEFAULT_USER_ID, object_id=obj_id,
                language="es", mastery_score=0.5, total_reviews=3,
                progression_stage="recognition",
            ))
        # One French item
        fr_id = canonical_object_id("fr", "vocabulary", "chat")
        session.add(CanonicalObjectRow(
            id=fr_id, language="fr", type="vocabulary",
            canonical_form="chat", display_label="chat",
            lesson_data={"gloss": "cat"},
        ))
        session.add(UserKnowledgeRow(
            user_id=DEFAULT_USER_ID, object_id=fr_id,
            language="fr", mastery_score=0.2, total_reviews=1,
            progression_stage="recognition",
        ))
        # One conjugation item (should be excluded by default type=vocabulary filter)
        conj_id = canonical_object_id("es", "conjugation", "hablar")
        session.add(CanonicalObjectRow(
            id=conj_id, language="es", type="conjugation",
            canonical_form="hablar", display_label="hablar",
            lesson_data={},
        ))
        session.add(UserKnowledgeRow(
            user_id=DEFAULT_USER_ID, object_id=conj_id,
            language="es", mastery_score=0.1, total_reviews=1,
        ))
        await session.commit()

    async def _override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db_session, None)


# ── Empty state ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_csv_empty_user_returns_header_only(async_client):
    resp = await async_client.get(
        "/users/me/vocabulary/export",
        headers={"X-User-Id": "nobody"},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    assert rows == []


@pytest.mark.asyncio
async def test_anki_empty_user_returns_header_comments_only(async_client):
    resp = await async_client.get(
        "/users/me/vocabulary/export?format=anki",
        headers={"X-User-Id": "nobody"},
    )
    assert resp.status_code == 200
    lines = [l for l in resp.text.splitlines() if l.strip()]
    # All non-empty lines should be Anki comment/metadata lines
    assert all(l.startswith("#") for l in lines)


# ── CSV format ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_csv_contains_seeded_vocabulary(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary/export")
    assert resp.status_code == 200
    assert 'attachment; filename="mnemosyne_vocabulary.csv"' in resp.headers.get(
        "content-disposition", ""
    )
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    words = {r["word"] for r in rows}
    assert "gato" in words
    assert "perro" in words
    assert "chat" in words


@pytest.mark.asyncio
async def test_csv_default_type_excludes_conjugations(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary/export")
    reader = csv.DictReader(io.StringIO(resp.text))
    types = {r["type"] for r in reader}
    assert "conjugation" not in types


@pytest.mark.asyncio
async def test_csv_type_all_includes_conjugations(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary/export?type=all")
    reader = csv.DictReader(io.StringIO(resp.text))
    types = {r["type"] for r in reader}
    assert "conjugation" in types
    assert "vocabulary" in types


@pytest.mark.asyncio
async def test_csv_language_filter(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary/export?language=fr")
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["word"] == "chat"
    assert rows[0]["language"] == "fr"


@pytest.mark.asyncio
async def test_csv_gloss_field_populated(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary/export?language=es")
    reader = csv.DictReader(io.StringIO(resp.text))
    glosses = {r["word"]: r["gloss"] for r in reader}
    assert glosses["gato"] == "cat"
    assert glosses["perro"] == "dog"


@pytest.mark.asyncio
async def test_csv_columns_present(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary/export")
    reader = csv.DictReader(io.StringIO(resp.text))
    assert reader.fieldnames == [
        "word", "display", "language", "type", "gloss",
        "cefr_level", "mastery_score", "total_reviews", "due_at", "progression_stage",
    ]


@pytest.mark.asyncio
async def test_csv_mastery_score_present(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary/export?language=es")
    reader = csv.DictReader(io.StringIO(resp.text))
    for row in reader:
        assert float(row["mastery_score"]) == pytest.approx(0.5, abs=0.001)
        assert row["total_reviews"] == "3"


# ── Anki format ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_anki_has_separator_comment(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary/export?format=anki")
    assert "#separator:tab" in resp.text


@pytest.mark.asyncio
async def test_anki_contains_tab_separated_rows(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary/export?format=anki")
    data_lines = [l for l in resp.text.splitlines() if l and not l.startswith("#")]
    assert len(data_lines) == 3  # gato, perro, chat
    for line in data_lines:
        parts = line.split("\t")
        assert len(parts) == 3, f"Expected 3 tab-separated columns, got: {line!r}"


@pytest.mark.asyncio
async def test_anki_front_is_canonical_form(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary/export?format=anki&language=es")
    data_lines = [l for l in resp.text.splitlines() if l and not l.startswith("#")]
    fronts = {line.split("\t")[0] for line in data_lines}
    assert fronts == {"gato", "perro"}


@pytest.mark.asyncio
async def test_anki_back_uses_gloss(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary/export?format=anki&language=fr")
    data_lines = [l for l in resp.text.splitlines() if l and not l.startswith("#")]
    assert len(data_lines) == 1
    front, back, tags = data_lines[0].split("\t")
    assert front == "chat"
    assert back == "cat"
    assert "fr" in tags


@pytest.mark.asyncio
async def test_anki_filename(seeded_client):
    resp = await seeded_client.get("/users/me/vocabulary/export?format=anki")
    assert 'filename="mnemosyne_vocabulary.txt"' in resp.headers.get(
        "content-disposition", ""
    )


@pytest.mark.asyncio
async def test_anki_language_filter(seeded_client):
    resp = await seeded_client.get(
        "/users/me/vocabulary/export?format=anki&language=es"
    )
    data_lines = [l for l in resp.text.splitlines() if l and not l.startswith("#")]
    assert len(data_lines) == 2


# ── Invalid format ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_format_returns_422(async_client):
    resp = await async_client.get("/users/me/vocabulary/export?format=xlsx")
    assert resp.status_code == 422
