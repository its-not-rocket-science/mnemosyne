import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.lesson import router as lesson_router
from backend.api.routes.parse import router as parse_router
from backend.api.routes.review import router as review_router
from backend.core.config import get_settings
from backend.api.dependencies import get_plugin_registry
from backend.core.database import engine
from backend.models import Base

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup.  In production, replace with Alembic migrations
    # (`alembic upgrade head`) and remove this block.
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified.")
    except Exception as exc:
        logger.warning("Could not initialise database tables: %s", exc)

    registry = get_plugin_registry()
    loaded = list(registry.all().keys())
    if loaded:
        logger.info("Plugins loaded: %s", loaded)
    else:
        logger.warning("No plugins found in package '%s'.", settings.plugin_package)
    yield


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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
