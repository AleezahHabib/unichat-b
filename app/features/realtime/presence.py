import logging
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

PRESENCE_PREFIX = "unichat:presence:"
PRESENCE_TTL_SECONDS = 60


class PresenceManager:
    async def set_online(self, redis: Redis, user_id: str) -> None:
        try:
            key = f"{PRESENCE_PREFIX}{user_id}"
            await redis.set(key, "1", ex=PRESENCE_TTL_SECONDS)
        except Exception as e:
            logger.warning(f"Error setting presence online for {user_id}: {e}")

    async def refresh_ping(self, redis: Redis, user_id: str) -> None:
        await self.set_online(redis, user_id)

    async def set_offline(self, redis: Redis, user_id: str) -> None:
        try:
            key = f"{PRESENCE_PREFIX}{user_id}"
            await redis.delete(key)
        except Exception as e:
            logger.warning(f"Error deleting presence for {user_id}: {e}")

    async def is_online(self, redis: Redis, user_id: str) -> bool:
        try:
            key = f"{PRESENCE_PREFIX}{user_id}"
            val = await redis.get(key)
            return val is not None
        except Exception as e:
            logger.warning(f"Error checking presence for {user_id}: {e}")
            return False


presence_manager = PresenceManager()
