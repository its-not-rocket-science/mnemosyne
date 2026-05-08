"""Tests for backend.core.jobs (InMemoryJobStore, factory) and
backend.core.jobs_redis (RedisJobStore, serialisation, pub/sub).

All Redis tests use AsyncMock — no real Redis connection required.
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import backend.core.jobs as jobs_module
from backend.core.jobs import (
    InMemoryJobStore,
    JOB_TTL_SECONDS,
    MAX_JOBS,
    ParseJob,
    get_job_store,
)
from backend.core.jobs_redis import (
    RedisJobStore,
    _CRASH_TTL,
    _channel,
    _hash_to_job,
    _job_to_hash,
    _key,
)


# ── Shared fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_store_singleton(monkeypatch):
    """Ensure _store and _store_lock are fresh for every test."""
    monkeypatch.setattr(jobs_module, "_store", None)
    monkeypatch.setattr(jobs_module, "_store_lock", asyncio.Lock())
    yield


# ── ParseJob.public_dict ───────────────────────────────────────────────────────

class TestParseJobPublicDict:
    def test_contains_expected_keys(self):
        job = ParseJob(id="j1", user_id="u1")
        d = job.public_dict()
        assert set(d.keys()) == {
            "job_id", "status", "progress", "stage",
            "sentences_done", "sentences_total", "error",
            "created_at", "updated_at",
        }

    def test_progress_rounded_to_3dp(self):
        job = ParseJob(id="j1", user_id="u1", progress=0.12345678)
        assert job.public_dict()["progress"] == 0.123

    def test_private_subscribers_not_included(self):
        job = ParseJob(id="j1", user_id="u1")
        job._subscribers.append(asyncio.Queue())
        assert "_subscribers" not in job.public_dict()


# ── InMemoryJobStore ───────────────────────────────────────────────────────────

class TestInMemoryJobStore:
    @pytest.mark.asyncio
    async def test_create_returns_pending_job(self):
        store = InMemoryJobStore()
        job = await store.create("j1", "u1")
        assert job.id == "j1"
        assert job.user_id == "u1"
        assert job.status == "pending"
        assert job.progress == 0.0

    @pytest.mark.asyncio
    async def test_get_returns_same_object(self):
        store = InMemoryJobStore()
        job = await store.create("j1", "u1")
        assert await store.get("j1") is job

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self):
        store = InMemoryJobStore()
        assert await store.get("nope") is None

    @pytest.mark.asyncio
    async def test_update_mutates_job_and_notifies_subscriber(self):
        store = InMemoryJobStore()
        job = await store.create("j1", "u1")
        q = await store.subscribe(job)
        await store.update(job, status="running", progress=0.2)
        assert job.status == "running"
        assert job.progress == pytest.approx(0.2)
        data = q.get_nowait()
        assert data["status"] == "running"
        assert data["progress"] == pytest.approx(0.2)

    @pytest.mark.asyncio
    async def test_update_stamps_updated_at(self):
        store = InMemoryJobStore()
        job = await store.create("j1", "u1")
        before = job.updated_at
        await asyncio.sleep(0.01)
        await store.update(job, progress=0.5)
        assert job.updated_at > before

    @pytest.mark.asyncio
    async def test_finish_sets_terminal_fields_and_notifies(self):
        store = InMemoryJobStore()
        job = await store.create("j1", "u1")
        q = await store.subscribe(job)
        result = {"sentences": []}
        await store.finish(job, result)
        assert job.status == "done"
        assert job.stage == "done"
        assert job.progress == 1.0
        assert job.result is result
        data = q.get_nowait()
        assert data["status"] == "done"
        assert "result" in data

    @pytest.mark.asyncio
    async def test_fail_sets_terminal_fields_and_notifies(self):
        store = InMemoryJobStore()
        job = await store.create("j1", "u1")
        q = await store.subscribe(job)
        await store.fail(job, "explosion")
        assert job.status == "failed"
        assert job.stage == "failed"
        assert job.error == "explosion"
        data = q.get_nowait()
        assert data["status"] == "failed"

    @pytest.mark.asyncio
    async def test_unsubscribe_stops_further_notifications(self):
        store = InMemoryJobStore()
        job = await store.create("j1", "u1")
        q = await store.subscribe(job)
        await store.unsubscribe(job, q)
        await store.update(job, status="running")
        assert q.empty()

    @pytest.mark.asyncio
    async def test_multiple_subscribers_all_notified(self):
        store = InMemoryJobStore()
        job = await store.create("j1", "u1")
        q1 = await store.subscribe(job)
        q2 = await store.subscribe(job)
        await store.update(job, status="running")
        assert not q1.empty()
        assert not q2.empty()

    @pytest.mark.asyncio
    async def test_eviction_when_at_max_jobs(self):
        store = InMemoryJobStore()
        for i in range(MAX_JOBS):
            job = await store.create(f"j{i}", "u1")
            await store.finish(job, {})
        new_job = await store.create("new", "u1")
        assert new_job is not None
        assert len(store._jobs) <= MAX_JOBS

    @pytest.mark.asyncio
    async def test_no_eviction_below_max(self):
        store = InMemoryJobStore()
        for i in range(10):
            await store.create(f"j{i}", "u1")
        assert len(store._jobs) == 10


# ── Redis serialisation ────────────────────────────────────────────────────────

class TestSerialisation:
    def _make_job(self, **kwargs) -> ParseJob:
        now = datetime.now(UTC)
        defaults = dict(
            id="j1", user_id="u1", status="running", progress=0.5,
            stage="nlp", sentences_done=3, sentences_total=10,
            result=None, error=None, created_at=now, updated_at=now,
        )
        defaults.update(kwargs)
        return ParseJob(**defaults)

    def test_round_trip_no_result(self):
        job = self._make_job()
        restored = _hash_to_job(_job_to_hash(job))
        assert restored.id == job.id
        assert restored.status == job.status
        assert restored.progress == job.progress
        assert restored.result is None
        assert restored.error is None

    def test_round_trip_with_result(self):
        job = self._make_job(status="done", result={"sentences": []}, progress=1.0)
        restored = _hash_to_job(_job_to_hash(job))
        assert restored.result == {"sentences": []}

    def test_round_trip_with_error(self):
        job = self._make_job(status="failed", error="boom")
        restored = _hash_to_job(_job_to_hash(job))
        assert restored.error == "boom"

    def test_timestamps_preserved(self):
        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
        job = self._make_job(created_at=now, updated_at=now)
        restored = _hash_to_job(_job_to_hash(job))
        assert restored.created_at == now
        assert restored.updated_at == now

    def test_key_and_channel_format(self):
        assert _key("abc") == "job:abc"
        assert _channel("abc") == "job:abc:events"


# ── RedisJobStore ──────────────────────────────────────────────────────────────

class TestRedisJobStore:
    @pytest.fixture
    def redis_mock(self):
        m = AsyncMock()
        m.hset = AsyncMock(return_value=1)
        m.hgetall = AsyncMock(return_value={})
        m.expire = AsyncMock(return_value=1)
        m.publish = AsyncMock(return_value=1)
        m.ping = AsyncMock(return_value=True)
        return m

    @pytest.fixture
    def store(self, redis_mock):
        return RedisJobStore(redis_mock)

    @pytest.mark.asyncio
    async def test_create_writes_hash_with_crash_ttl(self, store, redis_mock):
        job = await store.create("j1", "u1")
        assert job.id == "j1"
        redis_mock.hset.assert_called_once()
        redis_mock.expire.assert_called_once_with("job:j1", _CRASH_TTL)

    @pytest.mark.asyncio
    async def test_get_reconstructs_job_from_hash(self, store, redis_mock):
        now = datetime.now(UTC).isoformat()
        redis_mock.hgetall.return_value = {
            "id": "j1", "user_id": "u1", "status": "running",
            "progress": "0.4", "stage": "nlp",
            "sentences_done": "2", "sentences_total": "5",
            "result": "", "error": "",
            "created_at": now, "updated_at": now,
        }
        job = await store.get("j1")
        assert job is not None
        assert job.id == "j1"
        assert job.status == "running"
        assert job.progress == pytest.approx(0.4)

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing_key(self, store, redis_mock):
        redis_mock.hgetall.return_value = {}
        assert await store.get("missing") is None

    @pytest.mark.asyncio
    async def test_update_mutates_job_and_publishes(self, store, redis_mock):
        job = ParseJob(id="j1", user_id="u1")
        await store.update(job, status="running", progress=0.1)
        assert job.status == "running"
        redis_mock.publish.assert_called_once()
        channel, payload = redis_mock.publish.call_args.args
        assert channel == "job:j1:events"
        data = json.loads(payload)
        assert data["status"] == "running"

    @pytest.mark.asyncio
    async def test_update_uses_crash_ttl(self, store, redis_mock):
        job = ParseJob(id="j1", user_id="u1")
        await store.update(job, status="running")
        redis_mock.expire.assert_called_with("job:j1", _CRASH_TTL)

    @pytest.mark.asyncio
    async def test_finish_publishes_result_and_uses_short_ttl(self, store, redis_mock):
        job = ParseJob(id="j1", user_id="u1")
        await store.finish(job, {"sentences": []})
        assert job.status == "done"
        assert job.progress == 1.0
        _, payload = redis_mock.publish.call_args.args
        assert "result" in json.loads(payload)
        redis_mock.expire.assert_called_with("job:j1", JOB_TTL_SECONDS)

    @pytest.mark.asyncio
    async def test_fail_uses_short_ttl(self, store, redis_mock):
        job = ParseJob(id="j1", user_id="u1")
        await store.fail(job, "oops")
        assert job.status == "failed"
        redis_mock.expire.assert_called_with("job:j1", JOB_TTL_SECONDS)

    @pytest.mark.asyncio
    async def test_subscribe_creates_tracked_task(self, store):
        job = ParseJob(id="j1", user_id="u1")

        async def _noop(job_id, q):
            try:
                await asyncio.sleep(9999)
            except asyncio.CancelledError:
                pass

        with patch.object(store, "_listen", _noop):
            q = await store.subscribe(job)

        assert isinstance(q, asyncio.Queue)
        assert id(q) in store._sub_tasks
        # Cleanup to avoid dangling tasks.
        await store.unsubscribe(job, q)

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_and_cancels_task(self, store):
        job = ParseJob(id="j1", user_id="u1")

        async def _noop(job_id, q):
            try:
                await asyncio.sleep(9999)
            except asyncio.CancelledError:
                pass

        with patch.object(store, "_listen", _noop):
            q = await store.subscribe(job)
        await store.unsubscribe(job, q)
        assert id(q) not in store._sub_tasks

    @pytest.mark.asyncio
    async def test_probe_pings_redis(self):
        mock_redis = AsyncMock()
        with patch("backend.core.jobs_redis.Redis") as MockRedis, \
             patch("backend.core.jobs_redis.get_settings") as mock_cfg:
            mock_cfg.return_value.redis_url = "redis://localhost:6379/0"
            MockRedis.from_url.return_value = mock_redis
            store = await RedisJobStore.probe()
        assert isinstance(store, RedisJobStore)
        mock_redis.ping.assert_called_once()

    def _make_listen_mocks(self, fake_gen):
        """Return (mock_redis, mock_pubsub) where pubsub() is synchronous."""
        mock_pubsub = AsyncMock()
        mock_pubsub.listen = fake_gen
        mock_redis = AsyncMock()
        # redis.pubsub() is a sync call in redis-py; use MagicMock so it
        # returns mock_pubsub directly instead of a coroutine.
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        return mock_redis, mock_pubsub

    @pytest.mark.asyncio
    async def test_listen_delivers_messages_stops_on_done(self, store):
        q: asyncio.Queue = asyncio.Queue()

        async def fake_gen():
            yield {"type": "subscribe", "data": 1}
            yield {"type": "message", "data": json.dumps({"status": "running"})}
            yield {"type": "message", "data": json.dumps({"status": "done"})}

        mock_redis, _ = self._make_listen_mocks(fake_gen)
        with patch("backend.core.jobs_redis.Redis") as MockRedis, \
             patch("backend.core.jobs_redis.get_settings") as mock_cfg:
            mock_cfg.return_value.redis_url = "redis://localhost:6379/0"
            MockRedis.from_url.return_value = mock_redis
            await store._listen("j1", q)

        assert q.qsize() == 2
        assert q.get_nowait()["status"] == "running"
        assert q.get_nowait()["status"] == "done"

    @pytest.mark.asyncio
    async def test_listen_cleans_up_on_completion(self, store):
        q: asyncio.Queue = asyncio.Queue()

        async def fake_gen():
            yield {"type": "message", "data": json.dumps({"status": "done"})}

        mock_redis, mock_pubsub = self._make_listen_mocks(fake_gen)
        with patch("backend.core.jobs_redis.Redis") as MockRedis, \
             patch("backend.core.jobs_redis.get_settings") as mock_cfg:
            mock_cfg.return_value.redis_url = "redis://localhost:6379/0"
            MockRedis.from_url.return_value = mock_redis
            await store._listen("j1", q)

        mock_pubsub.aclose.assert_called()
        mock_redis.aclose.assert_called()

    @pytest.mark.asyncio
    async def test_listen_ignores_non_message_types(self, store):
        q: asyncio.Queue = asyncio.Queue()

        async def fake_gen():
            yield {"type": "subscribe", "data": 1}
            yield {"type": "psubscribe", "data": 1}
            yield {"type": "message", "data": json.dumps({"status": "done"})}

        mock_redis, _ = self._make_listen_mocks(fake_gen)
        with patch("backend.core.jobs_redis.Redis") as MockRedis, \
             patch("backend.core.jobs_redis.get_settings") as mock_cfg:
            mock_cfg.return_value.redis_url = "redis://localhost:6379/0"
            MockRedis.from_url.return_value = mock_redis
            await store._listen("j1", q)

        assert q.qsize() == 1  # only the message event
        assert q.get_nowait()["status"] == "done"


# ── get_job_store factory ──────────────────────────────────────────────────────

class TestGetJobStore:
    @pytest.mark.asyncio
    async def test_returns_redis_store_when_reachable(self):
        mock_redis = AsyncMock()
        with patch("backend.core.jobs_redis.Redis") as MockRedis, \
             patch("backend.core.jobs_redis.get_settings") as mock_cfg, \
             patch("backend.core.jobs.get_settings") as mock_cfg2:
            mock_cfg.return_value.redis_url = "redis://localhost:6379/0"
            mock_cfg2.return_value.debug = False
            MockRedis.from_url.return_value = mock_redis
            store = await get_job_store()
        assert isinstance(store, RedisJobStore)

    @pytest.mark.asyncio
    async def test_falls_back_to_in_memory_in_debug_mode(self, monkeypatch):
        mock_settings = MagicMock()
        mock_settings.debug = True
        monkeypatch.setattr(jobs_module, "_store", None)
        with patch("backend.core.jobs.get_settings", return_value=mock_settings), \
             patch("backend.core.jobs_redis.Redis") as MockRedis:
            MockRedis.from_url.side_effect = OSError("connection refused")
            store = await get_job_store()
        assert isinstance(store, InMemoryJobStore)

    @pytest.mark.asyncio
    async def test_raises_runtime_error_in_production_when_redis_fails(self, monkeypatch):
        mock_settings = MagicMock()
        mock_settings.debug = False
        monkeypatch.setattr(jobs_module, "_store", None)
        with patch("backend.core.jobs.get_settings", return_value=mock_settings), \
             patch("backend.core.jobs_redis.Redis") as MockRedis:
            MockRedis.from_url.side_effect = OSError("connection refused")
            with pytest.raises(RuntimeError, match="unavailable"):
                await get_job_store()

    @pytest.mark.asyncio
    async def test_singleton_same_instance_on_repeated_calls(self):
        mock_redis = AsyncMock()
        with patch("backend.core.jobs_redis.Redis") as MockRedis, \
             patch("backend.core.jobs_redis.get_settings") as mock_cfg, \
             patch("backend.core.jobs.get_settings") as mock_cfg2:
            mock_cfg.return_value.redis_url = "redis://localhost:6379/0"
            mock_cfg2.return_value.debug = False
            MockRedis.from_url.return_value = mock_redis
            s1 = await get_job_store()
            s2 = await get_job_store()
        assert s1 is s2
