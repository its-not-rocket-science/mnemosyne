"""Tests for backend/srs/calibrate.py and the /users/me/calibrate endpoint.

Calibration logic tests are pure unit tests — no DB required.
API tests use the standard tmp_path SQLite fixture.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.dependencies import get_current_user, get_db_session
from backend.core.database import get_session_factory
from backend.main import app
from backend.models import Base, ReviewEventRow, UserFsrsParamsRow
from backend.srs.calibrate import (
    DR_MAX,
    DR_MIN,
    MIN_REVIEWS_FOR_CALIBRATION,
    CalibrationResult,
    calibrate,
)
from backend.srs.fsrs import DESIRED_RETENTION


# ── Pure calibration unit tests ───────────────────────────────────────────────

class TestCalibrateInsufficient:
    def test_returns_none_below_minimum(self):
        events = [(0.9, 3)] * (MIN_REVIEWS_FOR_CALIBRATION - 1)
        assert calibrate(events) is None

    def test_returns_none_for_empty(self):
        assert calibrate([]) is None

    def test_returns_result_at_minimum(self):
        events = [(0.9, 3)] * MIN_REVIEWS_FOR_CALIBRATION
        result = calibrate(events)
        assert result is not None
        assert isinstance(result, CalibrationResult)


class TestCalibrateNoBias:
    """When predicted R matches actual recall, desired_retention should stay
    close to the global default."""

    def test_perfect_recall_at_high_r(self):
        # All reviews at R≈0.95 (bin 9, midpoint 0.95), all successful.
        # Actual 1.0 vs predicted 0.95 → small positive bias → small DR decrease.
        events = [(0.95, 3)] * 100
        result = calibrate(events)
        assert result is not None
        # Small bias (~0.05 shift) so DR stays near default
        assert abs(result.desired_retention - DESIRED_RETENTION) < 0.10

    def test_uniform_50pct_recall(self):
        # Predicted R ≈ 0.5, actual recall 50 %
        events = [(0.45, 3)] * 50 + [(0.45, 1)] * 50
        result = calibrate(events)
        assert result is not None
        # No systematic bias — DR stays near default
        assert DR_MIN <= result.desired_retention <= DR_MAX


class TestCalibrateBiasDirection:
    """Verify the direction of correction is correct."""

    def test_overperforming_lowers_dr(self):
        # User recalls everything effortlessly — model under-estimates memory
        events = [(0.5, 4)] * 100  # predicted 0.5, actual 100 %
        result = calibrate(events)
        assert result is not None
        # Positive bias → DR should be LOWER than default
        assert result.desired_retention < DESIRED_RETENTION

    def test_underperforming_raises_dr(self):
        # User forgets everything — model over-estimates memory
        events = [(0.95, 1)] * 100  # predicted 0.95, actual 0 %
        result = calibrate(events)
        assert result is not None
        # Negative bias → DR should be HIGHER than default
        assert result.desired_retention > DESIRED_RETENTION

    def test_clamped_to_dr_min(self):
        # Extreme overperformance should not push DR below floor
        events = [(0.1, 4)] * 200  # always recalled at very low predicted R
        result = calibrate(events)
        assert result is not None
        assert result.desired_retention >= DR_MIN

    def test_clamped_to_dr_max(self):
        # Extreme underperformance should not push DR above ceiling
        events = [(0.99, 1)] * 200  # never recalled even at near-certain predicted R
        result = calibrate(events)
        assert result is not None
        assert result.desired_retention <= DR_MAX


class TestCalibrateOutput:
    def test_reviews_used_matches_input(self):
        events = [(0.9, 3)] * MIN_REVIEWS_FOR_CALIBRATION
        result = calibrate(events)
        assert result is not None
        assert result.reviews_used == MIN_REVIEWS_FOR_CALIBRATION

    def test_rmse_is_none_with_single_bin(self):
        # All events in one bin → rmse needs ≥ 2 bins
        events = [(0.85, 3)] * MIN_REVIEWS_FOR_CALIBRATION
        result = calibrate(events)
        assert result is not None
        assert result.calibration_rmse is None

    def test_rmse_present_with_spread(self):
        events = [(0.25, 1)] * 20 + [(0.55, 3)] * 20 + [(0.85, 4)] * 20
        result = calibrate(events)
        assert result is not None
        assert result.calibration_rmse is not None
        assert result.calibration_rmse >= 0.0

    def test_desired_retention_rounded(self):
        events = [(0.9, 3)] * MIN_REVIEWS_FOR_CALIBRATION
        result = calibrate(events)
        assert result is not None
        # Should be rounded to 4 decimal places
        assert result.desired_retention == round(result.desired_retention, 4)


# ── DB + API fixtures ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


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


@pytest_asyncio.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


# ── GET /users/me/fsrs-params ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_fsrs_params_defaults(client):
    resp = await client.get("/users/me/fsrs-params")
    assert resp.status_code == 200
    data = resp.json()
    assert data["desired_retention"] == DESIRED_RETENTION
    assert data["last_calibrated_at"] is None
    assert data["reviews_used"] is None


# ── PATCH /users/me/fsrs-params ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_fsrs_params_sets_value(client):
    resp = await client.patch(
        "/users/me/fsrs-params",
        json={"desired_retention": 0.80},
    )
    assert resp.status_code == 200
    assert resp.json()["desired_retention"] == 0.80
    assert resp.json()["last_calibrated_at"] is None


@pytest.mark.asyncio
async def test_patch_fsrs_params_persists(client):
    await client.patch("/users/me/fsrs-params", json={"desired_retention": 0.75})
    resp = await client.get("/users/me/fsrs-params")
    assert resp.json()["desired_retention"] == 0.75


@pytest.mark.asyncio
async def test_patch_fsrs_params_validation_too_low(client):
    resp = await client.patch(
        "/users/me/fsrs-params",
        json={"desired_retention": 0.50},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_fsrs_params_validation_too_high(client):
    resp = await client.patch(
        "/users/me/fsrs-params",
        json={"desired_retention": 0.99},
    )
    assert resp.status_code == 422


# ── POST /users/me/calibrate ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_calibrate_insufficient_reviews(client):
    resp = await client.post("/users/me/calibrate")
    assert resp.status_code == 422
    assert "Not enough" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_calibrate_with_enough_reviews(client, db_session):
    # Insert MIN_REVIEWS_FOR_CALIBRATION review events for the test user
    for i in range(MIN_REVIEWS_FOR_CALIBRATION):
        db_session.add(ReviewEventRow(
            user_id="test-user",
            object_id=f"obj-{i}",
            quality=3,
            mastery_score_before=0.88,
            mastery_score_after=0.92,
        ))
    await db_session.commit()

    resp = await client.post("/users/me/calibrate")
    assert resp.status_code == 200
    data = resp.json()
    assert DR_MIN <= data["desired_retention"] <= DR_MAX
    assert data["last_calibrated_at"] is not None
    assert data["reviews_used"] == MIN_REVIEWS_FOR_CALIBRATION


@pytest.mark.asyncio
async def test_calibrate_persists_and_visible_in_get(client, db_session):
    for i in range(MIN_REVIEWS_FOR_CALIBRATION):
        db_session.add(ReviewEventRow(
            user_id="test-user",
            object_id=f"obj-{i}",
            quality=3,
            mastery_score_before=0.9,
            mastery_score_after=0.92,
        ))
    await db_session.commit()

    cal_resp = await client.post("/users/me/calibrate")
    get_resp = await client.get("/users/me/fsrs-params")

    assert cal_resp.json()["desired_retention"] == get_resp.json()["desired_retention"]
    assert get_resp.json()["last_calibrated_at"] is not None


@pytest.mark.asyncio
async def test_patch_clears_calibration_metadata(client, db_session):
    for i in range(MIN_REVIEWS_FOR_CALIBRATION):
        db_session.add(ReviewEventRow(
            user_id="test-user",
            object_id=f"obj-{i}",
            quality=3,
            mastery_score_before=0.9,
            mastery_score_after=0.92,
        ))
    await db_session.commit()

    await client.post("/users/me/calibrate")
    resp = await client.patch("/users/me/fsrs-params", json={"desired_retention": 0.85})
    assert resp.json()["last_calibrated_at"] is None
    assert resp.json()["reviews_used"] is None


# ── DELETE /users/me cascades fsrs-params ────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_account_removes_fsrs_params(client, db_session):
    db_session.add(UserFsrsParamsRow(
        user_id="test-user",
        desired_retention=0.80,
    ))
    await db_session.commit()

    resp = await client.delete("/users/me")
    assert resp.status_code == 204

    # Row should be gone
    from sqlalchemy import select
    row = await db_session.get(UserFsrsParamsRow, "test-user")
    assert row is None
