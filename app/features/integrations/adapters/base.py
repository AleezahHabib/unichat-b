from abc import ABC, abstractmethod
from typing import Any
from app.features.integrations.schemas import ExternalChannel


class PlatformAdapter(ABC):
    @abstractmethod
    async def validate_credentials(self) -> dict[str, Any]:
        """Validates bot credentials and returns bot identity metadata."""
        pass

    @abstractmethod
    async def list_channels(self) -> list[ExternalChannel]:
        """Lists external channels on the platform."""
        pass

    @abstractmethod
    async def send_message(
        self,
        external_channel_id: str,
        author_name: str,
        body: str,
        thread_ts: str | None = None,
        webhook_url: str | None = None,
        source: str = "unichat",
    ) -> str:
        """Sends a message to the external platform and returns the external message ID."""
        pass

    @abstractmethod
    async def edit_message(
        self,
        external_channel_id: str,
        external_message_id: str,
        body: str,
        webhook_url: str | None = None,
        thread_ts: str | None = None,
    ) -> bool:
        """Updates an existing message on the external platform."""
        pass

