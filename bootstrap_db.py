import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from backend.core.config import get_settings
from backend.models import Base


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Schema created from current ORM models.")


if __name__ == "__main__":
    asyncio.run(main())