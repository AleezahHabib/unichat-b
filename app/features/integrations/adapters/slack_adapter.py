import time
import logging
from typing import Any
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from app.features.integrations.adapters.base import PlatformAdapter
from app.features.integrations.schemas import ExternalChannel

logger = logging.getLogger(__name__)


class SlackAdapter(PlatformAdapter):
    def __init__(self, bot_token: str, app_token: str | None = None):
        self.bot_token = bot_token
        self.app_token = app_token
        self.client = AsyncWebClient(token=bot_token)
        # user_id -> (name, timestamp)
        self.user_cache: dict[str, tuple[str, float]] = {}

    async def validate_credentials(self) -> dict[str, Any]:
        try:
            res = await self.client.auth_test()
            return {
                "bot_id": res.get("bot_id"),
                "user_id": res.get("user_id"),
                "display_name": res.get("user") or res.get("team") or "Slack Workspace",
                "team_id": res.get("team_id"),
            }
        except SlackApiError as e:
            raise ValueError(f"Invalid Slack bot token: {e.response['error']}")

    async def list_channels(self) -> list[ExternalChannel]:
        try:
            res = await self.client.conversations_list(
                types="public_channel", exclude_archived=True
            )
            channels = res.get("channels", [])
            return [
                ExternalChannel(id=c["id"], name=c["name"]) for c in channels
            ]
        except SlackApiError as e:
            logger.error(f"Error listing Slack channels: {e}")
            return []

    async def join_channel(self, external_channel_id: str) -> None:
        try:
            await self.client.conversations_join(channel=external_channel_id)
        except Exception as e:
            logger.warning(f"Could not join Slack channel {external_channel_id}: {e}")

    async def send_message(
        self,
        external_channel_id: str,
        author_name: str,
        body: str,
        thread_ts: str | None = None,
        webhook_url: str | None = None,
        source: str = "unichat",
    ) -> str:
        try:
            clean_author = author_name
            if " (via " in clean_author:
                clean_author = clean_author.split(" (via ")[0].strip()

            if source == "discord":
                suffix = "(via Discord)"
            elif source == "slack":
                suffix = "(via Slack)"
            else:
                suffix = "(via FistaChat)"

            display_name = f"{clean_author} {suffix}"

            kwargs = {
                "channel": external_channel_id,
                "text": body,
                "username": display_name,
            }
            if thread_ts:
                kwargs["thread_ts"] = thread_ts

            res = await self.client.chat_postMessage(**kwargs)
            return str(res["ts"])
        except SlackApiError as e:
            logger.error(f"Error sending message to Slack: {e}")
            raise RuntimeError(f"Slack post message failed: {e}")

    async def resolve_user_name(self, user_id: str) -> str:
        now = time.time()
        if user_id in self.user_cache:
            name, ts = self.user_cache[user_id]
            if now - ts < 600:  # 10 minutes cache
                return name

        try:
            res = await self.client.users_info(user=user_id)
            user_data = res.get("user", {})
            name = (
                user_data.get("real_name")
                or user_data.get("name")
                or f"Slack User ({user_id})"
            )
            self.user_cache[user_id] = (name, now)
            return name
        except Exception:
            return f"Slack User ({user_id})"
