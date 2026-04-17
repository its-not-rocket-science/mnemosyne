"""Tests for POST /parse/jobs and GET /parse/jobs/{id} endpoints.

Tests cover:
  - JobStore unit tests (create, update, finish, fail, subscribe/drain)
  - POST /parse/jobs happy path (202 + job_id)
  - POST /parse/jobs 413 when text > max_job_chars
  - POST /parse/jobs 404 for unsupported language
  - GET /parse/jobs/{id} pending / done / failed states
  - GET /parse/jobs/{id} 404 for unknown / other-user job
  - SSE event stream receives progress and final done event
"""
from __future__ import annotations

import asyncio
import json

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.dependencies import get_current_user, get_db_session
from backend.core.database import get_session_factory
from backend.core.jobs import JobStore, ParseJob, job_store
from backend.main import app
from backend.models import Base


# ── JobStore unit tests ───────────────────────────────────────────────────────

class TestJobStore:
    def setup_method(self):
        self.store = JobStore()

    def test_create_returns_job(self):
        job = self.store.create("job1", "alice")
        assert job.id == "job1"
        assert job.user_id == "alice"
        assert job.status == "pending"

    def test_get_existing(self):
        self.store.create("j1", "u1")
        assert self.store.get("j1") is not None

    def test_get_missing_returns_none(self):
        assert self.store.get("missing") is None

    def test_update_changes_fields(self):
        job = self.store.create("j2", "u2")
        self.store.update(job, status="running", progress=0.5, stage="nlp")
        assert job.status == "running"
        assert job.progress == 0.5
        assert job.stage == "nlp"

    def test_finish_marks_done(self):
        job = self.store.create("j3", "u3")
        self.store.finish(job, {"sentences": []})
        assert job.status == "done"
        assert job.progress == 1.0
        assert job.result == {"sentences": []}

    def test_fail_marks_failed(self):
        job = self.store.create("j4", "u4")
        self.store.fail(job, "NLP crashed")
        assert job.status == "failed"
        assert job.error == "NLP crashed"

    def test_update_broadcasts_to_subscriber(self):
        job = self.store.create("j5", "u5")
        q = self.store.subscribe(job)
        self.store.update(job, status="running", progress=0.2, stage="nlp")
        assert not q.empty()
        event = q.get_nowait()
        assert event["status"] == "running"
        assert event["progress"] == pytest.approx(0.2, abs=1e-3)

    def test_finish_broadcasts_result_to_subscriber(self):
        job = self.store.create("j6", "u6")
        q = self.store.subscribe(job)
        self.store.finish(job, {"sentences": [{"text": "hi", "learnable_objects": []}]})
        event = q.get_nowait()
        assert event["status"] == "done"
        assert "result" in event

    def test_unsubscribe_stops_delivery(self):
        job = self.store.create("j7", "u7")
        q = self.store.subscribe(job)
        self.store.unsubscribe(job, q)
        self.store.update(job, status="running")
        assert q.empty()

    def test_public_dict_has_no_private_fields(self):
        job = self.store.create("j8", "u8")
        d = job.public_dict()
        assert "_subscribers" not in d
        assert "user_id" not in d
        assert "job_id" in d


# ── DB + app fixtures ─────────────────────────────────────────────────────────

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

    app.dependency_overrides[get_db_session]       = _override_db
    app.dependency_overrides[get_session_factory]  = lambda: factory
    app.dependency_overrides[get_current_user]     = lambda: "test-user"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    # Clean up any jobs created during the test.
    job_store._jobs.clear()


# ── POST /parse/jobs ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_job_returns_202(client):
    resp = await client.post(
        "/parse/jobs",
        json={"language": "es", "text": "El gato come pescado."},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_create_job_413_when_too_long(client):
    from backend.core.config import get_settings
    app.dependency_overrides[get_settings] = lambda: _tiny_settings(max_job_chars=10)
    try:
        resp = await client.post(
            "/parse/jobs",
            json={"language": "es", "text": "x" * 11},
        )
    finally:
        del app.dependency_overrides[get_settings]
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_create_job_404_unknown_language(client):
    resp = await client.post(
        "/parse/jobs",
        json={"language": "xx", "text": "some text here"},
    )
    assert resp.status_code == 404


# ── GET /parse/jobs/{id} ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_job_pending(client):
    resp = await client.post(
        "/parse/jobs",
        json={"language": "es", "text": "El perro."},
    )
    job_id = resp.json()["job_id"]

    # Poll before the background task has a chance to run.
    status_resp = await client.get(f"/parse/jobs/{job_id}")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["job_id"] == job_id
    assert data["status"] in ("pending", "running", "done")


@pytest.mark.asyncio
async def test_get_job_404_unknown(client):
    resp = await client.get("/parse/jobs/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_job_404_wrong_user(client, db_engine):
    """A job owned by another user must return 404 to the requesting user."""
    # Create a job owned by "other-user" directly in the store.
    job = job_store.create("owned-by-other", "other-user")
    job_store.finish(job, {"sentences": []})

    resp = await client.get("/parse/jobs/owned-by-other")
    # The fixture user is "test-user", so this should 404.
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_job_done_has_result(client):
    """Inject a completed job and confirm GET returns its result."""
    job = job_store.create("done-job", "test-user")
    job_store.finish(job, {"sentences": [{"text": "Hola.", "learnable_objects": []}]})

    resp = await client.get("/parse/jobs/done-job")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "done"
    assert data["result"] is not None
    assert data["result"]["sentences"][0]["text"] == "Hola."


# ── SSE event stream ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sse_stream_already_done(client):
    """SSE for an already-finished job should emit the done event immediately."""
    job = job_store.create("sse-done", "test-user")
    job_store.finish(job, {"sentences": []})

    resp = await client.get("/parse/jobs/sse-done/events")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = _parse_sse_body(resp.text)
    assert any(e.get("status") == "done" for e in events)


@pytest.mark.asyncio
async def test_sse_stream_already_failed(client):
    """SSE for a failed job should emit a failed event immediately."""
    job = job_store.create("sse-fail", "test-user")
    job_store.fail(job, "explosion")

    resp = await client.get("/parse/jobs/sse-fail/events")
    events = _parse_sse_body(resp.text)
    assert any(e.get("status") == "failed" for e in events)


@pytest.mark.asyncio
async def test_sse_receives_progress_then_done(client):
    """Inject a job that transitions running → done while the SSE stream is open."""
    job = job_store.create("sse-live", "test-user")
    job_store.update(job, status="running", stage="nlp", progress=0.2)

    async def _complete_job_soon():
        await asyncio.sleep(0.05)
        job_store.finish(job, {"sentences": []})

    task = asyncio.create_task(_complete_job_soon())
    resp = await client.get("/parse/jobs/sse-live/events")
    await task

    events = _parse_sse_body(resp.text)
    assert any(e.get("status") == "done" for e in events)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_sse_body(body: str) -> list[dict]:
    events = []
    for line in body.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


class _tiny_settings:
    def __init__(self, **kw):
        from backend.core.config import get_settings
        base = get_settings()
        self.rate_limit_parse         = base.rate_limit_parse
        self.max_parse_chars          = base.max_parse_chars
        self.max_job_chars            = kw.get("max_job_chars", base.max_job_chars)
        self.enable_dictionary_lookup = False
        self.enable_translation_enrichment = False
        self.translation_provider     = "none"
        self.translation_api_url      = None
        self.translation_api_key      = None
