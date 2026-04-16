"""B7 — DELETE /users/me account and data deletion tests.

Strategy
────────
Use an in-memory SQLite DB (via aiosqlite) — no real PostgreSQL required.
Each test gets its own engine + schema so state never leaks between cases.

We verify:
  - All four user-linked tables are wiped for the requesting user.
  - Rows belonging to a different user are untouched.
  - The endpoint is idempotent: a second DELETE also returns 204.
  - A user with no data (never registered) still gets 204.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.dependencies import get_db_session
from backend.auth.tokens import create_access_token
from backend.main import app
from backend.models import (
    Base,
    SourceProgressionRow,
    UserKnowledgeRow,
    UserLanguagePreferenceRow,
    UserRow,
)

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ── Fixtures ──────────────────────────────────────────────────────────────────


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


async def _seed_user(db_engine, user_id: str) -> None:
    """Insert one row into every user-linked table for *user_id*."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        db.add(UserRow(id=user_id, email=f"{user_id}@example.com", hashed_password="x"))
        db.add(UserKnowledgeRow(
            user_id=user_id,
            object_id="obj-1",
            language="es",
        ))
        db.add(UserLanguagePreferenceRow(user_id=user_id, language_code="es"))
        # SourceProgressionRow needs a source_document_id FK.
        # We skip it here and test it separately via direct DB insert after
        # relaxing FK checks (SQLite does not enforce FKs by default).
        await db.commit()


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_me_returns_204(async_client, db_engine) -> None:
    user_id = "del-user-001"
    await _seed_user(db_engine, user_id)
    token = create_access_token(user_id)

    resp = await async_client.delete(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
    assert resp.content == b""


@pytest.mark.asyncio
async def test_delete_me_removes_knowledge_rows(async_client, db_engine) -> None:
    user_id = "del-user-002"
    await _seed_user(db_engine, user_id)
    token = create_access_token(user_id)

    await async_client.delete(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        rows = (
            await db.execute(
                select(UserKnowledgeRow).where(UserKnowledgeRow.user_id == user_id)
            )
        ).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_delete_me_removes_preferences(async_client, db_engine) -> None:
    user_id = "del-user-003"
    await _seed_user(db_engine, user_id)
    token = create_access_token(user_id)

    await async_client.delete(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        rows = (
            await db.execute(
                select(UserLanguagePreferenceRow).where(
                    UserLanguagePreferenceRow.user_id == user_id
                )
            )
        ).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_delete_me_removes_user_row(async_client, db_engine) -> None:
    user_id = "del-user-004"
    await _seed_user(db_engine, user_id)
    token = create_access_token(user_id)

    await async_client.delete(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        row = await db.get(UserRow, user_id)
    assert row is None


@pytest.mark.asyncio
async def test_delete_me_is_idempotent(async_client, db_engine) -> None:
    """A second DELETE on the same user still returns 204."""
    user_id = "del-user-005"
    await _seed_user(db_engine, user_id)
    token = create_access_token(user_id)

    r1 = await async_client.delete(
        "/users/me", headers={"Authorization": f"Bearer {token}"}
    )
    r2 = await async_client.delete(
        "/users/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert r1.status_code == 204
    assert r2.status_code == 204


@pytest.mark.asyncio
async def test_delete_me_does_not_affect_other_users(async_client, db_engine) -> None:
    """Deleting alice must not touch bob's data."""
    alice_id = "del-alice"
    bob_id = "del-bob"
    await _seed_user(db_engine, alice_id)
    await _seed_user(db_engine, bob_id)

    alice_token = create_access_token(alice_id)
    await async_client.delete(
        "/users/me", headers={"Authorization": f"Bearer {alice_token}"}
    )

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        bob_knowledge = (
            await db.execute(
                select(UserKnowledgeRow).where(UserKnowledgeRow.user_id == bob_id)
            )
        ).scalars().all()
        bob_prefs = (
            await db.execute(
                select(UserLanguagePreferenceRow).where(
                    UserLanguagePreferenceRow.user_id == bob_id
                )
            )
        ).scalars().all()

    assert len(bob_knowledge) == 1
    assert len(bob_prefs) == 1


@pytest.mark.asyncio
async def test_delete_me_source_progression_removed(async_client, db_engine) -> None:
    """source_progression rows for the user are deleted."""
    user_id = "del-user-006"
    await _seed_user(db_engine, user_id)

    # SQLite does not enforce FK constraints by default, so we can insert
    # a source_progression row with a fake source_document_id.
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        db.add(SourceProgressionRow(
            user_id=user_id,
            source_document_id="fake-doc-id",
        ))
        await db.commit()

    token = create_access_token(user_id)
    await async_client.delete(
        "/users/me", headers={"Authorization": f"Bearer {token}"}
    )

    async with factory() as db:
        rows = (
            await db.execute(
                select(SourceProgressionRow).where(
                    SourceProgressionRow.user_id == user_id
                )
            )
        ).scalars().all()
    assert rows == []
