"""Readiness probe — verifies that the DB and Redis are reachable.

GET /ready

Returns 200 {"status": "ready", "db": "ok", "redis": "ok"} when all
backing services respond normally.

Returns 503 with per-service error detail on any failure.

Use this endpoint for:
  - Kubernetes readiness probes (kubelet stops sending traffic on 503)
  - Docker Compose health checks on the app service
  - Manual team checks after deploy  (`make ready`)

Unlike /health (which only confirms the process is alive), /ready performs
live I/O against each dependency on every call — it is never cached.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.core.cache import get_redis
from backend.core.database import engine

router = APIRouter(tags=["ops"])


@router.get("/ready")
async def ready() -> JSONResponse:
    report: dict[str, str] = {"db": "unknown", "redis": "unknown"}
    failed = False

    # ── Database ──────────────────────────────────────────────────────────────
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        report["db"] = "ok"
    except Exception as exc:
        report["db"] = f"error ({type(exc).__name__})"
        failed = True

    # ── Redis ─────────────────────────────────────────────────────────────────
    try:
        redis = await get_redis()
        await redis.ping()
        report["redis"] = "ok"
    except Exception as exc:
        report["redis"] = f"error ({type(exc).__name__})"
        failed = True

    report["status"] = "degraded" if failed else "ready"
    return JSONResponse(content=report, status_code=503 if failed else 200)
