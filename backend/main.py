import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.dependencies import get_plugin_registry
from backend.api.routes.dashboard import router as dashboard_router
from backend.api.routes.languages import router as languages_router
from backend.api.routes.lesson import router as lesson_router
from backend.api.routes.parse import router as parse_router
from backend.api.routes.ready import router as ready_router
from backend.api.routes.review import router as review_router
from backend.core.config import Settings, get_settings
from backend.core.database import engine
from backend.models import Base

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

settings = get_settings()


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
    logger.info("└──────────────────────────────────────────────────────")


def _warn_config(s: Settings) -> None:
    """Emit warnings for common misconfiguration before traffic arrives."""
    if not s.debug and "*" in s.cors_origins:
        logger.warning(
            "CORS_ORIGINS contains '*' but DEBUG=False. "
            "Restrict to specific origins before exposing this service."
        )
    # Detect unchanged default credentials in DATABASE_URL.
    if "postgres:postgres@" in s.database_url or ":changeme@" in s.database_url:
        logger.warning(
            "DATABASE_URL appears to use default credentials. "
            "Set a strong password in .env before deploying."
        )


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    _log_config(settings)
    _warn_config(settings)

    # Create DB tables on startup.
    # Replace with `alembic upgrade head` once migrations are in place.
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified.")
    except Exception as exc:
        logger.warning("Database unavailable at startup — continuing: %s", exc)

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parse_router)
app.include_router(lesson_router)
app.include_router(review_router)
app.include_router(dashboard_router)
app.include_router(languages_router)
app.include_router(ready_router)


# ── Ops endpoints ─────────────────────────────────────────────────────────────


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness probe — 200 when the process is alive.

    Does not check backing services.  Use /ready for that.
    """
    return {"status": "ok"}
