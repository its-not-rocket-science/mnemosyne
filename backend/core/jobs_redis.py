"""Redis-backed job store.

State model
───────────
Each job is stored as a Redis hash at ``job:{job_id}`` with a TTL:
  • Pending/running jobs: ``JOB_TTL_SECONDS * 2`` (crash recovery).
  • Completed/failed jobs: ``JOB_TTL_SECONDS`` (same as InMemoryJobStore).

SSE fan-out
───────────
Progress events are published to ``job:{job_id}:events`` as JSON strings.
``subscribe()`` starts a background asyncio task that listens on a dedicated
pub/sub connection and forwards messages into an ``asyncio.Queue``.  This
design works across multiple Uvicorn workers: any worker can publish; any
worker's subscriber will receive the event.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis

from backend.core.config import get_settings
from backend.core.jobs import JOB_TTL_SECONDS, AbstractJobStore, ParseJob

logger = logging.getLogger(__name__)

_CRASH_TTL = JOB_TTL_SECONDS * 2  # TTL while job is pending/running


# ── Key helpers ────────────────────────────────────────────────────────────────

def _key(job_id: str) -> str:
    return f"job:{job_id}"


def _channel(job_id: str) -> str:
    return f"job:{job_id}:events"


# ── Serialisation ──────────────────────────────────────────────────────────────

def _job_to_hash(job: ParseJob) -> dict[str, str]:
    return {
        "id": job.id,
        "user_id": job.user_id,
        "status": job.status,
        "progress": str(job.progress),
        "stage": job.stage,
        "sentences_done": str(job.sentences_done),
        "sentences_total": str(job.sentences_total),
        "result": json.dumps(job.result) if job.result is not None else "",
        "error": job.error or "",
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


def _hash_to_job(data: dict[str, str]) -> ParseJob:
    return ParseJob(
        id=data["id"],
        user_id=data["user_id"],
        status=data["status"],
        progress=float(data["progress"]),
        stage=data["stage"],
        sentences_done=int(data["sentences_done"]),
        sentences_total=int(data["sentences_total"]),
        result=json.loads(data["result"]) if data.get("result") else None,
        error=data.get("error") or None,
        created_at=datetime.fromisoformat(data["created_at"]),
        updated_at=datetime.fromisoformat(data["updated_at"]),
    )


# ── RedisJobStore ──────────────────────────────────────────────────────────────

class RedisJobStore(AbstractJobStore):
    """Job store backed by Redis hashes and pub/sub."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        # Maps id(queue) → background listener task.
        self._sub_tasks: dict[int, asyncio.Task] = {}

    @classmethod
    async def probe(cls) -> "RedisJobStore":
        """Create a RedisJobStore, verifying connectivity with PING."""
        settings = get_settings()
        redis: Redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=1.0,
            socket_connect_timeout=1.0,
        )
        await redis.ping()
        return cls(redis)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def create(self, job_id: str, user_id: str) -> ParseJob:
        job = ParseJob(id=job_id, user_id=user_id)
        await self._redis.hset(_key(job_id), mapping=_job_to_hash(job))
        await self._redis.expire(_key(job_id), _CRASH_TTL)
        return job

    async def get(self, job_id: str) -> ParseJob | None:
        data = await self._redis.hgetall(_key(job_id))
        if not data:
            return None
        return _hash_to_job(data)

    # ── State transitions ─────────────────────────────────────────────────────

    async def update(self, job: ParseJob, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(job, key, value)
        job.updated_at = datetime.now(UTC)
        await self._redis.hset(_key(job.id), mapping=_job_to_hash(job))
        await self._redis.expire(_key(job.id), _CRASH_TTL)
        await self._redis.publish(_channel(job.id), json.dumps(job.public_dict()))

    async def finish(self, job: ParseJob, result: dict[str, Any]) -> None:
        job.result = result
        job.status = "done"
        job.stage = "done"
        job.progress = 1.0
        job.updated_at = datetime.now(UTC)
        await self._redis.hset(_key(job.id), mapping=_job_to_hash(job))
        await self._redis.expire(_key(job.id), JOB_TTL_SECONDS)
        snapshot = {**job.public_dict(), "result": result}
        await self._redis.publish(_channel(job.id), json.dumps(snapshot))

    async def fail(self, job: ParseJob, error: str) -> None:
        job.status = "failed"
        job.stage = "failed"
        job.error = error
        job.updated_at = datetime.now(UTC)
        await self._redis.hset(_key(job.id), mapping=_job_to_hash(job))
        await self._redis.expire(_key(job.id), JOB_TTL_SECONDS)
        await self._redis.publish(_channel(job.id), json.dumps(job.public_dict()))

    # ── SSE subscription ──────────────────────────────────────────────────────

    async def subscribe(self, job: ParseJob) -> asyncio.Queue:
        """Return a queue fed by a background pub/sub listener for *job*."""
        q: asyncio.Queue = asyncio.Queue()
        task = asyncio.create_task(
            self._listen(job.id, q),
            name=f"job-pubsub-{job.id}",
        )
        self._sub_tasks[id(q)] = task
        return q

    async def unsubscribe(self, job: ParseJob, q: asyncio.Queue) -> None:
        task = self._sub_tasks.pop(id(q), None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    async def _listen(self, job_id: str, q: asyncio.Queue) -> None:
        """Background task: subscribe to Redis pub/sub and feed *q*."""
        settings = get_settings()
        redis: Redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1.0,
        )
        pubsub = redis.pubsub()
        await pubsub.subscribe(_channel(job_id))
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                data = json.loads(message["data"])
                await q.put(data)
                if data.get("status") in ("done", "failed"):
                    break
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("pub/sub listener for job %s failed: %s", job_id, exc)
        finally:
            try:
                await pubsub.unsubscribe(_channel(job_id))
                await pubsub.aclose()
                await redis.aclose()
            except Exception:
                pass
