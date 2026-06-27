"""Readiness probe — verifies that the DB, Redis, and plugins are healthy.

GET /ready

Returns 200 {"status": "ready", "db": "ok", "redis": "ok", "plugins": "ok"}
when all backing services respond normally and every plugin loaded.

Returns 503 with per-service error detail on any failure.

``plugins`` is included in the degraded status even though it does not block
DB or Redis I/O — a partially-loaded plugin set means some languages will
return 404 on parse/lesson requests, which is observable and worth flagging.

Use this endpoint for:
  - Kubernetes readiness probes (kubelet stops sending traffic on 503)
  - Docker Compose health checks on the app service
  - Manual team checks after deploy  (`make ready`)

Unlike /health (which only confirms the process is alive), /ready performs
live I/O against each dependency on every call — it is never cached.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.api.dependencies import get_plugin_registry
from backend.core.cache import get_redis
from backend.core.database import engine
from backend.parsing.plugin_loader import PluginRegistry

router = APIRouter(tags=["ops"])


@router.get("/ready")
async def ready(
    request: Request,
    registry: PluginRegistry = Depends(get_plugin_registry),
) -> JSONResponse:
    report: dict[str, object] = {
        "db": "unknown",
        "redis": "unknown",
        "plugins": "unknown",
        "startup": "ok",
    }
    failed = False

    # ── Startup errors (migration failures, DB unreachable at boot) ───────────
    startup_errors: list[str] = getattr(request.app.state, "startup_errors", [])
    if startup_errors:
        report["startup"] = startup_errors
        failed = True

    # ── Database ──────────────────────────────────────────────────────────────
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        report["db"] = "ok"
    except Exception as exc:
        report["db"] = f"error ({type(exc).__name__})"
        failed = True

    # ── Redis ─────────────────────────────────────────────────────────────────
    # Redis is used only for caching; the app degrades gracefully without it.
    # A missing Redis is reported in the report body but does not set failed=True
    # so deployments without Redis don't show the degraded banner.
    try:
        redis = await get_redis()
        await redis.ping()
        report["redis"] = "ok"
    except Exception as exc:
        report["redis"] = f"unavailable ({type(exc).__name__})"

    # ── Plugin health ─────────────────────────────────────────────────────────
    failed_plugins = registry.failed_plugins()
    if failed_plugins:
        report["plugins"] = {"degraded": list(failed_plugins.keys())}
        failed = True
    else:
        report["plugins"] = "ok"

    report["status"] = "degraded" if failed else "ready"
    return JSONResponse(content=report, status_code=503 if failed else 200)
