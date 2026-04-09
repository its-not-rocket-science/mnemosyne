import json
import logging

from redis.asyncio import Redis

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: Redis | None = None


async def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def get_json(key: str) -> dict | list | None:
    redis = await get_redis()
    value = await redis.get(key)
    if value is None:
        logger.debug("cache MISS key=%s", key)
        return None
    logger.debug("cache HIT key=%s", key)
    return json.loads(value)


async def set_json(key: str, value: dict | list, ttl_seconds: int = 3600) -> None:
    redis = await get_redis()
    await redis.set(key, json.dumps(value), ex=ttl_seconds)
    logger.debug("cache SET key=%s ttl=%d", key, ttl_seconds)
