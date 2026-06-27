"""Integration tests for GET /metrics.

Uses the same in-memory SQLite + async_client fixtures as other test modules.
"""
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


# ── Empty state ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metrics_empty_when_no_data(async_client) -> None:
    resp = await async_client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_seen"] == 0
    assert data["total_reviewed"] == 0
    assert data["total_mastered"] == 0
    assert data["overall_retention"] == 0.0
    assert data["success_rate"] == 0.0
    assert data["by_language"] == []
    assert data["by_type"] == []
    assert data["weakest"] == []


# ── After parse ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metrics_seen_increments_after_parse(async_client) -> None:
    await async_client.post(
        "/parse", json={"text": "Hola amigo.", "language": "es"}
    )
    data = (await async_client.get("/metrics")).json()
    assert data["total_seen"] > 0
    assert data["total_reviewed"] == 0   # not reviewed yet


@pytest.mark.asyncio
async def test_metrics_reviewed_increments_after_review(async_client) -> None:
    parse_resp = await async_client.post(
        "/parse", json={"text": "Hola.", "language": "es"}
    )
    obj_id = parse_resp.json()["sentences"][0]["learnable_objects"][0]["id"]
    await async_client.post("/review", json={"object_id": obj_id, "quality": 3})

    data = (await async_client.get("/metrics")).json()
    assert data["total_reviewed"] >= 1
    assert data["overall_retention"] > 0.0
    assert data["success_rate"] > 0.0
    assert data["avg_stability_days"] > 0.0


# ── Required response fields ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metrics_response_fields_present(async_client) -> None:
    resp = await async_client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    for field in (
        "total_seen", "total_reviewed", "total_mastered",
        "overall_retention", "success_rate", "avg_stability_days",
        "overdue_count", "by_language", "by_type", "weakest",
    ):
        assert field in data, f"Missing field: {field}"


# ── By-language breakdown ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metrics_by_language_populated(async_client) -> None:
    await async_client.post("/parse", json={"text": "Hola.", "language": "es"})
    await async_client.post("/parse", json={"text": "Bonjour.", "language": "fr"})

    data = (await async_client.get("/metrics")).json()
    langs = {row["language"] for row in data["by_language"]}
    assert "es" in langs
    assert "fr" in langs


@pytest.mark.asyncio
async def test_metrics_language_filter_isolates_language(async_client) -> None:
    await async_client.post("/parse", json={"text": "El gato.", "language": "es"})
    await async_client.post("/parse", json={"text": "Bonjour monde.", "language": "fr"})

    es_data = (await async_client.get("/metrics?language=es")).json()
    fr_data = (await async_client.get("/metrics?language=fr")).json()

    # Spanish objects must not appear in French metrics and vice versa
    assert all(r["language"] == "es" for r in es_data["by_language"])
    assert all(r["language"] == "fr" for r in fr_data["by_language"])
    assert es_data["total_seen"] > 0
    assert fr_data["total_seen"] > 0
    # Totals should not overlap
    assert es_data["total_seen"] + fr_data["total_seen"] <= (
        (await async_client.get("/metrics")).json()["total_seen"]
    )


@pytest.mark.asyncio
async def test_metrics_unknown_language_returns_zeros(async_client) -> None:
    await async_client.post("/parse", json={"text": "Hola.", "language": "es"})
    data = (await async_client.get("/metrics?language=zh")).json()
    assert data["total_seen"] == 0
    assert data["by_language"] == []


# ── By-type breakdown ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metrics_by_type_contains_vocabulary(async_client) -> None:
    await async_client.post(
        "/parse", json={"text": "El gato duerme.", "language": "es"}
    )
    data = (await async_client.get("/metrics")).json()
    types = {row["type"] for row in data["by_type"]}
    assert "vocabulary" in types or "conjugation" in types, (
        f"Expected at least one known type, got {types}"
    )


# ── Weakest areas ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metrics_weakest_populated_after_review(async_client) -> None:
    parse_resp = await async_client.post(
        "/parse", json={"text": "Hola amigo.", "language": "es"}
    )
    obj_id = parse_resp.json()["sentences"][0]["learnable_objects"][0]["id"]
    await async_client.post("/review", json={"object_id": obj_id, "quality": 1})

    data = (await async_client.get("/metrics")).json()
    assert len(data["weakest"]) >= 1
    for w in data["weakest"]:
        assert "object_id" in w
        assert "mastery_score" in w
        assert "lapse_rate" in w
        assert "total_reviews" in w


@pytest.mark.asyncio
async def test_metrics_weakest_ordered_ascending(async_client) -> None:
    """Weakest list must be sorted by mastery_score ascending."""
    for i in range(3):
        parse_resp = await async_client.post(
            "/parse",
            json={"text": f"Hola palabra{i}.", "language": "es"},
        )
        obj_id = parse_resp.json()["sentences"][0]["learnable_objects"][0]["id"]
        await async_client.post(
            "/review", json={"object_id": obj_id, "quality": (i % 4) + 1}
        )

    data = (await async_client.get("/metrics")).json()
    scores = [w["mastery_score"] for w in data["weakest"]]
    assert scores == sorted(scores), f"Weakest not sorted: {scores}"


@pytest.mark.asyncio
async def test_metrics_weakest_at_most_10(async_client) -> None:
    """Weakest list must be capped at 10 entries."""
    for i in range(15):
        parse_resp = await async_client.post(
            "/parse", json={"text": f"Palabra{i} interesante.", "language": "es"}
        )
        obj_id = parse_resp.json()["sentences"][0]["learnable_objects"][0]["id"]
        await async_client.post("/review", json={"object_id": obj_id, "quality": 2})

    data = (await async_client.get("/metrics")).json()
    assert len(data["weakest"]) <= 10


# ── Retention and success_rate ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metrics_retention_in_unit_interval(async_client) -> None:
    parse_resp = await async_client.post(
        "/parse", json={"text": "El libro rojo.", "language": "es"}
    )
    obj_id = parse_resp.json()["sentences"][0]["learnable_objects"][0]["id"]
    await async_client.post("/review", json={"object_id": obj_id, "quality": 3})

    data = (await async_client.get("/metrics")).json()
    assert 0.0 <= data["overall_retention"] <= 1.0
    assert 0.0 <= data["success_rate"] <= 1.0


@pytest.mark.asyncio
async def test_metrics_success_rate_lower_after_lapse(async_client) -> None:
    """Reviewing with quality=1 (lapse) should yield success_rate < 1.0."""
    parse_resp = await async_client.post(
        "/parse", json={"text": "Hola.", "language": "es"}
    )
    obj_id = parse_resp.json()["sentences"][0]["learnable_objects"][0]["id"]
    await async_client.post("/review", json={"object_id": obj_id, "quality": 1})

    data = (await async_client.get("/metrics")).json()
    assert data["success_rate"] < 1.0, "A lapse should bring success_rate below 1.0"
