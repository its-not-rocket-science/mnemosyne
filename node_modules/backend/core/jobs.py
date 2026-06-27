"""Job store interface, in-memory implementation, and factory.

``get_job_store()`` returns ``RedisJobStore`` when Redis is reachable,
``InMemoryJobStore`` when ``DEBUG=true`` and Redis is unavailable.
Raises ``RuntimeError`` in production when Redis is unreachable.

Job lifecycle
─────────────
  pending → running → done
                    → failed

TTL / eviction
──────────────
InMemoryJobStore evicts completed jobs lazily on ``create()``.
RedisJobStore sets Redis key TTLs automatically.
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

JOB_TTL_SECONDS = 3600  # 1 hour — used by both backends
MAX_JOBS = 500           # hard cap for InMemoryJobStore only


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class ParseJob:
    id: str
    user_id: str
    status: str = "pending"   # pending | running | done | failed
    progress: float = 0.0     # 0.0–1.0
    stage: str = "pending"    # pending | nlp | persist | done | failed
    sentences_done: int = 0
    sentences_total: int = 0
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # In-memory SSE fan-out only.  Not persisted.
    _subscribers: list[asyncio.Queue] = field(default_factory=list, repr=False)

    def public_dict(self) -> dict[str, Any]:
        """Serialisable snapshot (no private fields, no full result body)."""
        return {
            "job_id": self.id,
            "status": self.status,
            "progress": round(self.progress, 3),
            "stage": self.stage,
            "sentences_done": self.sentences_done,
            "sentences_total": self.sentences_total,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ── Interface ──────────────────────────────────────────────────────────────────

class AbstractJobStore(ABC):
    """Async interface shared by InMemoryJobStore and RedisJobStore."""

    @abstractmethod
    async def create(self, job_id: str, user_id: str) -> ParseJob: ...

    @abstractmethod
    async def get(self, job_id: str) -> ParseJob | None: ...

    @abstractmethod
    async def update(self, job: ParseJob, **kwargs: Any) -> None: ...

    @abstractmethod
    async def finish(self, job: ParseJob, result: dict[str, Any]) -> None: ...

    @abstractmethod
    async def fail(self, job: ParseJob, error: str) -> None: ...

    @abstractmethod
    async def subscribe(self, job: ParseJob) -> asyncio.Queue: ...

    @abstractmethod
    async def unsubscribe(self, job: ParseJob, q: asyncio.Queue) -> None: ...


# ── In-memory backend ──────────────────────────────────────────────────────────

class InMemoryJobStore(AbstractJobStore):
    """Single-process in-process job registry (dev / fallback)."""

    def __init__(self) -> None:
        self._jobs: dict[str, ParseJob] = {}

    async def create(self, job_id: str, user_id: str) -> ParseJob:
        self._evict_stale()
        job = ParseJob(id=job_id, user_id=user_id)
        self._jobs[job_id] = job
        return job

    async def get(self, job_id: str) -> ParseJob | None:
        return self._jobs.get(job_id)

    async def update(self, job: ParseJob, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(job, key, value)
        job.updated_at = datetime.now(UTC)
        snapshot = job.public_dict()
        for q in list(job._subscribers):
            q.put_nowait(snapshot)

    async def finish(self, job: ParseJob, result: dict[str, Any]) -> None:
        job.result = result
        job.status = "done"
        job.stage = "done"
        job.progress = 1.0
        job.updated_at = datetime.now(UTC)
        snapshot = {**job.public_dict(), "result": result}
        for q in list(job._subscribers):
            q.put_nowait(snapshot)

    async def fail(self, job: ParseJob, error: str) -> None:
        job.status = "failed"
        job.stage = "failed"
        job.error = error
        job.updated_at = datetime.now(UTC)
        snapshot = job.public_dict()
        for q in list(job._subscribers):
            q.put_nowait(snapshot)

    async def subscribe(self, job: ParseJob) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        job._subscribers.append(q)
        return q

    async def unsubscribe(self, job: ParseJob, q: asyncio.Queue) -> None:
        try:
            job._subscribers.remove(q)
        except ValueError:
            pass

    def _evict_stale(self) -> None:
        if len(self._jobs) < MAX_JOBS:
            return
        now = datetime.now(UTC)
        to_delete = [
            jid for jid, j in self._jobs.items()
            if j.status in ("done", "failed")
            and (now - j.updated_at).total_seconds() > JOB_TTL_SECONDS
        ]
        for jid in to_delete:
            del self._jobs[jid]
        if len(self._jobs) >= MAX_JOBS:
            completed = sorted(
                [(jid, j) for jid, j in self._jobs.items()
                 if j.status in ("done", "failed")],
                key=lambda pair: pair[1].updated_at,
            )
            for jid, _ in completed[: len(self._jobs) - MAX_JOBS + 1]:
                del self._jobs[jid]


# ── Factory ────────────────────────────────────────────────────────────────────

_store: AbstractJobStore | None = None
_store_lock = asyncio.Lock()


async def get_job_store() -> AbstractJobStore:
    """Return the singleton job store, initialising on first call.

    Selection order:
    1. Redis (``RedisJobStore``) — preferred in all environments.
    2. InMemoryJobStore — only when ``DEBUG=true`` and Redis is unreachable.
    3. RuntimeError — when ``DEBUG=false`` and Redis is unreachable.
    """
    global _store
    if _store is not None:
        return _store
    async with _store_lock:
        if _store is not None:
            return _store
        settings = get_settings()
        try:
            from backend.core.jobs_redis import RedisJobStore
            _store = await RedisJobStore.probe()
            logger.info("job store: Redis (%s)", settings.redis_url)
        except Exception as exc:
            if settings.debug:
                logger.warning(
                    "Redis unavailable; falling back to in-memory job store "
                    "(debug mode — not suitable for multi-worker): %s", exc
                )
                _store = InMemoryJobStore()
            else:
                raise RuntimeError(
                    f"Redis job store is unavailable in production mode: {exc}"
                ) from exc
        return _store  # type: ignore[return-value]
