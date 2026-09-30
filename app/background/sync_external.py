import asyncio
import json
import logging
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

from app.core.config import settings
from app.core.database import async_session
from app.core.leader import is_leader
from app.core.redis import get_redis_client
from app.core.security import decrypt_secret
from app.features.integrations.echo_guard import echo_guard
from app.features.integrations.models import ConnectedPlatform, ChannelLink
from app.features.integrations.service import integration_service
from app.features.messaging.models import Message
from app.features.realtime.pubsub import publish_event
from app.background.embed_worker import enqueue_message_embedding

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Active Slack Socket Mode clients: platform_id -> (SocketModeClient, AsyncWebClient)
_active_slack_clients: dict[UUID, tuple[SocketModeClient, AsyncWebClient, str]] = {}



def get_background_status() -> str:
    if not settings.ENABLE_BACKGROUND:
        return "off"
    return "leader" if is_leader() else "follower"


async def process_slack_event(
    req: SocketModeRequest,
    client: SocketModeClient,
    web_client: AsyncWebClient,
    bot_id: str,
    platform_id: UUID,
) -> None:
    """Handles an incoming Socket Mode event from Slack."""
    # Acknowledge the request immediately (within 3 seconds per AC-05-03)
    response = SocketModeResponse(envelope_id=req.envelope_id)
    await client.send_socket_mode_response(response)

    if req.type != "events_api":
        return

    payload = req.payload
    event = payload.get("event", {})
    if event.get("type") != "message":
        return

    # Check subtypes — ignore message edits/deletions/join/leave unless regular message
    subtype = event.get("subtype")
    if subtype is not None and subtype != "thread_broadcast":
        return

    slack_user_id = event.get("user")
    external_channel_id = event.get("channel")
    text = event.get("text", "")
    ts = event.get("ts")
    thread_ts = event.get("thread_ts")
    bot_event_id = event.get("bot_id")

    # Layer 1 Echo Guard: Identity Filter (ignore messages from own bot identity)
    if echo_guard.is_identity_echo(slack_user_id, bot_id) or echo_guard.is_identity_echo(bot_event_id, bot_id):
        logger.debug("Layer 1 Echo Guard: Ignored message from own bot identity (%s)", bot_id)
        return

    redis = get_redis_client()

    # Layer 3 Echo Guard: Race Window Guard (ignore echoes in active outbound race window)
    if ts and await echo_guard.is_race_window_echo(redis, ts):
        logger.debug("Layer 3 Echo Guard: Ignored outbound race window echo (%s)", ts)
        return

    async with async_session() as db:
        # Find if this external channel is linked to a UniChat channel
        link_stmt = select(ChannelLink).where(
            ChannelLink.platform == "slack",
            ChannelLink.external_channel_id == external_channel_id,
        )
        link = (await db.execute(link_stmt)).scalar_one_or_none()
        if not link:
            logger.debug("No UniChat channel linked to Slack channel %s", external_channel_id)
            return

        # Resolve author display name via users.info
        author_name = "Slack User"
        if slack_user_id:
            try:
                user_info = await web_client.users_info(user=slack_user_id)
                user_data = user_info.get("user", {})
                author_name = (
                    user_data.get("real_name")
                    or user_data.get("name")
                    or f"Slack User ({slack_user_id})"
                )
            except Exception as e:
                logger.warning("Could not resolve Slack user info for %s: %s", slack_user_id, e)
                author_name = f"Slack User ({slack_user_id})"

        # Handle thread parent mapping
        parent_id = None
        if thread_ts and thread_ts != ts:
            parent_stmt = select(Message.id).where(
                Message.external_channel_id == external_channel_id,
                Message.external_id == thread_ts,
            )
            parent_id = (await db.execute(parent_stmt)).scalar_one_or_none()

        # Insert message into database with Layer 2 constraint protection
        new_msg = Message(
            channel_id=link.channel_id,
            author_id=None,
            external_author_name=author_name,
            body=text,
            source="slack",
            external_id=ts,
            external_channel_id=external_channel_id,
            parent_id=parent_id,
            created_at=datetime.now(timezone.utc),
        )

        try:
            db.add(new_msg)
            await db.commit()
            await db.refresh(new_msg)
        except Exception as e:
            # Layer 2 Echo Guard: Duplicate external_id caught by uq_messages_external
            await db.rollback()
            logger.debug("Layer 2 Echo Guard: Duplicate message %s ignored (%s)", ts, e)
            return

        # Fetch workspace_id for the channel
        from app.features.workspaces_and_channels.models import Channel
        ch_stmt = select(Channel.workspace_id).where(Channel.id == link.channel_id)
        workspace_id = (await db.execute(ch_stmt)).scalar_one_or_none()

        if workspace_id:
            # Publish Realtime WebSocket event
            msg_payload = {
                "id": str(new_msg.id),
                "channel_id": str(new_msg.channel_id),
                "author": {
                    "id": None,
                    "name": author_name,
                    "avatar_color": "#4A154B",
                },
                "external_author_name": author_name,
                "body": new_msg.body,
                "source": "slack",
                "external_id": new_msg.external_id,
                "external_channel_id": new_msg.external_channel_id,
                "parent_id": str(new_msg.parent_id) if new_msg.parent_id else None,
                "created_at": new_msg.created_at.isoformat(),
                "edited_at": None,
                "deleted_at": None,
                "reply_count": 0,
            }
            from app.features.realtime.events import message_created_event
            evt = message_created_event(str(workspace_id), str(link.channel_id), msg_payload)
            await publish_event(redis, str(workspace_id), evt)

            # AC-05-06: Cross-platform relaying to other connected platforms (e.g. Discord)
            await integration_service.relay_outbound(db, redis, new_msg, author_name)

        # Enqueue for embedding
        enqueue_message_embedding(new_msg.id, link.external_channel_name or "slack", author_name, new_msg.body)
        logger.info("Synced Slack message %s from %s into UniChat channel %s", ts, author_name, link.channel_id)




async def start_slack_socket_mode_for_platform(platform: ConnectedPlatform) -> None:
    """Instantiates and starts a SocketModeClient for a Slack integration."""
    try:
        raw_tokens = json.loads(decrypt_secret(platform.encrypted_tokens))
        bot_token = raw_tokens["bot_token"]
        app_token = raw_tokens["app_token"]

        web_client = AsyncWebClient(token=bot_token)
        socket_client = SocketModeClient(app_token=app_token, web_client=web_client)

        bot_id = platform.bot_identity or ""

        async def _handler(client: SocketModeClient, req: SocketModeRequest):
            await process_slack_event(req, client, web_client, bot_id, platform.id)

        socket_client.socket_mode_request_listeners.append(_handler)
        await socket_client.connect()
        _active_slack_clients[platform.id] = (socket_client, web_client, bot_id)
        logger.info("Connected Slack Socket Mode listener for platform %s (%s)", platform.id, platform.display_name)
    except Exception as e:
        logger.error("Failed to connect Slack Socket Mode for platform %s: %s", platform.id, e)


async def stop_slack_socket_mode_for_platform(platform_id: UUID) -> None:
    """Closes and removes a SocketModeClient."""
    if platform_id in _active_slack_clients:
        client, web_client, _ = _active_slack_clients.pop(platform_id)
        try:
            await client.close()
            await web_client.session.close()
            logger.info("Closed Slack Socket Mode client for platform %s", platform_id)
        except Exception as e:
            logger.warning("Error closing Slack client for platform %s: %s", platform_id, e)


async def sync_external_loop() -> None:
    """
    Background worker loop that manages Socket Mode listeners and pollers
    under the Redis leader lock.
    """
    last_leader_state: bool | None = None

    while True:
        try:
            current_leader = is_leader()
            if current_leader != last_leader_state:
                if current_leader:
                    logger.info("External sync loop acquired leader lock. Managing integrations.")
                else:
                    logger.info("External sync loop lost leader lock or running as follower.")
                last_leader_state = current_leader

            if current_leader:
                async with async_session() as db:
                    # Fetch all connected Slack platforms
                    stmt = select(ConnectedPlatform).where(ConnectedPlatform.platform == "slack")
                    platforms = (await db.execute(stmt)).scalars().all()
                    current_db_ids = {p.id for p in platforms}

                    # Drop dead connections so they reconnect
                    for pid, (client, _, _) in list(_active_slack_clients.items()):
                        if not await client.is_connected():
                            logger.warning("Slack Socket Mode disconnected for platform %s. Dropping to reconnect.", pid)
                            await stop_slack_socket_mode_for_platform(pid)

                    # Start any new platforms not yet connected
                    for platform in platforms:
                        if platform.id not in _active_slack_clients:
                            await start_slack_socket_mode_for_platform(platform)

                    # Stop any removed platforms
                    active_ids = list(_active_slack_clients.keys())
                    for pid in active_ids:
                        if pid not in current_db_ids:
                            await stop_slack_socket_mode_for_platform(pid)
            else:
                # If follower or lost leadership, close all active listeners
                active_ids = list(_active_slack_clients.keys())
                for pid in active_ids:
                    await stop_slack_socket_mode_for_platform(pid)

            await asyncio.sleep(5)
        except asyncio.CancelledError:
            active_ids = list(_active_slack_clients.keys())
            for pid in active_ids:
                await stop_slack_socket_mode_for_platform(pid)
            break
        except Exception as e:
            logger.warning("Error in sync_external_loop: %s", e)
            await asyncio.sleep(5)
