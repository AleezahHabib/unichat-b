import asyncio
import logging
from typing import Any
import httpx

from app.features.integrations.adapters.base import PlatformAdapter
from app.features.integrations.schemas import ExternalChannel

logger = logging.getLogger(__name__)

DISCORD_API_BASE = "https://discord.com/api/v10"


class DiscordAdapter(PlatformAdapter):
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json",
        }

    async def validate_credentials(self) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{DISCORD_API_BASE}/users/@me", headers=self.headers)
            if res.status_code != 200:
                raise ValueError("Invalid Discord bot token")
            data = res.json()
            return {
                "bot_id": str(data["id"]),
                "display_name": data.get("username", "Discord Bot"),
            }

    async def list_channels(self) -> list[ExternalChannel]:
        channels: list[ExternalChannel] = []
        async with httpx.AsyncClient() as client:
            # 1. Fetch guilds
            g_res = await client.get(f"{DISCORD_API_BASE}/users/@me/guilds", headers=self.headers)
            if g_res.status_code != 200:
                return []
            guilds = g_res.json()

            # 2. Fetch channels for each guild
            for guild in guilds:
                g_id = guild["id"]
                g_name = guild.get("name", "Server")
                c_res = await client.get(f"{DISCORD_API_BASE}/guilds/{g_id}/channels", headers=self.headers)
                if c_res.status_code == 200:
                    for ch in c_res.json():
                        if ch.get("type") == 0:  # GUILD_TEXT
                            channels.append(
                                ExternalChannel(
                                    id=str(ch["id"]),
                                    name=ch["name"],
                                    group_name=g_name,
                                )
                            )
        return channels

    async def create_webhook(self, external_channel_id: str) -> tuple[str, str]:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{DISCORD_API_BASE}/channels/{external_channel_id}/webhooks",
                headers=self.headers,
                json={"name": "UniChat Relay"},
            )
            if res.status_code not in (200, 201):
                raise RuntimeError(f"Failed to create Discord webhook: {res.text}")
            data = res.json()
            webhook_id = str(data["id"])
            webhook_token = data["token"]
            webhook_url = f"{DISCORD_API_BASE}/webhooks/{webhook_id}/{webhook_token}"
            return webhook_url, webhook_id

    async def send_message(
        self,
        external_channel_id: str,
        author_name: str,
        body: str,
        thread_ts: str | None = None,
        webhook_url: str | None = None,
        source: str = "unichat",
    ) -> str:
        if not webhook_url:
            raise ValueError("Webhook URL required for Discord send_message")

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

        content = body
        if thread_ts:
            # Prefix thread replies for Discord display
            snippet = thread_ts[:60]
            content = f'↪ replying: "{snippet}"\n{body}'

        payload = {
            "content": content,
            "username": display_name,
            "allowed_mentions": {"parse": []},
        }

        async with httpx.AsyncClient() as client:
            url = f"{webhook_url}?wait=true"
            res = await client.post(url, json=payload)
            if res.status_code not in (200, 201):
                raise RuntimeError(f"Discord webhook post failed: {res.text}")
            data = res.json()
            return str(data["id"])

    async def fetch_messages_after(
        self, external_channel_id: str, after_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        url = f"{DISCORD_API_BASE}/channels/{external_channel_id}/messages?limit={limit}"
        if after_id:
            url += f"&after={after_id}"

        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=self.headers)
            if res.status_code == 429:
                data = res.json()
                retry_after = data.get("retry_after", 3.0)
                await asyncio.sleep(retry_after)
                return []
            if res.status_code != 200:
                return []
            messages = res.json()
            # Discord API returns messages newest-first; sort oldest-first for sequential poller sync
            messages.sort(key=lambda m: m["id"])
            return messages
