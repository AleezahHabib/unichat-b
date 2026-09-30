import logging
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

ECHO_RACE_PREFIX = "unichat:echo_guard:"
ECHO_RACE_TTL_SECONDS = 30


class EchoGuard:
    """
    Three-layer Echo Guard:
    1. Identity filter (checks if author is own bot_user or webhook_id).
    2. DB Constraint (partial unique index uq_messages_external + ON CONFLICT DO NOTHING).
    3. Race Window Guard (30s Redis key for outbound messages).
    """

    def is_identity_echo(
        self,
        author_id: str | None,
        own_bot_id: str | None,
        webhook_id: str | None = None,
        own_webhook_id: str | None = None,
    ) -> bool:
        if own_bot_id and author_id and str(author_id) == str(own_bot_id):
            return True
        if own_webhook_id and webhook_id and str(webhook_id) == str(own_webhook_id):
            return True
        return False

    async def set_race_window(self, redis: Redis | None, external_id: str) -> None:
        if not redis or not external_id:
            return
        try:
            key = f"{ECHO_RACE_PREFIX}{external_id}"
            await redis.set(key, "1", ex=ECHO_RACE_TTL_SECONDS)
        except Exception as e:
            logger.warning(f"Error setting echo guard race window for {external_id}: {e}")

    async def is_race_window_echo(self, redis: Redis | None, external_id: str) -> bool:
        if not redis or not external_id:
            return False
        try:
            key = f"{ECHO_RACE_PREFIX}{external_id}"
            val = await redis.get(key)
            return val is not None
        except Exception as e:
            logger.warning(f"Error checking echo guard race window for {external_id}: {e}")
            return False


echo_guard = EchoGuard()
