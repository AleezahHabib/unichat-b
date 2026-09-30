import asyncio
import logging
import uuid
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

LEADER_KEY = "unichat:leader"
LEADER_TTL = 30
RENEW_INTERVAL = 10

_instance_id = str(uuid.uuid4())
_is_leader = False
_leader_task: asyncio.Task | None = None


def get_instance_id() -> str:
    return _instance_id


def is_leader() -> bool:
    return _is_leader


async def _leader_loop(redis_client: aioredis.Redis) -> None:
    global _is_leader
    while True:
        try:
            # Try to acquire or extend leadership
            if _is_leader:
                # Renew leadership key if we still own it
                val = await redis_client.get(LEADER_KEY)
                if val == _instance_id:
                    await redis_client.expire(LEADER_KEY, LEADER_TTL)
                else:
                    logger.info("Lost leadership to %s", val)
                    _is_leader = False
            else:
                # Try to acquire with NX
                acquired = await redis_client.set(
                    LEADER_KEY, _instance_id, nx=True, ex=LEADER_TTL
                )
                if acquired:
                    _is_leader = True
                    logger.info("Acquired leadership for instance %s", _instance_id)
        except Exception as e:
            logger.warning("Error in leadership loop: %s", e)
            _is_leader = False

        await asyncio.sleep(RENEW_INTERVAL)


def start_leader_election(redis_client: aioredis.Redis) -> asyncio.Task:
    global _leader_task
    if _leader_task is None or _leader_task.done():
        _leader_task = asyncio.create_task(_leader_loop(redis_client))
    return _leader_task


async def stop_leader_election(redis_client: aioredis.Redis) -> None:
    global _leader_task, _is_leader
    if _leader_task and not _leader_task.done():
        _leader_task.cancel()
        try:
            await _leader_task
        except asyncio.CancelledError:
            pass
    if _is_leader:
        try:
            val = await redis_client.get(LEADER_KEY)
            if val == _instance_id:
                await redis_client.delete(LEADER_KEY)
        except Exception:
            pass
        _is_leader = False
