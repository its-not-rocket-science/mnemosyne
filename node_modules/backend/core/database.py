from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=settings.debug, future=True)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


def get_session_factory() -> async_sessionmaker:
    """Return the active session factory.

    Exposed as a FastAPI dependency so background tasks (which need their own
    session) can be injected with a test-overridable factory instead of
    importing ``SessionLocal`` directly.

    Override in tests alongside ``get_db_session`` to ensure background tasks
    write to the same in-memory database as the route handlers::

        app.dependency_overrides[get_session_factory] = lambda: test_factory
    """
    return SessionLocal
