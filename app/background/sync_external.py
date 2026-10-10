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
from app.features.integrations.adapters.discord_adapter import DiscordAdapter
from app.features.integrations.echo_guard import echo_guard
from app.features.integrations.models import ConnectedPlatform, ChannelLink
from app.features.integrations.service import integration_service
from app.features.messaging.models import Message
from app.features.realtime.events import message_created_event
from app.features.realtime.pubsub import publish_event
from app.features.workspaces_and_channels.models import Channel
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
    platform_id: UUID | None = None,
) -> None:
    """Handles an incoming Socket Mode event from Slack with multi-workspace routing."""
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
    
    # Extract team_id from payload or event (AC-05-10: multi-workspace routing)
    event_team_id = payload.get("team_id") or event.get("team") or payload.get("context_team_id")

    redis = get_redis_client()

    # Layer 3 Echo Guard: Race Window Guard (ignore echoes in active outbound race window)
    if ts and await echo_guard.is_race_window_echo(redis, ts):
        logger.debug("Layer 3 Echo Guard: Ignored outbound race window echo (%s)", ts)
        return

    async with async_session() as db:
        # Multi-workspace routing: Find the matching ConnectedPlatform
        stmt = select(ConnectedPlatform).where(ConnectedPlatform.platform == "slack")
        platforms = (await db.execute(stmt)).scalars().all()

        target_platform: ConnectedPlatform | None = None
        target_bot_token: str | None = None
        target_bot_id: str | None = None

        for p in platforms:
            try:
                tokens = json.loads(decrypt_secret(p.encrypted_tokens))
                p_team_id = tokens.get("team_id")
                if event_team_id and p_team_id == event_team_id:
                    target_platform = p
                    target_bot_token = tokens.get("bot_token")
                    target_bot_id = p.bot_identity
                    break
                elif platform_id and p.id == platform_id:
                    target_platform = p
                    target_bot_token = tokens.get("bot_token")
                    target_bot_id = p.bot_identity
            except Exception:
                continue

        if not target_platform and platforms:
            if len(platforms) == 1:
                target_platform = platforms[0]
                try:
                    tokens = json.loads(decrypt_secret(target_platform.encrypted_tokens))
                    target_bot_token = tokens.get("bot_token")
                    target_bot_id = target_platform.bot_identity
                except Exception:
                    pass

        if not target_platform:
            logger.debug("No Slack connected platform matched for team_id %s", event_team_id)
            return

        # Layer 1 Echo Guard: Identity Filter
        if echo_guard.is_identity_echo(slack_user_id, target_bot_id or "") or echo_guard.is_identity_echo(bot_event_id, target_bot_id or ""):
            logger.debug("Layer 1 Echo Guard: Ignored message from own bot identity (%s)", target_bot_id)
            return

        # Find if this external channel is linked to a UniChat channel under THIS platform
        link_stmt = select(ChannelLink).where(
            ChannelLink.platform == "slack",
            ChannelLink.platform_id == target_platform.id,
            ChannelLink.external_channel_id == external_channel_id,
        )
        link = (await db.execute(link_stmt)).scalar_one_or_none()
        if not link:
            # Fallback by channel ID
            link_stmt_fallback = select(ChannelLink).where(
                ChannelLink.platform == "slack",
                ChannelLink.external_channel_id == external_channel_id,
            )
            link = (await db.execute(link_stmt_fallback)).scalar_one_or_none()
            if not link:
                logger.debug("No UniChat channel linked to Slack channel %s for platform %s", external_channel_id, target_platform.id)
                return

        # Resolve author display name via users.info using the target workspace's bot token
        author_name = "Slack User"
        if slack_user_id and target_bot_token:
            try:
                temp_client = AsyncWebClient(token=target_bot_token)
                user_info = await temp_client.users_info(user=slack_user_id)
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
        bot_token = raw_tokens.get("bot_token")
        app_token = raw_tokens.get("app_token") or settings.SLACK_APP_TOKEN
        if not app_token or not bot_token:
            logger.warning("Missing bot_token or app_token for Slack platform %s", platform.id)
            return

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


async def poll_discord_channels() -> None:
    """
    Polls active Discord channel links for new messages under leader lock.
    Respects AC-05-04 and 3-layer Echo Guard.
    """
    try:
        async with async_session() as db:
            # 1. Fetch active Discord channel links
            stmt = select(ChannelLink).where(ChannelLink.platform == "discord")
            links = (await db.execute(stmt)).scalars().all()
            if not links:
                return

            # 2. Fetch connected platforms for Discord
            p_stmt = select(ConnectedPlatform).where(ConnectedPlatform.platform == "discord")
            platforms = {p.id: p for p in (await db.execute(p_stmt)).scalars().all()}

            redis = get_redis_client()

            for link in links:
                platform = platforms.get(link.platform_id)
                if not platform:
                    continue

                try:
                    tokens = json.loads(decrypt_secret(platform.encrypted_tokens))
                    bot_token = tokens.get("bot_token")
                    if not bot_token:
                        continue
                except Exception as e:
                    logger.error("Error decrypting Discord tokens for platform %s: %s", platform.id, e)
                    continue

                adapter = DiscordAdapter(bot_token)

                # Initialize cursor if not yet set
                if not link.last_synced_external_id:
                    try:
                        init_msgs = await adapter.fetch_messages_after(link.external_channel_id, limit=1)
                        if init_msgs:
                            link.last_synced_external_id = str(init_msgs[-1]["id"])
                            await db.commit()
                            logger.info(
                                "Initialized Discord cursor for channel %s to %s",
                                link.external_channel_id,
                                link.last_synced_external_id,
                            )
                        continue
                    except Exception as e:
                        logger.warning("Error initializing Discord cursor for channel %s: %s", link.external_channel_id, e)
                        continue

                try:
                    messages = await adapter.fetch_messages_after(
                        link.external_channel_id,
                        after_id=link.last_synced_external_id,
                        limit=50,
                    )
                except Exception as e:
                    logger.warning("Error fetching messages for Discord channel %s: %s", link.external_channel_id, e)
                    continue

                if not messages:
                    continue

                for msg in messages:
                    msg_id = str(msg["id"])
                    author = msg.get("author") or {}
                    author_id = str(author.get("id") or "")
                    webhook_id = str(msg.get("webhook_id") or "")
                    own_bot_id = str(platform.bot_identity or "")
                    own_webhook_id = str(link.webhook_id or "")

                    # Layer 1 Echo Guard: Identity Filter
                    if echo_guard.is_identity_echo(
                        author_id=author_id,
                        own_bot_id=own_bot_id,
                        webhook_id=webhook_id,
                        own_webhook_id=own_webhook_id,
                    ) or (own_bot_id and author_id == own_bot_id) or (own_webhook_id and webhook_id == own_webhook_id):
                        logger.debug("Discord Layer 1 Echo Guard: Ignored own bot/webhook message %s", msg_id)
                        link.last_synced_external_id = msg_id
                        await db.commit()
                        continue

                    # Layer 3 Echo Guard: Race Window Guard
                    if await echo_guard.is_race_window_echo(redis, msg_id):
                        logger.debug("Discord Layer 3 Echo Guard: Ignored race window echo %s", msg_id)
                        link.last_synced_external_id = msg_id
                        await db.commit()
                        continue

                    # Resolve author name: nickname -> global_name -> username -> "Discord User"
                    member = msg.get("member") or {}
                    author_name = (
                        member.get("nick")
                        or author.get("global_name")
                        or author.get("username")
                        or "Discord User"
                    )

                    # Thread parent mapping
                    parent_id = None
                    ref_msg_id = (msg.get("message_reference") or {}).get("message_id")
                    if ref_msg_id:
                        parent_stmt = select(Message.id).where(
                            Message.external_channel_id == link.external_channel_id,
                            Message.external_id == str(ref_msg_id),
                        )
                        parent_id = (await db.execute(parent_stmt)).scalar_one_or_none()

                    # Layer 2 Echo Guard: Database Unique Constraint Protection
                    new_msg = Message(
                        channel_id=link.channel_id,
                        author_id=None,
                        external_author_name=author_name,
                        body=msg.get("content", ""),
                        source="discord",
                        external_id=msg_id,
                        external_channel_id=link.external_channel_id,
                        parent_id=parent_id,
                        created_at=datetime.now(timezone.utc),
                    )

                    try:
                        db.add(new_msg)
                        link.last_synced_external_id = msg_id
                        await db.commit()
                        await db.refresh(new_msg)
                    except Exception as e:
                        # Duplicate caught by Layer 2 constraint
                        await db.rollback()
                        link.last_synced_external_id = msg_id
                        await db.commit()
                        logger.debug("Discord Layer 2 Echo Guard: Duplicate message %s ignored (%s)", msg_id, e)
                        continue

                    # Fetch workspace_id for realtime WS event
                    ch_stmt = select(Channel.workspace_id).where(Channel.id == link.channel_id)
                    workspace_id = (await db.execute(ch_stmt)).scalar_one_or_none()

                    if workspace_id:
                        msg_payload = {
                            "id": str(new_msg.id),
                            "channel_id": str(new_msg.channel_id),
                            "author": {
                                "id": None,
                                "name": author_name,
                                "avatar_color": "#5865F2",
                            },
                            "external_author_name": author_name,
                            "body": new_msg.body,
                            "source": "discord",
                            "external_id": new_msg.external_id,
                            "external_channel_id": new_msg.external_channel_id,
                            "parent_id": str(new_msg.parent_id) if new_msg.parent_id else None,
                            "created_at": new_msg.created_at.isoformat(),
                            "edited_at": None,
                            "deleted_at": None,
                            "reply_count": 0,
                        }
                        evt = message_created_event(str(workspace_id), str(link.channel_id), msg_payload)
                        await publish_event(redis, str(workspace_id), evt)

                        # AC-05-06 / Step 4: Cross-platform relay outbound (e.g. to Slack)
                        await integration_service.relay_outbound(db, redis, new_msg, author_name)

                    # Enqueue for embedding
                    enqueue_message_embedding(
                        new_msg.id,
                        link.external_channel_name or "discord",
                        author_name,
                        new_msg.body,
                    )
                    logger.info(
                        "Synced Discord message %s from %s into UniChat channel %s",
                        msg_id,
                        author_name,
                        link.channel_id,
                    )
    except Exception as e:
        logger.error("Error in poll_discord_channels: %s", e, exc_info=True)


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
                    logger.info("External sync loop acquired leader lock. Managing integrations (Slack Socket Mode + Discord poller).")
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

                # Poll Discord channels on each tick under leader lock
                await poll_discord_channels()
            else:
                # If follower or lost leadership, close all active listeners
                active_ids = list(_active_slack_clients.keys())
                for pid in active_ids:
                    await stop_slack_socket_mode_for_platform(pid)

            await asyncio.sleep(settings.DISCORD_POLL_SECONDS)
        except asyncio.CancelledError:
            active_ids = list(_active_slack_clients.keys())
            for pid in active_ids:
                await stop_slack_socket_mode_for_platform(pid)
            break
        except Exception as e:
            logger.warning("Error in sync_external_loop: %s", e)
            await asyncio.sleep(settings.DISCORD_POLL_SECONDS)
