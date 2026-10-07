from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_channel_member, require_workspace_member
from app.features.workspaces_and_channels.schemas import (
    AcceptInviteResponse,
    ChannelMemberResponse,
    ChannelResponse,
    CreateChannelRequest,
    CreateInviteResponse,
    CreateWorkspaceRequest,
    InvitePreviewResponse,
    WorkspaceMemberResponse,
    WorkspaceResponse,
)
from app.features.workspaces_and_channels.service import workspace_service

router = APIRouter(tags=["workspaces_and_channels"])


@router.get(
    "/workspaces",
    response_model=list[WorkspaceResponse],
    summary="List workspaces for current user",
)
async def list_workspaces(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceResponse]:
    user_id = UUID(current_user["sub"])
    return await workspace_service.list_user_workspaces(db, user_id)


@router.post(
    "/workspaces",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
)
async def create_workspace(
    req: CreateWorkspaceRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    user_id = UUID(current_user["sub"])
    return await workspace_service.create_workspace(db, req, user_id)


@router.delete(
    "/workspaces/{workspace_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a workspace (Owner only)",
)
async def delete_workspace(
    workspace_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user_id = UUID(current_user["sub"])
    await workspace_service.delete_workspace(db, workspace_id, user_id)
    return {"status": "ok"}


@router.post(
    "/workspaces/{workspace_id}/leave",
    status_code=status.HTTP_200_OK,
    summary="Leave a workspace (removes from workspace and all channels; owner cannot leave)",
)
async def leave_workspace(
    workspace_id: UUID,
    current_user: dict = Depends(get_current_user),
    _: UUID = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user_id = UUID(current_user["sub"])
    await workspace_service.leave_workspace(db, workspace_id, user_id)
    return {"message": "Successfully left workspace"}


@router.delete(
    "/workspaces/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove a member from a workspace (Owner only)",
)
async def remove_workspace_member(
    workspace_id: UUID,
    user_id: UUID,
    current_user: dict = Depends(get_current_user),
    _: UUID = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    caller_id = UUID(current_user["sub"])
    await workspace_service.remove_member(db, workspace_id, caller_id, user_id)
    return {"message": "Member removed successfully"}


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=list[WorkspaceMemberResponse],
    summary="List workspace members",
)
async def list_workspace_members(
    workspace_id: UUID,
    _: UUID = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceMemberResponse]:
    return await workspace_service.list_workspace_members(db, workspace_id)


@router.post(
    "/workspaces/{workspace_id}/invites",
    response_model=CreateInviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workspace invite link",
)
async def create_invite(
    workspace_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CreateInviteResponse:
    user_id = UUID(current_user["sub"])
    return await workspace_service.create_invite(db, workspace_id, user_id)


@router.get(
    "/invites/{token}",
    response_model=InvitePreviewResponse,
    summary="Preview workspace invite link details",
)
async def get_invite_preview(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InvitePreviewResponse:
    return await workspace_service.get_invite_preview(db, token)


@router.post(
    "/invites/{token}/accept",
    response_model=AcceptInviteResponse,
    summary="Accept workspace invite",
)
async def accept_invite(
    token: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AcceptInviteResponse:
    user_id = UUID(current_user["sub"])
    return await workspace_service.accept_invite(db, token, user_id)


@router.get(
    "/workspaces/{workspace_id}/channels",
    response_model=list[ChannelResponse],
    summary="List channels in workspace",
)
async def list_workspace_channels(
    workspace_id: UUID,
    joined_only: bool = False,
    current_user: dict = Depends(get_current_user),
    _: UUID = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
) -> list[ChannelResponse]:
    user_id = UUID(current_user["sub"])
    return await workspace_service.list_workspace_channels(db, workspace_id, user_id=user_id if joined_only else None)


@router.post(
    "/workspaces/{workspace_id}/channels",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a channel in workspace",
)
async def create_channel(
    workspace_id: UUID,
    req: CreateChannelRequest,
    current_user: dict = Depends(get_current_user),
    _: UUID = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
) -> ChannelResponse:
    user_id = UUID(current_user["sub"])
    return await workspace_service.create_channel(db, workspace_id, req, user_id)


@router.post(
    "/channels/{channel_id}/join",
    status_code=status.HTTP_200_OK,
    summary="Join a channel",
)
async def join_channel(
    channel_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user_id = UUID(current_user["sub"])
    await workspace_service.join_channel(db, channel_id, user_id)
    return {"status": "ok"}


@router.post(
    "/channels/{channel_id}/leave",
    status_code=status.HTTP_200_OK,
    summary="Leave a channel",
)
async def leave_channel(
    channel_id: UUID,
    current_user: dict = Depends(get_current_user),
    _: UUID = Depends(require_channel_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user_id = UUID(current_user["sub"])
    await workspace_service.leave_channel(db, channel_id, user_id)
    return {"status": "ok"}


@router.get(
    "/channels/{channel_id}/members",
    response_model=list[ChannelMemberResponse],
    summary="List channel members",
)
async def list_channel_members(
    channel_id: UUID,
    _: UUID = Depends(require_channel_member),
    db: AsyncSession = Depends(get_db),
) -> list[ChannelMemberResponse]:
    return await workspace_service.list_channel_members(db, channel_id)
