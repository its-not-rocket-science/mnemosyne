"""User isolation tests.

Verifies that:
  1. get_current_user resolves the X-User-Id header correctly.
  2. Routes fall back to DEFAULT_USER_ID when the header is absent.
  3. Knowledge state is strictly per-user: reviews by alice do not
     affect bob's dashboard, metrics, or recommendation results.
  4. Multiple languages are independently isolated per user.
  5. Language preferences are per-user and per-language.

Test strategy
─────────────
All persistence tests run against an in-memory SQLite database (aiosqlite)
so no live PostgreSQL or Redis instance is required.  The get_db_session
dependency is overridden per-test via app.dependency_overrides.  An
AsyncClient from httpx drives the ASGI app directly.

User identity is communicated via the ``X-User-Id`` header — the same
mechanism production clients will use until JWT auth is added.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.dependencies import get_current_user, get_db_session
from backend.main import app
from backend.models import Base, UserKnowledgeRow, UserLanguagePreferenceRow
from backend.srs.knowledge import DEFAULT_USER_ID

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(_TEST_DB_URL)
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


# ── get_current_user unit tests ───────────────────────────────────────────────


def test_get_current_user_returns_default_when_header_absent() -> None:
    result = get_current_user(x_user_id=None)
    assert result == DEFAULT_USER_ID


def test_get_current_user_returns_default_for_empty_string() -> None:
    result = get_current_user(x_user_id="")
    assert result == DEFAULT_USER_ID


def test_get_current_user_returns_default_for_whitespace_only() -> None:
    result = get_current_user(x_user_id="   ")
    assert result == DEFAULT_USER_ID


def test_get_current_user_returns_header_value() -> None:
    result = get_current_user(x_user_id="alice")
    assert result == "alice"


def test_get_current_user_strips_whitespace() -> None:
    result = get_current_user(x_user_id="  bob  ")
    assert result == "bob"


def test_get_current_user_default_is_string_default() -> None:
    assert DEFAULT_USER_ID == "default"


# ── Header forwarding — route level ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_review_uses_header_user_id(async_client, db_engine) -> None:
    """A review submitted with X-User-Id: alice creates a row for alice."""
    resp = await async_client.post(
        "/review",
        json={"object_id": "en:vocab:hello", "quality": 3},
        headers={"X-User-Id": "alice"},
    )
    assert resp.status_code == 200

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        rows = (await db.execute(select(UserKnowledgeRow))).scalars().all()

    assert len(rows) == 1
    assert rows[0].user_id == "alice"


@pytest.mark.asyncio
async def test_review_without_header_uses_default(async_client, db_engine) -> None:
    """A review with no header falls back to DEFAULT_USER_ID."""
    resp = await async_client.post(
        "/review",
        json={"object_id": "en:vocab:world", "quality": 3},
    )
    assert resp.status_code == 200

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        rows = (await db.execute(select(UserKnowledgeRow))).scalars().all()

    assert len(rows) == 1
    assert rows[0].user_id == DEFAULT_USER_ID


# ── Knowledge isolation ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_review_knowledge_isolated_between_users(async_client, db_engine) -> None:
    """alice and bob each review the same object; rows must be separate."""
    obj = "en:vocab:cat"

    await async_client.post(
        "/review",
        json={"object_id": obj, "quality": 3},
        headers={"X-User-Id": "alice"},
    )
    await async_client.post(
        "/review",
        json={"object_id": obj, "quality": 1},
        headers={"X-User-Id": "bob"},
    )

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        rows = (await db.execute(select(UserKnowledgeRow))).scalars().all()

    assert len(rows) == 2
    user_ids = {r.user_id for r in rows}
    assert user_ids == {"alice", "bob"}

    alice_row = next(r for r in rows if r.user_id == "alice")
    bob_row   = next(r for r in rows if r.user_id == "bob")

    # Same object, but independent FSRS states.
    assert alice_row.object_id == bob_row.object_id == obj
    assert alice_row.fsrs_state != bob_row.fsrs_state


@pytest.mark.asyncio
async def test_parse_seeds_knowledge_for_correct_user(async_client, db_engine) -> None:
    """Parsing text with X-User-Id: carol creates UserKnowledge rows for carol only."""
    resp = await async_client.post(
        "/parse",
        json={"text": "Hola.", "language": "es"},
        headers={"X-User-Id": "carol"},
    )
    assert resp.status_code == 200

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        rows = (await db.execute(select(UserKnowledgeRow))).scalars().all()

    assert all(r.user_id == "carol" for r in rows), (
        f"Expected all rows for carol; got {[r.user_id for r in rows]}"
    )


@pytest.mark.asyncio
async def test_parse_two_users_independent_knowledge(async_client, db_engine) -> None:
    """Two users parsing different sentences accumulate separate knowledge rows."""
    # Use distinct sentences so each user gets their own canonical objects.
    # (Using identical text would require updating the same canonical object rows
    # in two sequential sessions, which exercises SQLite locking rather than
    # user isolation.  Isolation via shared canonical objects is covered by the
    # review-based isolation tests above.)
    r1 = await async_client.post(
        "/parse",
        json={"text": "Hola amigo.", "language": "es"},
        headers={"X-User-Id": "dave"},
    )
    r2 = await async_client.post(
        "/parse",
        json={"text": "Buenos días.", "language": "es"},
        headers={"X-User-Id": "eve"},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        rows = (await db.execute(select(UserKnowledgeRow))).scalars().all()

    user_ids = {r.user_id for r in rows}
    assert "dave" in user_ids
    assert "eve"  in user_ids
    # No rows bleed between users.
    assert not any(r.user_id not in {"dave", "eve"} for r in rows)


# ── Multi-language isolation ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_knowledge_isolated_across_languages(async_client, db_engine) -> None:
    """alice's Spanish reviews and bob's English reviews do not mix."""
    await async_client.post(
        "/review",
        json={"object_id": "es:vocab:gato", "quality": 4},
        headers={"X-User-Id": "alice"},
    )
    await async_client.post(
        "/review",
        json={"object_id": "en:vocab:cat", "quality": 2},
        headers={"X-User-Id": "bob"},
    )

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        alice_rows = (
            await db.execute(
                select(UserKnowledgeRow).where(UserKnowledgeRow.user_id == "alice")
            )
        ).scalars().all()
        bob_rows = (
            await db.execute(
                select(UserKnowledgeRow).where(UserKnowledgeRow.user_id == "bob")
            )
        ).scalars().all()

    assert len(alice_rows) == 1
    assert alice_rows[0].object_id == "es:vocab:gato"

    assert len(bob_rows) == 1
    assert bob_rows[0].object_id == "en:vocab:cat"


@pytest.mark.asyncio
async def test_one_user_multiple_languages(async_client, db_engine) -> None:
    """A single user studying both Spanish and Latin accumulates independent rows."""
    await async_client.post(
        "/review",
        json={"object_id": "es:vocab:amor", "quality": 3},
        headers={"X-User-Id": "multilingual"},
    )
    await async_client.post(
        "/review",
        json={"object_id": "la:vocab:amor", "quality": 3},
        headers={"X-User-Id": "multilingual"},
    )

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        rows = (
            await db.execute(
                select(UserKnowledgeRow).where(UserKnowledgeRow.user_id == "multilingual")
            )
        ).scalars().all()

    assert len(rows) == 2
    object_ids = {r.object_id for r in rows}
    assert "es:vocab:amor" in object_ids
    assert "la:vocab:amor" in object_ids


# ── Language preferences isolation ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_preference_get_defaults_when_no_row(async_client) -> None:
    """GET preferences for an unsaved language returns all-default values."""
    resp = await async_client.get(
        "/users/me/languages/zh/preferences",
        headers={"X-User-Id": "alice"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["language_code"] == "zh"
    assert data["show_transliteration"] is True
    assert data["script_preference"] is None
    assert data["lesson_mode_override"] is None


@pytest.mark.asyncio
async def test_preference_put_and_get_roundtrip(async_client) -> None:
    """A saved preference is retrievable with the correct values."""
    payload = {
        "language_code": "zh",
        "show_transliteration": False,
        "script_preference": "simplified",
        "lesson_mode_override": "dictionary",
    }
    put_resp = await async_client.put(
        "/users/me/languages/zh/preferences",
        json=payload,
        headers={"X-User-Id": "alice"},
    )
    assert put_resp.status_code == 200

    get_resp = await async_client.get(
        "/users/me/languages/zh/preferences",
        headers={"X-User-Id": "alice"},
    )
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["show_transliteration"] is False
    assert data["script_preference"] == "simplified"
    assert data["lesson_mode_override"] == "dictionary"


@pytest.mark.asyncio
async def test_preferences_isolated_between_users(async_client) -> None:
    """alice's Chinese preferences do not affect bob's Chinese defaults."""
    await async_client.put(
        "/users/me/languages/zh/preferences",
        json={
            "language_code": "zh",
            "show_transliteration": False,
            "script_preference": "traditional",
            "lesson_mode_override": None,
        },
        headers={"X-User-Id": "alice"},
    )

    bob_resp = await async_client.get(
        "/users/me/languages/zh/preferences",
        headers={"X-User-Id": "bob"},
    )
    assert bob_resp.status_code == 200
    bob_data = bob_resp.json()
    # bob has not set any preferences — must get defaults, not alice's values
    assert bob_data["show_transliteration"] is True
    assert bob_data["script_preference"] is None


@pytest.mark.asyncio
async def test_preferences_isolated_across_languages_for_same_user(async_client) -> None:
    """alice's Arabic preference does not bleed into her Chinese preference."""
    await async_client.put(
        "/users/me/languages/ar/preferences",
        json={
            "language_code": "ar",
            "show_transliteration": False,
            "script_preference": "modern",
            "lesson_mode_override": "dictionary",
        },
        headers={"X-User-Id": "alice"},
    )

    zh_resp = await async_client.get(
        "/users/me/languages/zh/preferences",
        headers={"X-User-Id": "alice"},
    )
    assert zh_resp.status_code == 200
    zh_data = zh_resp.json()
    assert zh_data["show_transliteration"] is True
    assert zh_data["script_preference"] is None
    assert zh_data["lesson_mode_override"] is None


@pytest.mark.asyncio
async def test_get_all_preferences_returns_only_saved_languages(async_client) -> None:
    """GET /users/me/preferences lists only languages with saved rows."""
    await async_client.put(
        "/users/me/languages/ar/preferences",
        json={"language_code": "ar", "show_transliteration": False,
              "script_preference": None, "lesson_mode_override": None},
        headers={"X-User-Id": "frank"},
    )
    await async_client.put(
        "/users/me/languages/la/preferences",
        json={"language_code": "la", "show_transliteration": True,
              "script_preference": None, "lesson_mode_override": "dictionary"},
        headers={"X-User-Id": "frank"},
    )

    resp = await async_client.get(
        "/users/me/preferences",
        headers={"X-User-Id": "frank"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "frank"
    codes = {lang["language_code"] for lang in data["languages"]}
    assert codes == {"ar", "la"}


@pytest.mark.asyncio
async def test_get_all_preferences_empty_for_new_user(async_client) -> None:
    """A brand-new user has an empty preferences list."""
    resp = await async_client.get(
        "/users/me/preferences",
        headers={"X-User-Id": "brand-new-user"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "brand-new-user"
    assert data["languages"] == []


@pytest.mark.asyncio
async def test_preference_upsert_updates_existing_row(async_client) -> None:
    """A second PUT on the same (user, language) updates rather than duplicates."""
    lang_url = "/users/me/languages/zh/preferences"
    headers = {"X-User-Id": "alice"}

    await async_client.put(
        lang_url,
        json={"language_code": "zh", "show_transliteration": True,
              "script_preference": "simplified", "lesson_mode_override": None},
        headers=headers,
    )
    await async_client.put(
        lang_url,
        json={"language_code": "zh", "show_transliteration": False,
              "script_preference": "traditional", "lesson_mode_override": "vocabulary"},
        headers=headers,
    )

    resp = await async_client.get(lang_url, headers=headers)
    data = resp.json()
    assert data["show_transliteration"] is False
    assert data["script_preference"] == "traditional"
    assert data["lesson_mode_override"] == "vocabulary"

    # Verify only one row exists in the DB.
    all_resp = await async_client.get("/users/me/preferences", headers=headers)
    zh_rows = [l for l in all_resp.json()["languages"] if l["language_code"] == "zh"]
    assert len(zh_rows) == 1
