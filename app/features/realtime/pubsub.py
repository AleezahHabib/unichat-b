import asyncio
import json
import logging
from typing import Any
from redis.asyncio import Redis

from app.features.realtime.connections import connection_manager

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "unichat:ws:"


async def publish_event(
    redis: Redis, workspace_id: str | None, event: dict[str, Any]
) -> None:
    if not workspace_id:
        return
    channel = f"{CHANNEL_PREFIX}{workspace_id}"
    payload = json.dumps(event)
    await connection_manager.broadcast_to_workspace(workspace_id, event)
    try:
        await redis.publish(channel, payload)
    except Exception as e:
        logger.warning(f"Error publishing event to Redis channel {channel}: {e}")


async def start_pubsub_subscriber(redis: Redis) -> None:
    """
    Subscribes to unichat:ws:* pattern and dispatches events to local WebSockets.
    """
    try:
        pubsub = redis.pubsub()
        await pubsub.psubscribe(f"{CHANNEL_PREFIX}*")
        logger.info("Subscribed to Redis pattern unichat:ws:*")

        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                try:
                    channel_name: str = message["channel"]
                    workspace_id = channel_name.replace(CHANNEL_PREFIX, "")
                    data_str: str = message["data"]
                    event = json.loads(data_str)
                    await connection_manager.broadcast_to_workspace(
                        workspace_id, event
                    )
                except Exception as ex:
                    logger.error(f"Error processing pubsub message: {ex}")
    except asyncio.CancelledError:
        logger.info("PubSub subscriber task cancelled")
    except Exception as e:
        logger.warning(f"PubSub subscriber stopped: {e}")
