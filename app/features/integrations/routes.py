from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.deps import get_current_user, require_channel_member, require_workspace_member
from app.features.integrations.schemas import (
    ChannelLinkResponse,
    ConnectDiscordRequest,
    ConnectedPlatformResponse,
    ConnectSlackRequest,
    ExternalChannel,
    LinkChannelRequest,
)
from app.features.integrations.service import integration_service

router = APIRouter(tags=["integrations"])


@router.get(
    "/integrations/slack/oauth/start",
    summary="Start Slack OAuth authorization flow",
    response_class=RedirectResponse,
    status_code=status.HTTP_302_FOUND,
)
async def start_slack_oauth(
    workspace_id: UUID = Query(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    user_id = UUID(current_user["sub"])
    auth_url = await integration_service.start_slack_oauth(db, redis, workspace_id, user_id)
    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/integrations/slack/oauth/callback",
    summary="Handle Slack OAuth callback and redirect to frontend",
    response_class=RedirectResponse,
    status_code=status.HTTP_302_FOUND,
)
async def slack_oauth_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    redirect_url = await integration_service.handle_slack_oauth_callback(db, redis, code, state, error)
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/integrations",
    response_model=list[ConnectedPlatformResponse],
    summary="List connected integrations for workspace",
)
async def list_integrations(
    workspace_id: UUID = Query(...),
    _: UUID = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
) -> list[ConnectedPlatformResponse]:
    return await integration_service.list_workspace_integrations(db, workspace_id)



@router.get(
    "/workspaces/{workspace_id}/channel-links",
    response_model=list[ChannelLinkResponse],
    summary="List channel links for a workspace",
)
async def list_workspace_channel_links(
    workspace_id: UUID,
    _: UUID = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
) -> list[ChannelLinkResponse]:
    return await integration_service.list_workspace_channel_links(db, workspace_id)


@router.get(
    "/channels/{channel_id}/links",
    response_model=list[ChannelLinkResponse],
    summary="List links for a specific channel",
)
async def get_channel_links(
    channel_id: UUID,
    _: UUID = Depends(require_channel_member),
    db: AsyncSession = Depends(get_db),
) -> list[ChannelLinkResponse]:
    return await integration_service.get_channel_links(db, channel_id)


@router.post(
    "/integrations/slack/connect",
    response_model=ConnectedPlatformResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect Slack workspace integration",
)
async def connect_slack(
    req: ConnectSlackRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectedPlatformResponse:
    user_id = UUID(current_user["sub"])
    return await integration_service.connect_slack(db, req, user_id)


@router.post(
    "/integrations/discord/connect",
    response_model=ConnectedPlatformResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect Discord bot integration",
)
async def connect_discord(
    req: ConnectDiscordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectedPlatformResponse:
    user_id = UUID(current_user["sub"])
    return await integration_service.connect_discord(db, req, user_id)


@router.delete(
    "/integrations/{platform_id}",
    status_code=status.HTTP_200_OK,
    summary="Disconnect platform integration",
)
async def delete_integration(
    platform_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await integration_service.delete_integration(db, platform_id)
    return {"status": "ok"}


@router.get(
    "/integrations/{platform_id}/external-channels",
    response_model=list[ExternalChannel],
    summary="List channels available on connected platform",
)
async def list_external_channels(
    platform_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ExternalChannel]:
    return await integration_service.list_external_channels(db, platform_id)


@router.post(
    "/channels/{channel_id}/link",
    response_model=ChannelLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Link a UniChat channel to an external platform channel",
)
async def link_channel(
    channel_id: UUID,
    req: LinkChannelRequest,
    _: UUID = Depends(require_channel_member),
    db: AsyncSession = Depends(get_db),
) -> ChannelLinkResponse:
    return await integration_service.link_channel(db, channel_id, req)


@router.delete(
    "/channels/{channel_id}/link",
    status_code=status.HTTP_200_OK,
    summary="Unlink a channel from a platform",
)
async def unlink_channel(
    channel_id: UUID,
    platform: str = Query(...),
    _: UUID = Depends(require_channel_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await integration_service.unlink_channel(db, channel_id, platform)
    return {"status": "ok"}


