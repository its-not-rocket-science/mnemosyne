"""In-process async job store for long-running parse jobs.

Architecture
────────────
Jobs are kept in a module-level dict so all routes in the same process share
state.  This is intentional for the single-worker development setup.

In a multi-worker production deployment (Gunicorn + multiple Uvicorn workers)
each worker has its own in-process store.  Clients should be directed to the
same worker for the lifetime of a job (sticky sessions), or the store should
be replaced with a Redis-backed implementation.  A Redis backend is left as a
future improvement; for now an operator note in the relevant route documents
the limitation.

Job lifecycle
─────────────
  pending → running → done
                    → failed

Cleanup
───────
Completed jobs are retained for ``JOB_TTL_SECONDS`` after completion, then
purged lazily on the next ``create()`` call.  This prevents unbounded memory
growth in long-running processes without requiring a background thread.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

JOB_TTL_SECONDS = 3600  # 1 hour
MAX_JOBS = 500          # hard cap; oldest completed jobs are evicted first


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
    # Private: SSE subscriber queues.  Not serialised.
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


class JobStore:
    """Thread-safe (asyncio-safe) in-process job registry."""

    def __init__(self) -> None:
        self._jobs: dict[str, ParseJob] = {}

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def create(self, job_id: str, user_id: str) -> ParseJob:
        """Register a new job and return it.  Evicts stale completed jobs."""
        self._evict_stale()
        job = ParseJob(id=job_id, user_id=user_id)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> ParseJob | None:
        return self._jobs.get(job_id)

    # ── State transitions ─────────────────────────────────────────────────────

    def update(self, job: ParseJob, **kwargs: Any) -> None:
        """Apply keyword updates to *job* and fan-out a progress event."""
        for key, value in kwargs.items():
            setattr(job, key, value)
        job.updated_at = datetime.now(UTC)
        snapshot = job.public_dict()
        for q in list(job._subscribers):
            q.put_nowait(snapshot)

    def finish(self, job: ParseJob, result: dict[str, Any]) -> None:
        """Mark job as done, attach full result, and notify all subscribers."""
        job.result   = result
        job.status   = "done"
        job.stage    = "done"
        job.progress = 1.0
        job.updated_at = datetime.now(UTC)
        snapshot = {**job.public_dict(), "result": result}
        for q in list(job._subscribers):
            q.put_nowait(snapshot)

    def fail(self, job: ParseJob, error: str) -> None:
        """Mark job as failed and notify all subscribers."""
        job.status   = "failed"
        job.stage    = "failed"
        job.error    = error
        job.updated_at = datetime.now(UTC)
        snapshot = job.public_dict()
        for q in list(job._subscribers):
            q.put_nowait(snapshot)

    # ── SSE subscription ──────────────────────────────────────────────────────

    def subscribe(self, job: ParseJob) -> asyncio.Queue:
        """Return a new asyncio.Queue that receives every update for *job*."""
        q: asyncio.Queue = asyncio.Queue()
        job._subscribers.append(q)
        return q

    def unsubscribe(self, job: ParseJob, q: asyncio.Queue) -> None:
        try:
            job._subscribers.remove(q)
        except ValueError:
            pass

    # ── Housekeeping ──────────────────────────────────────────────────────────

    def _evict_stale(self) -> None:
        """Remove completed/failed jobs older than JOB_TTL_SECONDS."""
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
        # If still too many, evict oldest completed jobs regardless of TTL.
        if len(self._jobs) >= MAX_JOBS:
            completed = sorted(
                [(jid, j) for jid, j in self._jobs.items()
                 if j.status in ("done", "failed")],
                key=lambda pair: pair[1].updated_at,
            )
            for jid, _ in completed[: len(self._jobs) - MAX_JOBS + 1]:
                del self._jobs[jid]


# Module-level singleton — imported by route modules.
job_store = JobStore()
