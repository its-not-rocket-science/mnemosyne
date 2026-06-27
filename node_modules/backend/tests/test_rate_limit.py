"""Rate-limit tests for /parse and /ingest.

Strategy
────────
Override ``rate_limit_parse`` to a very tight window ("2/minute") so tests
don't have to hammer the endpoint 20 times.  The limiter uses in-memory
storage, so each test gets a fresh state via a fresh TestClient.

We test:
  - The 3rd request within a minute returns 429.
  - The 429 body matches FastAPI's JSON error format {"detail": "..."}.
  - Different user keys get independent counters.
  - The key function resolves: JWT > X-User-Id > IP.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from unittest.mock import MagicMock, patch

from backend.api.dependencies import get_db_session
from backend.auth.tokens import create_access_token
from backend.core.config import Settings
from backend.core.limiter import _user_or_ip_key
from backend.main import app
from backend.models import Base


def _tight_settings() -> Settings:
    """Return a Settings instance with a very tight parse rate limit for tests."""
    s = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        rate_limit_parse="2/minute",
    )
    return s

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


# ── Key-function unit tests ───────────────────────────────────────────────────

class _FakeRequest:
    """Minimal Request stand-in for unit-testing the key function."""
    def __init__(self, auth=None, x_user_id=None, client_host="1.2.3.4"):
        self.headers = {}
        if auth:
            self.headers["Authorization"] = auth
        if x_user_id:
            self.headers["X-User-Id"] = x_user_id
        self.client = type("C", (), {"host": client_host})()


def test_key_uses_jwt_user_id():
    user_id = "jwt-user-001"
    token = create_access_token(user_id)
    req = _FakeRequest(auth=f"Bearer {token}")
    assert _user_or_ip_key(req) == f"user:{user_id}"


def test_key_falls_back_to_x_user_id():
    req = _FakeRequest(x_user_id="dev-user")
    assert _user_or_ip_key(req) == "user:dev-user"


def test_key_jwt_takes_priority_over_x_user_id():
    user_id = "jwt-wins"
    token = create_access_token(user_id)
    req = _FakeRequest(auth=f"Bearer {token}", x_user_id="header-user")
    assert _user_or_ip_key(req) == f"user:{user_id}"


def test_key_falls_back_to_ip():
    req = _FakeRequest(client_host="10.0.0.1")
    assert _user_or_ip_key(req) == "10.0.0.1"


def test_key_invalid_jwt_falls_back_to_ip():
    req = _FakeRequest(auth="Bearer not.a.real.token", client_host="5.6.7.8")
    assert _user_or_ip_key(req) == "5.6.7.8"


# ── 429 integration tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_parse_rate_limited_returns_429(async_client) -> None:
    """After exceeding the limit, /parse returns 429 with a JSON detail."""
    headers = {"X-User-Id": "rl-test-user"}
    tight = _tight_settings()

    with patch("backend.api.routes.parse.get_settings", return_value=tight):
        # Two requests should succeed (or 404 if es plugin absent).
        for _ in range(2):
            resp = await async_client.post(
                "/parse",
                json={"text": "Hola.", "language": "es"},
                headers=headers,
            )
            assert resp.status_code in (200, 404, 413)

        # Third request should be rate-limited.
        resp = await async_client.post(
            "/parse",
            json={"text": "Hola.", "language": "es"},
            headers=headers,
        )
        assert resp.status_code == 429
        body = resp.json()
        assert "detail" in body
        assert "Rate limit exceeded" in body["detail"]


@pytest.mark.asyncio
async def test_ingest_rate_limited_returns_429(async_client) -> None:
    """After exceeding the limit, /ingest returns 429 with a JSON detail."""
    headers = {"X-User-Id": "rl-ingest-user"}
    tight = _tight_settings()

    with patch("backend.api.routes.ingest.get_settings", return_value=tight):
        for _ in range(2):
            await async_client.post(
                "/ingest",
                json={"text": "Hola.", "language": "es", "content_type": "pasted_text"},
                headers=headers,
            )
        resp = await async_client.post(
            "/ingest",
            json={"text": "Hola.", "language": "es", "content_type": "pasted_text"},
            headers=headers,
        )
        assert resp.status_code == 429


@pytest.mark.asyncio
async def test_different_users_have_independent_counters(async_client) -> None:
    """alice's limit does not affect bob's."""
    tight = _tight_settings()

    with patch("backend.api.routes.parse.get_settings", return_value=tight):
        # Exhaust alice's limit.
        for _ in range(2):
            await async_client.post(
                "/parse",
                json={"text": "Hola.", "language": "es"},
                headers={"X-User-Id": "rl-alice2"},
            )

        # alice is now limited.
        alice_resp = await async_client.post(
            "/parse",
            json={"text": "Hola.", "language": "es"},
            headers={"X-User-Id": "rl-alice2"},
        )
        assert alice_resp.status_code == 429

        # bob's first request should not be rate-limited.
        bob_resp = await async_client.post(
            "/parse",
            json={"text": "Hola.", "language": "es"},
            headers={"X-User-Id": "rl-bob2"},
        )
        assert bob_resp.status_code != 429


@pytest.mark.asyncio
async def test_429_has_retry_after_header(async_client) -> None:
    """The 429 response includes a Retry-After header."""
    headers = {"X-User-Id": "rl-retry-user"}
    tight = _tight_settings()

    with patch("backend.api.routes.parse.get_settings", return_value=tight):
        for _ in range(2):
            await async_client.post(
                "/parse",
                json={"text": "Hola.", "language": "es"},
                headers=headers,
            )
        resp = await async_client.post(
            "/parse",
            json={"text": "Hola.", "language": "es"},
            headers=headers,
        )
        assert resp.status_code == 429
        assert "retry-after" in resp.headers
