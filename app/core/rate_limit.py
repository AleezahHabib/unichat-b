import redis.asyncio as aioredis


async def check_rate_limit(
    redis_client: aioredis.Redis,
    key: str,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int, int]:
    """
    Fixed-window rate limiter using INCR + EXPIRE.
    Returns (allowed, current_count, ttl).
    """
    current = await redis_client.incr(key)
    if current == 1:
        await redis_client.expire(key, window_seconds)
        ttl = window_seconds
    else:
        ttl = await redis_client.ttl(key)
        if ttl == -1:  # In case expire didn't get set due to network glitch
            await redis_client.expire(key, window_seconds)
            ttl = window_seconds

    allowed = current <= limit
    return allowed, max(0, ttl)


async def check_ai_rate_limit(redis_client: aioredis.Redis, user_id: str) -> tuple[bool, int]:
    """
    Enforces global AI budget (8 req/min) and per-user AI limit (10 req/min).
    Returns (allowed, retry_after_seconds).
    """
    from app.core.config import settings

    # 1. Check global budget
    g_allowed, g_ttl = await check_rate_limit(
        redis_client, key="rate_limit:ai_global", limit=settings.AI_REQUESTS_PER_MINUTE, window_seconds=60
    )
    if not g_allowed:
        return False, max(1, g_ttl)

    # 2. Check per-user limit
    u_allowed, u_ttl = await check_rate_limit(
        redis_client, key=f"rate_limit:ai_user:{user_id}", limit=10, window_seconds=60
    )
    if not u_allowed:
        return False, max(1, u_ttl)

    return True, 0
