"""Tests for JWT authentication.

Covers:
  - POST /auth/register — happy path, duplicate email, short password
  - POST /auth/login    — happy path, wrong password, unknown email
  - JWT token decoding in get_current_user (Bearer header takes priority
    over X-User-Id; invalid token falls back gracefully)
  - Token round-trip: register → use token on /users/me/preferences

All tests use an in-memory SQLite database (aiosqlite) via the same
dependency-override pattern as test_user_isolation.py.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.dependencies import get_current_user, get_db_session
from backend.auth.tokens import create_access_token, decode_access_token
from backend.main import app
from backend.models import Base

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


# ── Token unit tests ──────────────────────────────────────────────────────────


def test_create_and_decode_token() -> None:
    user_id = "some-uuid-1234"
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id


def test_decode_invalid_token_returns_none() -> None:
    assert decode_access_token("not.a.valid.token") is None


def test_decode_empty_string_returns_none() -> None:
    assert decode_access_token("") is None


# ── get_current_user with Bearer ──────────────────────────────────────────────


def test_get_current_user_bearer_takes_priority_over_header() -> None:
    user_id = "jwt-user-abc"
    token = create_access_token(user_id)
    result = get_current_user(
        authorization=f"Bearer {token}",
        x_user_id="header-user",
    )
    assert result == user_id


def test_get_current_user_bearer_invalid_falls_back_to_header() -> None:
    result = get_current_user(
        authorization="Bearer invalid.token.here",
        x_user_id="fallback-user",
    )
    assert result == "fallback-user"


def test_get_current_user_no_auth_returns_default() -> None:
    from backend.srs.knowledge import DEFAULT_USER_ID
    result = get_current_user(authorization=None, x_user_id=None)
    assert result == DEFAULT_USER_ID


# ── Register ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_creates_account_and_returns_token(async_client) -> None:
    resp = await async_client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "s3cr3tpass"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert "access_token" in data
    assert "user_id" in data
    # Token decodes to the returned user_id.
    assert decode_access_token(data["access_token"]) == data["user_id"]


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(async_client) -> None:
    payload = {"email": "bob@example.com", "password": "password1"}
    await async_client.post("/auth/register", json=payload)
    resp = await async_client.post("/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_email_case_insensitive(async_client) -> None:
    await async_client.post(
        "/auth/register",
        json={"email": "Carol@Example.COM", "password": "password1"},
    )
    resp = await async_client.post(
        "/auth/register",
        json={"email": "carol@example.com", "password": "password1"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_short_password_returns_422(async_client) -> None:
    resp = await async_client.post(
        "/auth/register",
        json={"email": "short@example.com", "password": "abc"},
    )
    assert resp.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_valid_credentials_returns_token(async_client) -> None:
    await async_client.post(
        "/auth/register",
        json={"email": "dave@example.com", "password": "correcthorse"},
    )
    resp = await async_client.post(
        "/auth/login",
        json={"email": "dave@example.com", "password": "correcthorse"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert decode_access_token(data["access_token"]) == data["user_id"]


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(async_client) -> None:
    await async_client.post(
        "/auth/register",
        json={"email": "eve@example.com", "password": "correcthorse"},
    )
    resp = await async_client.post(
        "/auth/login",
        json={"email": "eve@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(async_client) -> None:
    resp = await async_client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "doesnotmatter"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_and_unknown_have_same_error_message(async_client) -> None:
    """Identical error messages prevent email enumeration."""
    await async_client.post(
        "/auth/register",
        json={"email": "frank@example.com", "password": "realpassword"},
    )
    wrong_pw = await async_client.post(
        "/auth/login",
        json={"email": "frank@example.com", "password": "badpassword"},
    )
    unknown = await async_client.post(
        "/auth/login",
        json={"email": "ghost@example.com", "password": "anything"},
    )
    assert wrong_pw.json()["detail"] == unknown.json()["detail"]


# ── End-to-end: token used on a protected route ───────────────────────────────


@pytest.mark.asyncio
async def test_jwt_token_authenticates_on_preference_route(async_client) -> None:
    """A token from /auth/register is accepted by /users/me/preferences."""
    reg = await async_client.post(
        "/auth/register",
        json={"email": "grace@example.com", "password": "passw0rd!"},
    )
    token = reg.json()["access_token"]
    user_id = reg.json()["user_id"]

    resp = await async_client.get(
        "/users/me/preferences",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["user_id"] == user_id


@pytest.mark.asyncio
async def test_register_and_login_same_user_id(async_client) -> None:
    """The user_id returned by register equals the one returned by login."""
    reg = await async_client.post(
        "/auth/register",
        json={"email": "henry@example.com", "password": "passw0rd!"},
    )
    login = await async_client.post(
        "/auth/login",
        json={"email": "henry@example.com", "password": "passw0rd!"},
    )
    assert reg.json()["user_id"] == login.json()["user_id"]
