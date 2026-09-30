from collections.abc import AsyncGenerator
import redis.asyncio as aioredis

from app.core.config import settings

redis_client: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis:
    global redis_client
    if redis_client is None:
        if not settings.REDIS_URL:
            raise RuntimeError(
                "REDIS_URL environment variable is not configured in backend/.env. "
                "UniChat requires an Upstash Redis connection string."
            )
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    return redis_client


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    client = get_redis_client()
    yield client
