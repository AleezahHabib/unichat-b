import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.features.authentication.repository import user_repository
from app.features.workspaces_and_channels.repository import workspace_repository
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


def normalize_channel_name(name: str) -> str:
    cleaned = name.lower().strip()
    cleaned = re.sub(r"[^\w\s-]", "", cleaned)
    cleaned = re.sub(r"[\s_]+", "-", cleaned)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    if not cleaned:
        raise AppError("Invalid channel name", code="invalid_channel_name", status_code=400)
    return cleaned[:80]


class WorkspaceService:
    async def create_workspace(
        self, db: AsyncSession, req: CreateWorkspaceRequest, owner_id: UUID
    ) -> WorkspaceResponse:
        name = req.name.strip()
        if not name:
            raise AppError("Workspace name required", code="invalid_name", status_code=400)
        ws = await workspace_repository.create_workspace(db, name, owner_id)
        return WorkspaceResponse.model_validate(ws)

    async def delete_workspace(
        self, db: AsyncSession, workspace_id: UUID, current_user_id: UUID
    ) -> None:
        ws = await workspace_repository.get_workspace(db, workspace_id)
        if not ws:
            raise AppError("Workspace not found", code="workspace_not_found", status_code=404)
        if ws.owner_id != current_user_id:
            raise AppError("Only the workspace owner can delete the workspace", code="forbidden", status_code=403)

        await workspace_repository.delete_workspace(db, workspace_id)

    async def list_user_workspaces(
        self, db: AsyncSession, user_id: UUID
    ) -> list[WorkspaceResponse]:
        workspaces = await workspace_repository.list_user_workspaces(db, user_id)
        return [WorkspaceResponse.model_validate(w) for w in workspaces]

    async def list_workspace_members(
        self, db: AsyncSession, workspace_id: UUID
    ) -> list[WorkspaceMemberResponse]:
        members = await workspace_repository.list_workspace_members(db, workspace_id)
        return [
            WorkspaceMemberResponse(
                id=m["user_id"],
                user_id=m["user_id"],
                name=m["name"],
                email=m["email"],
                avatar_color=m["avatar_color"],
                role=m["role"],
                joined_at=m["joined_at"],
                online=False,
            )
            for m in members
        ]

    async def leave_workspace(
        self, db: AsyncSession, workspace_id: UUID, user_id: UUID
    ) -> None:
        ws = await workspace_repository.get_workspace(db, workspace_id)
        if not ws:
            raise AppError("Workspace not found", code="workspace_not_found", status_code=404)
        if ws.owner_id == user_id:
            raise AppError("Workspace owner cannot leave workspace", code="owner_cannot_leave", status_code=403)

        await workspace_repository.remove_workspace_member_all_channels(db, workspace_id, user_id)

    async def remove_member(
        self, db: AsyncSession, workspace_id: UUID, current_user_id: UUID, target_user_id: UUID
    ) -> None:
        ws = await workspace_repository.get_workspace(db, workspace_id)
        if not ws:
            raise AppError("Workspace not found", code="workspace_not_found", status_code=404)
        if ws.owner_id != current_user_id:
            raise AppError("Only the workspace owner can remove members", code="forbidden", status_code=403)
        if target_user_id == current_user_id:
            raise AppError("Cannot remove workspace owner", code="cannot_remove_owner", status_code=400)

        members = await workspace_repository.list_workspace_members(db, workspace_id)
        if not any(m["user_id"] == target_user_id for m in members):
            raise AppError("Member not found in workspace", code="member_not_found", status_code=404)

        await workspace_repository.remove_workspace_member_all_channels(db, workspace_id, target_user_id)

    async def create_invite(
        self, db: AsyncSession, workspace_id: UUID, current_user_id: UUID
    ) -> CreateInviteResponse:
        ws = await workspace_repository.get_workspace(db, workspace_id)
        if not ws:
            raise AppError("Workspace not found", code="workspace_not_found", status_code=404)
        if ws.owner_id != current_user_id:
            raise AppError("Only the workspace owner can create invite links", code="forbidden", status_code=403)

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        invite = await workspace_repository.create_invite(
            db, workspace_id=workspace_id, token=token, created_by=current_user_id, expires_at=expires_at
        )
        return CreateInviteResponse.model_validate(invite)

    async def get_invite_preview(
        self, db: AsyncSession, token: str
    ) -> InvitePreviewResponse:
        invite = await workspace_repository.get_invite_by_token(db, token)
        if not invite:
            raise AppError("Invite not found", code="invite_not_found", status_code=404)

        ws = await workspace_repository.get_workspace(db, invite.workspace_id)
        inviter = await user_repository.get_by_id(db, invite.created_by)

        is_expired = datetime.now(timezone.utc) > invite.expires_at

        return InvitePreviewResponse(
            workspace_name=ws.name if ws else "Workspace",
            inviter_name=inviter.name if inviter else "Team Member",
            expires_at=invite.expires_at,
            is_expired=is_expired,
        )

    async def accept_invite(
        self, db: AsyncSession, token: str, user_id: UUID
    ) -> AcceptInviteResponse:
        invite = await workspace_repository.get_invite_by_token(db, token)
        if not invite:
            raise AppError("Invite not found", code="invite_not_found", status_code=404)

        if datetime.now(timezone.utc) > invite.expires_at:
            raise AppError("Invite has expired", code="invite_expired", status_code=400)

        # Explicitly join as role='member' (never 'owner')
        await workspace_repository.add_workspace_member(db, invite.workspace_id, user_id, role="member")
        return AcceptInviteResponse(workspace_id=invite.workspace_id)

    async def create_channel(
        self, db: AsyncSession, workspace_id: UUID, req: CreateChannelRequest, user_id: UUID
    ) -> ChannelResponse:
        normalized_name = normalize_channel_name(req.name)
        existing = await workspace_repository.get_channel_by_name(db, workspace_id, normalized_name)
        if existing:
            raise AppError("A channel with this name already exists in this workspace", code="channel_exists", status_code=409)

        channel = await workspace_repository.create_channel(
            db, workspace_id=workspace_id, name=normalized_name, description=req.description, created_by=user_id
        )
        return ChannelResponse.model_validate(channel)

    async def list_workspace_channels(
        self, db: AsyncSession, workspace_id: UUID, user_id: UUID | None = None
    ) -> list[ChannelResponse]:
        channels = await workspace_repository.list_workspace_channels(db, workspace_id, user_id=user_id)
        return [ChannelResponse.model_validate(c) for c in channels]

    async def join_channel(
        self, db: AsyncSession, channel_id: UUID, user_id: UUID
    ) -> None:
        channel = await workspace_repository.get_channel(db, channel_id)
        if not channel:
            raise AppError("Channel not found", code="channel_not_found", status_code=404)

        # Ensure user belongs to workspace
        members = await workspace_repository.list_workspace_members(db, channel.workspace_id)
        if not any(m["user_id"] == user_id for m in members):
            raise AppError("Not a member of this workspace", code="forbidden", status_code=403)

        await workspace_repository.add_channel_member(db, channel_id, user_id)

    async def leave_channel(
        self, db: AsyncSession, channel_id: UUID, user_id: UUID
    ) -> None:
        channel = await workspace_repository.get_channel(db, channel_id)
        if not channel:
            raise AppError("Channel not found", code="channel_not_found", status_code=404)

        if channel.name == "general":
            raise AppError("Cannot leave default #general channel", code="cannot_leave_general", status_code=400)

        await workspace_repository.remove_channel_member(db, channel_id, user_id)

    async def list_channel_members(
        self, db: AsyncSession, channel_id: UUID
    ) -> list[ChannelMemberResponse]:
        members = await workspace_repository.list_channel_members(db, channel_id)
        return [
            ChannelMemberResponse(
                user_id=m["user_id"],
                name=m["name"],
                email=m["email"],
                avatar_color=m["avatar_color"],
                joined_at=m["joined_at"],
            )
            for m in members
        ]


workspace_service = WorkspaceService()
