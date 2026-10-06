import json
import logging
import secrets
from uuid import UUID
import httpx

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import decrypt_secret, encrypt_secret
from app.features.authentication.repository import user_repository
from app.features.integrations.adapters.discord_adapter import DiscordAdapter
from app.features.integrations.adapters.slack_adapter import SlackAdapter
from app.features.integrations.echo_guard import echo_guard
from app.features.integrations.models import ChannelLink, ConnectedPlatform
from app.features.integrations.repository import integration_repository
from app.features.integrations.schemas import (
    ChannelLinkResponse,
    ConnectDiscordRequest,
    ConnectedPlatformResponse,
    ConnectSlackRequest,
    ExternalChannel,
    LinkChannelRequest,
)
from app.features.messaging.models import Message
from app.features.messaging.repository import message_repository
from app.features.realtime.events import message_created_event
from app.features.realtime.pubsub import publish_event
from app.features.workspaces_and_channels.repository import workspace_repository

logger = logging.getLogger(__name__)


class IntegrationService:
    async def start_slack_oauth(
        self, db: AsyncSession, redis: Redis, workspace_id: UUID, user_id: UUID
    ) -> str:
        ws = await workspace_repository.get_workspace(db, workspace_id)
        if not ws:
            raise AppError("Workspace not found", code="workspace_not_found", status_code=404)
        if ws.owner_id != user_id:
            raise AppError("Only the workspace owner can connect integrations", code="forbidden", status_code=403)

        if not settings.SLACK_CLIENT_ID or not settings.SLACK_CLIENT_SECRET:
            raise AppError("Slack OAuth credentials are not configured on the server", code="oauth_not_configured", status_code=500)

        state = secrets.token_urlsafe(32)
        redis_key = f"unichat:oauth:slack:{state}"
        payload = json.dumps({"user_id": str(user_id), "workspace_id": str(workspace_id)})
        await redis.set(redis_key, payload, ex=600)

        scopes = "channels:history,channels:read,channels:join,chat:write,chat:write.customize,users:read"
        auth_url = (
            f"https://slack.com/oauth/v2/authorize"
            f"?client_id={settings.SLACK_CLIENT_ID}"
            f"&scope={scopes}"
            f"&redirect_uri={settings.SLACK_REDIRECT_URI}"
            f"&state={state}"
        )
        return auth_url

    async def handle_slack_oauth_callback(
        self,
        db: AsyncSession,
        redis: Redis,
        code: str | None,
        state: str | None,
        error: str | None = None,
    ) -> str:
        fallback_url = f"{settings.FRONTEND_URL.rstrip('/')}/workspaces"
        if error:
            logger.warning("Slack OAuth returned error: %s", error)
            return f"{fallback_url}?error={error}"

        if not state:
            logger.warning("Slack OAuth callback missing state parameter")
            return f"{fallback_url}?error=invalid_state"

        redis_key = f"unichat:oauth:slack:{state}"
        state_data_raw = await redis.get(redis_key)
        if not state_data_raw:
            logger.warning("Slack OAuth CSRF verification failed: state '%s' not found in Redis", state)
            return f"{fallback_url}?error=csrf_rejected"

        # State token is single-use: immediately delete it
        await redis.delete(redis_key)

        try:
            state_data = json.loads(state_data_raw)
            workspace_id = UUID(state_data["workspace_id"])
        except Exception as e:
            logger.error("Failed to parse OAuth state payload: %s", e)
            return f"{fallback_url}?error=invalid_state_payload"

        target_integrations_url = f"{settings.FRONTEND_URL.rstrip('/')}/workspace/{workspace_id}/settings/integrations"

        if not code:
            logger.warning("Slack OAuth callback missing authorization code")
            return f"{target_integrations_url}?error=missing_code"

        # Exchange authorization code for bot token
        try:
            async with httpx.AsyncClient(timeout=15.0) as http_client:
                resp = await http_client.post(
                    "https://slack.com/api/oauth.v2.access",
                    data={
                        "client_id": settings.SLACK_CLIENT_ID,
                        "client_secret": settings.SLACK_CLIENT_SECRET,
                        "code": code,
                        "redirect_uri": settings.SLACK_REDIRECT_URI,
                    },
                )
                data = resp.json()
        except Exception as e:
            logger.error("Failed to communicate with Slack OAuth token endpoint: %s", e)
            return f"{target_integrations_url}?error=slack_exchange_network_error"

        if not data.get("ok"):
            err_msg = data.get("error", "oauth_failed")
            logger.warning("Slack OAuth exchange returned error: %s", err_msg)
            return f"{target_integrations_url}?error={err_msg}"

        bot_token = data.get("access_token")
        bot_user_id = data.get("bot_user_id")
        team = data.get("team") or {}
        team_id = team.get("id")
        team_name = team.get("name") or "Slack Workspace"
        app_token = settings.SLACK_APP_TOKEN

        tokens_json = json.dumps({
            "bot_token": bot_token,
            "app_token": app_token,
            "team_id": team_id,
        })
        encrypted_tokens = encrypt_secret(tokens_json)

        # Upsert into connected_platforms
        existing_platform = await integration_repository.get_workspace_platform(db, workspace_id, "slack")
        if existing_platform:
            existing_platform.encrypted_tokens = encrypted_tokens
            existing_platform.bot_identity = bot_user_id
            existing_platform.display_name = team_name
            await db.commit()
            logger.info("Updated existing Slack integration for workspace %s (team_id=%s)", workspace_id, team_id)
        else:
            await integration_repository.create_platform(
                db,
                workspace_id=workspace_id,
                platform="slack",
                encrypted_tokens=encrypted_tokens,
                bot_identity=bot_user_id,
                display_name=team_name,
            )
            logger.info("Created new Slack integration via OAuth for workspace %s (team_id=%s)", workspace_id, team_id)

        return f"{target_integrations_url}?slack=connected"

    async def connect_slack(
        self, db: AsyncSession, req: ConnectSlackRequest, user_id: UUID
    ) -> ConnectedPlatformResponse:
        ws = await workspace_repository.get_workspace(db, req.workspace_id)
        if not ws:
            raise AppError("Workspace not found", code="workspace_not_found", status_code=404)
        if ws.owner_id != user_id:
            raise AppError("Only the workspace owner can connect integrations", code="forbidden", status_code=403)

        adapter = SlackAdapter(req.bot_token, req.app_token)
        try:
            bot_meta = await adapter.validate_credentials()
        except ValueError as e:
            raise AppError(str(e), code="invalid_tokens", status_code=400)

        tokens_json = json.dumps({"bot_token": req.bot_token, "app_token": req.app_token, "team_id": bot_meta.get("team_id")})
        encrypted_tokens = encrypt_secret(tokens_json)

        existing_platform = await integration_repository.get_workspace_platform(db, req.workspace_id, "slack")
        if existing_platform:
            existing_platform.encrypted_tokens = encrypted_tokens
            existing_platform.bot_identity = bot_meta["bot_id"]
            existing_platform.display_name = bot_meta["display_name"]
            await db.commit()
            await db.refresh(existing_platform)
            return ConnectedPlatformResponse.model_validate(existing_platform)

        cp = await integration_repository.create_platform(
            db,
            workspace_id=req.workspace_id,
            platform="slack",
            encrypted_tokens=encrypted_tokens,
            bot_identity=bot_meta["bot_id"],
            display_name=bot_meta["display_name"],
        )
        return ConnectedPlatformResponse.model_validate(cp)


    async def connect_discord(
        self, db: AsyncSession, req: ConnectDiscordRequest, user_id: UUID
    ) -> ConnectedPlatformResponse:
        ws = await workspace_repository.get_workspace(db, req.workspace_id)
        if not ws:
            raise AppError("Workspace not found", code="workspace_not_found", status_code=404)
        if ws.owner_id != user_id:
            raise AppError("Only the workspace owner can connect integrations", code="forbidden", status_code=403)

        adapter = DiscordAdapter(req.bot_token)
        try:
            bot_meta = await adapter.validate_credentials()
        except ValueError as e:
            raise AppError(str(e), code="invalid_token", status_code=400)

        tokens_json = json.dumps({"bot_token": req.bot_token})
        encrypted_tokens = encrypt_secret(tokens_json)

        cp = await integration_repository.create_platform(
            db,
            workspace_id=req.workspace_id,
            platform="discord",
            encrypted_tokens=encrypted_tokens,
            bot_identity=bot_meta["bot_id"],
            display_name=bot_meta["display_name"],
        )
        return ConnectedPlatformResponse.model_validate(cp)

    async def list_workspace_integrations(
        self, db: AsyncSession, workspace_id: UUID
    ) -> list[ConnectedPlatformResponse]:
        platforms = await integration_repository.list_workspace_platforms(db, workspace_id)
        return [ConnectedPlatformResponse.model_validate(p) for p in platforms]

    async def get_channel_links(
        self, db: AsyncSession, channel_id: UUID
    ) -> list[ChannelLinkResponse]:
        links = await integration_repository.get_channel_links(db, channel_id)
        return [ChannelLinkResponse.model_validate(l) for l in links]

    async def list_workspace_channel_links(
        self, db: AsyncSession, workspace_id: UUID
    ) -> list[ChannelLinkResponse]:
        platforms = await integration_repository.list_workspace_platforms(db, workspace_id)
        for platform in platforms:
            try:
                await self.list_external_channels(db, platform.id)
            except Exception as e:
                logger.warning("Could not refresh external channels for platform %s: %s", platform.id, e)

        links = await integration_repository.list_workspace_channel_links(db, workspace_id)
        return [ChannelLinkResponse.model_validate(l) for l in links]

    async def delete_integration(self, db: AsyncSession, platform_id: UUID) -> None:
        platform = await integration_repository.get_platform(db, platform_id)
        if not platform:
            raise AppError("Integration not found", code="integration_not_found", status_code=404)
        await integration_repository.delete_platform(db, platform_id)

    async def list_external_channels(
        self, db: AsyncSession, platform_id: UUID
    ) -> list[ExternalChannel]:
        platform = await integration_repository.get_platform(db, platform_id)
        if not platform:
            raise AppError("Integration not found", code="integration_not_found", status_code=404)

        raw_tokens = json.loads(decrypt_secret(platform.encrypted_tokens))
        live_channels: list[ExternalChannel] = []
        if platform.platform == "slack":
            adapter = SlackAdapter(raw_tokens["bot_token"], raw_tokens.get("app_token"))
            live_channels = await adapter.list_channels()
        elif platform.platform == "discord":
            adapter = DiscordAdapter(raw_tokens["bot_token"])
            live_channels = await adapter.list_channels()

        # Opportunistic metadata refresh: sync cached external_channel_name with live platform name
        if live_channels:
            links = await integration_repository.list_platform_links(db, platform_id)
            channel_map = {
                (ch["id"] if isinstance(ch, dict) else ch.id): (
                    ch["name"] if isinstance(ch, dict) else ch.name
                )
                for ch in live_channels
            }
            updated = False
            for link in links:
                if link.external_channel_id in channel_map:
                    fresh_name = channel_map[link.external_channel_id]
                    if link.external_channel_name != fresh_name:
                        link.external_channel_name = fresh_name
                        updated = True
            if updated:
                await db.commit()

        return live_channels

    async def link_channel(
        self, db: AsyncSession, channel_id: UUID, req: LinkChannelRequest
    ) -> ChannelLinkResponse:
        platform = await integration_repository.get_platform(db, req.platform_id)
        if not platform:
            raise AppError("Integration not found", code="integration_not_found", status_code=404)

        # Check if this external channel is already linked to a different UniChat channel
        existing_ext_link = await integration_repository.get_link_by_external_channel(
            db, platform.platform, req.external_channel_id
        )
        if existing_ext_link and existing_ext_link.channel_id != channel_id:
            raise AppError(
                f"External channel #{req.external_channel_name} is already linked to another channel in UniChat.",
                code="channel_already_linked",
                status_code=409,
            )

        raw_tokens = json.loads(decrypt_secret(platform.encrypted_tokens))
        webhook_url_enc: str | None = None
        webhook_id: str | None = None

        if platform.platform == "slack":
            adapter = SlackAdapter(raw_tokens["bot_token"])
            await adapter.join_channel(req.external_channel_id)
        elif platform.platform == "discord":
            adapter = DiscordAdapter(raw_tokens["bot_token"])
            webhook_url, webhook_id = await adapter.create_webhook(req.external_channel_id)
            webhook_url_enc = encrypt_secret(webhook_url)

        # Check if the UniChat channel already has a link for this platform (upsert behavior)
        existing_links = await integration_repository.get_channel_links(db, channel_id)
        current_platform_link = next((l for l in existing_links if l.platform == platform.platform), None)

        if current_platform_link:
            current_platform_link.platform_id = req.platform_id
            current_platform_link.external_channel_id = req.external_channel_id
            current_platform_link.external_channel_name = req.external_channel_name
            if webhook_url_enc:
                current_platform_link.encrypted_webhook_url = webhook_url_enc
                current_platform_link.webhook_id = webhook_id
            await db.commit()
            await db.refresh(current_platform_link)
            return ChannelLinkResponse.model_validate(current_platform_link)

        link = await integration_repository.create_channel_link(
            db,
            channel_id=channel_id,
            platform_id=req.platform_id,
            platform=platform.platform,
            external_channel_id=req.external_channel_id,
            external_channel_name=req.external_channel_name,
            encrypted_webhook_url=webhook_url_enc,
            webhook_id=webhook_id,
        )
        return ChannelLinkResponse.model_validate(link)

    async def unlink_channel(
        self, db: AsyncSession, channel_id: UUID, platform: str
    ) -> None:
        await integration_repository.remove_channel_link(db, channel_id, platform)

    async def relay_outbound(
        self, db: AsyncSession, redis: Redis, message: Message, author_name: str
    ) -> None:
        """
        Relays a native or cross-platform message to connected external platforms.
        Only skips sending back to the message's own source platform.
        """
        logger.info("relay_outbound called for message %s (source=%s, channel=%s)", message.id, message.source, message.channel_id)
        links = await integration_repository.get_channel_links(db, message.channel_id)
        if not links:
            logger.info("relay_outbound: no channel links found for channel %s", message.channel_id)
            return

        thread_ts: str | None = None
        if message.parent_id:
            parent = await message_repository.get_message_by_id(db, message.parent_id)
            if parent:
                thread_ts = parent.external_id or parent.body[:60]

        for link in links:
            logger.info("relay_outbound: checking link platform=%s vs message.source=%s", link.platform, message.source)
            # Skip relaying back to the originating platform
            if link.platform == message.source:
                logger.info("relay_outbound: skipping link (same platform as source)")
                continue

            platform = await integration_repository.get_platform(db, link.platform_id)
            if not platform:
                logger.warning("relay_outbound: platform %s not found", link.platform_id)
                continue

            raw_tokens = json.loads(decrypt_secret(platform.encrypted_tokens))

            try:
                if link.platform == "slack":
                    adapter = SlackAdapter(raw_tokens["bot_token"])
                    logger.info("relay_outbound: sending to Slack channel %s", link.external_channel_id)
                    ext_id = await adapter.send_message(
                        external_channel_id=link.external_channel_id,
                        author_name=author_name,
                        body=message.body,
                        thread_ts=thread_ts,
                    )
                    logger.info("relay_outbound: Slack message sent, ext_id=%s", ext_id)
                    await echo_guard.set_race_window(redis, ext_id)

                elif link.platform == "discord" and link.encrypted_webhook_url:
                    webhook_url = decrypt_secret(link.encrypted_webhook_url)
                    adapter = DiscordAdapter(raw_tokens["bot_token"])
                    ext_id = await adapter.send_message(
                        external_channel_id=link.external_channel_id,
                        author_name=author_name,
                        body=message.body,
                        thread_ts=thread_ts,
                        webhook_url=webhook_url,
                    )
                    await echo_guard.set_race_window(redis, ext_id)
            except Exception as e:
                logger.error("relay_outbound: failed to relay to %s: %s", link.platform, e, exc_info=True)


integration_service = IntegrationService()

