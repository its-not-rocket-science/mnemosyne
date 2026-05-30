"""Integration tests for GET /metrics/forecast."""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.database import get_db_session, get_session_factory
from backend.main import app
from backend.models import Base


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
    app.dependency_overrides[get_session_factory] = lambda: factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_session_factory, None)


# ── Shape / schema ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_forecast_default_seven_days(async_client) -> None:
    resp = await async_client.get("/metrics/forecast")
    assert resp.status_code == 200
    data = resp.json()
    assert "days" in data
    assert "total_days" in data
    assert len(data["days"]) == 7
    assert data["total_days"] == 7


@pytest.mark.asyncio
async def test_forecast_day_fields(async_client) -> None:
    data = (await async_client.get("/metrics/forecast")).json()
    day = data["days"][0]
    for field in ("date", "day_label", "annotation_count", "sentence_count", "total", "is_today"):
        assert field in day, f"Missing field: {field}"


@pytest.mark.asyncio
async def test_forecast_first_day_is_today(async_client) -> None:
    data = (await async_client.get("/metrics/forecast")).json()
    assert data["days"][0]["is_today"] is True
    assert all(not d["is_today"] for d in data["days"][1:])


@pytest.mark.asyncio
async def test_forecast_totals_are_nonnegative(async_client) -> None:
    data = (await async_client.get("/metrics/forecast")).json()
    for day in data["days"]:
        assert day["annotation_count"] >= 0
        assert day["sentence_count"] >= 0
        assert day["total"] == day["annotation_count"] + day["sentence_count"]


@pytest.mark.asyncio
async def test_forecast_custom_days_param(async_client) -> None:
    data = (await async_client.get("/metrics/forecast?days=3")).json()
    assert len(data["days"]) == 3
    assert data["total_days"] == 3


@pytest.mark.asyncio
async def test_forecast_days_param_max_clamped(async_client) -> None:
    resp = await async_client.get("/metrics/forecast?days=31")
    assert resp.status_code == 422  # exceeds ge=1, le=30


@pytest.mark.asyncio
async def test_forecast_language_filter_accepted(async_client) -> None:
    resp = await async_client.get("/metrics/forecast?language=es")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["days"]) == 7


@pytest.mark.asyncio
async def test_forecast_counts_after_parse(async_client) -> None:
    """After parsing, today's annotation_count should be >= 1."""
    await async_client.post("/parse", json={"text": "Hola mundo.", "language": "es"})
    data = (await async_client.get("/metrics/forecast")).json()
    today = data["days"][0]
    assert today["annotation_count"] >= 1
    assert today["total"] >= 1
