import asyncio
import logging
import os
import re
import shutil
import subprocess
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from slowapi.errors import RateLimitExceeded

from backend.api.dependencies import get_plugin_registry
from backend.api.routes.auth import router as auth_router
from backend.core.limiter import limiter, rate_limit_exceeded_handler
from backend.api.routes.dashboard import router as dashboard_router
from backend.api.routes.fetch_url import router as fetch_url_router
from backend.api.routes.languages import router as languages_router
from backend.api.routes.lesson import router as lesson_router
from backend.api.routes.metrics import router as metrics_router
from backend.api.routes.ingest import router as ingest_router
from backend.api.routes.parse import router as parse_router
from backend.api.routes.parse_jobs import router as parse_jobs_router
from backend.api.routes.ready import router as ready_router
from backend.api.routes.reading import router as reading_router
from backend.api.routes.recommend import router as recommend_router
from backend.api.routes.review import router as review_router
from backend.api.routes.translate import router as translate_router
from backend.api.routes.users import router as users_router
from backend.core.config import Settings, get_settings
from backend.core.logging import RequestIdFilter, request_id_var

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
# Filters must be on handlers, not on loggers, so that propagated records
# from child loggers (e.g. httpx, sqlalchemy) also have request_id injected.
_request_id_filter = RequestIdFilter()
for _h in logging.getLogger().handlers:
    _h.addFilter(_request_id_filter)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

settings = get_settings()


def _init_sentry(s: Settings) -> None:
    """Initialise the Sentry SDK when a DSN is configured.

    A missing or empty DSN is treated as "monitoring disabled" — no exception
    is raised and no network connection is attempted.  This keeps local
    development and CI clean without requiring a real DSN.

    The FastAPI + Starlette integrations are enabled together so that:
      - Unhandled exceptions in route handlers are captured automatically.
      - Request context (URL, method, user) is attached to each event.
      - Performance traces are sent when ``traces_sample_rate > 0``.
    """
    if not s.sentry_dsn:
        return
    environment = s.sentry_environment or ("development" if s.debug else "production")
    sentry_sdk.init(
        dsn=s.sentry_dsn,
        environment=environment,
        integrations=[
            StarletteIntegration(transaction_style="url"),
            FastApiIntegration(transaction_style="url"),
        ],
        # Capture 100 % of errors; sample traces at 5 % to stay inside the
        # free quota on most plans.  Override via SENTRY_TRACES_SAMPLE_RATE.
        traces_sample_rate=0.05,
        # Strip PII — email addresses, IP addresses — from captured events.
        send_default_pii=False,
    )
    logger.info("Sentry initialised (environment=%s)", environment)


_init_sentry(settings)


def _log_config(s: Settings) -> None:
    """Log a sanitised summary of the runtime configuration."""
    # Remove the password from DATABASE_URL before it enters the log stream.
    safe_db = re.sub(r"://([^:]+):[^@]+@", r"://\1:***@", s.database_url)
    logger.info("┌── Mnemosyne ─────────────────────────────────────────")
    logger.info("│  app_name      : %s", s.app_name)
    logger.info("│  debug         : %s", s.debug)
    logger.info("│  database_url  : %s", safe_db)
    logger.info("│  redis_url     : %s", s.redis_url)
    logger.info("│  cors_origins  : %s", s.cors_origins)
    logger.info("│  plugin_package: %s", s.plugin_package)
    logger.info("│  enabled_langs : %s", s.enabled_languages or "all")
    logger.info("│  sentry        : %s", "enabled" if s.sentry_dsn else "disabled")
    logger.info("└──────────────────────────────────────────────────────")


def _warn_config(s: Settings) -> None:
    """Emit warnings for common misconfiguration before traffic arrives."""
    # Wildcard CORS in debug mode is expected; in production it is already
    # rejected by Settings._reject_wildcard_cors_in_production at startup.
    if s.debug and "*" in s.cors_origins:
        logger.warning(
            "CORS_ORIGINS is '*' — this is fine for local development but "
            "must be restricted before deploying (set DEBUG=False to enforce)."
        )
    if s.jwt_secret == "CHANGE_ME_IN_PRODUCTION":
        logger.warning(
            "JWT_SECRET is using the default insecure value. "
            "Set a strong random secret in .env before deploying."
        )
    # Detect unchanged default credentials in DATABASE_URL.
    if "postgres:postgres@" in s.database_url or ":changeme@" in s.database_url:
        logger.warning(
            "DATABASE_URL appears to use default credentials. "
            "Set a strong password in .env before deploying."
        )


# ── Migration helper ──────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).parent.parent


def _run_alembic_upgrade() -> None:
    """Run ``alembic upgrade head`` in a subprocess.

    The project's ``alembic/`` migrations directory shadows the installed
    ``alembic`` package inside this process's import system.  Running the
    ``alembic`` CLI binary as a subprocess sidesteps that collision — the
    binary resolves ``alembic`` from site-packages regardless of CWD.

    DATABASE_URL is injected explicitly so the subprocess receives it even
    when pydantic-settings loaded it from .env without touching os.environ.

    Raises RuntimeError on migration failure so the lifespan warning handler
    can log it and continue (same behaviour as the old create_all path).
    """
    alembic_bin = shutil.which("alembic")
    if alembic_bin is None:
        raise RuntimeError(
            "'alembic' executable not found in PATH. "
            "Install it with: pip install alembic"
        )
    env = {**os.environ, "DATABASE_URL": settings.database_url}
    result = subprocess.run(
        [alembic_bin, "upgrade", "head"],
        cwd=str(_PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        logger.info("alembic: %s", result.stdout.strip())
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade head exited {result.returncode}:\n{result.stderr.strip()}"
        )


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    _log_config(settings)
    _warn_config(settings)

    # Startup health state — read by /ready and the X-Startup-Warning middleware.
    # Each entry is a human-readable sentence shown in the banner and in /ready.
    app.state.startup_errors: list[str] = []

    # Run pending Alembic migrations on startup.
    # _run_alembic_upgrade uses subprocess to avoid the local alembic/ directory
    # shadowing the installed package; asyncio.to_thread prevents blocking the loop.
    try:
        await asyncio.to_thread(_run_alembic_upgrade)
        logger.info("Database migrations applied.")
    except Exception as exc:
        # Condense multi-line alembic output to one readable sentence.
        first_line = str(exc).splitlines()[0][:300]
        msg = (
            f"Database migration failed at startup ({first_line}). "
            "Ensure the database is running and DATABASE_URL is correct. "
            "API calls that require the database will fail until this is resolved."
        )
        logger.error("Startup: %s", msg)
        app.state.startup_errors.append(msg)

    # Load language plugins eagerly so the first request isn't slow.
    registry = get_plugin_registry()
    loaded = list(registry.all().keys())
    if loaded:
        logger.info("Plugins loaded: %s", loaded)
    else:
        logger.warning("No plugins found in package '%s'.", settings.plugin_package)

    logger.info("Startup complete. Serving on http://0.0.0.0:8000")
    yield
    logger.info("Shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _request_id_middleware(request: Request, call_next):
    """Attach a unique request ID to every request.

    Sets ``request.state.request_id`` for use in route handlers and stores the
    ID in a context variable so all log lines emitted during the request (via
    ``RequestIdFilter``) include the same ID.  The ID is echoed back in the
    ``X-Request-Id`` response header so clients can correlate frontend errors
    with server log entries.
    """
    request_id = uuid.uuid4().hex[:8]
    request.state.request_id = request_id
    request_id_var.set(request_id)
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


@app.middleware("http")
async def _startup_warning_middleware(request: Request, call_next):
    """Attach X-Startup-Warning to every response when startup had errors.

    The header value is the first error message, truncated to 500 characters.
    Clients (monitoring dashboards, the frontend health check) can read this
    header on any response to detect degraded-startup state without having to
    poll /ready explicitly.

    Ops routes (/health, /ready) are included — they benefit from the header
    as well since they are the first thing monitoring tools hit.
    """
    response = await call_next(request)
    errors: list[str] = getattr(request.app.state, "startup_errors", [])
    if errors:
        response.headers["X-Startup-Warning"] = errors[0][:500]
    return response


app.include_router(auth_router)
app.include_router(ingest_router)
app.include_router(fetch_url_router)
app.include_router(parse_router)
app.include_router(parse_jobs_router)
app.include_router(lesson_router)
app.include_router(review_router)
app.include_router(dashboard_router)
app.include_router(metrics_router)
app.include_router(reading_router)
app.include_router(recommend_router)
app.include_router(languages_router)
app.include_router(users_router)
app.include_router(translate_router)
app.include_router(ready_router)


# ── Ops endpoints ─────────────────────────────────────────────────────────────


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness probe — 200 when the process is alive.

    Does not check backing services.  Use /ready for that.
    """
    return {"status": "ok"}


# ── Static frontend ───────────────────────────────────────────────────────────
# Mounted last (after every route definition) so all API routes take priority
# over the static file handler in Starlette's route-matching order.
# Serves the frontend at / (index.html) and sub-paths (/css/*, /js/*, etc.).
# The service worker at /sw.js must be on the same origin as the page.
#
# When the frontend directory does not exist (API-only deployments) the mount
# is skipped silently rather than crashing startup.

_FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
