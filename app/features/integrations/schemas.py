from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class ConnectSlackRequest(BaseModel):
    workspace_id: UUID
    bot_token: str = Field(..., min_length=1)
    app_token: str = Field(..., min_length=1)


class ConnectDiscordRequest(BaseModel):
    workspace_id: UUID
    bot_token: str = Field(..., min_length=1)


class ConnectedPlatformResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    platform: str
    bot_identity: str | None = None
    display_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ExternalChannel(BaseModel):
    id: str
    name: str
    group_name: str | None = None


class LinkChannelRequest(BaseModel):
    platform_id: UUID
    external_channel_id: str
    external_channel_name: str


class ChannelLinkResponse(BaseModel):
    id: UUID
    channel_id: UUID
    platform_id: UUID
    platform: str
    external_channel_id: str
    external_channel_name: str
    created_at: datetime

    model_config = {"from_attributes": True}
