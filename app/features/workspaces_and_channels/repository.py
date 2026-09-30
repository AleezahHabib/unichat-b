from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.authentication.models import User
from app.features.workspaces_and_channels.models import (
    Channel,
    ChannelMember,
    Workspace,
    WorkspaceInvite,
    WorkspaceMember,
)


class WorkspaceRepository:
    async def create_workspace(self, db: AsyncSession, name: str, owner_id: UUID) -> Workspace:
        ws = Workspace(name=name, owner_id=owner_id)
        db.add(ws)
        await db.flush()

        # Add owner to workspace_members
        ws_member = WorkspaceMember(workspace_id=ws.id, user_id=owner_id, role="owner")
        db.add(ws_member)

        # Create default #general channel
        channel = Channel(workspace_id=ws.id, name="general", description="General discussion", created_by=owner_id)
        db.add(channel)
        await db.flush()

        # Add owner to #general channel_members
        ch_member = ChannelMember(channel_id=channel.id, user_id=owner_id)
        db.add(ch_member)

        await db.commit()
        await db.refresh(ws)
        return ws

    async def list_user_workspaces(self, db: AsyncSession, user_id: UUID) -> list[dict]:
        stmt = (
            select(
                Workspace.id,
                Workspace.name,
                Workspace.owner_id,
                Workspace.created_at,
                func.count(WorkspaceMember.user_id).label("member_count"),
            )
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(
                Workspace.id.in_(
                    select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user_id)
                )
            )
            .group_by(Workspace.id, Workspace.name, Workspace.owner_id, Workspace.created_at)
            .order_by(Workspace.created_at.asc())
        )
        result = await db.execute(stmt)
        return [dict(r._mapping) for r in result.all()]

    async def get_workspace(self, db: AsyncSession, workspace_id: UUID) -> Workspace | None:
        stmt = select(Workspace).where(Workspace.id == workspace_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_workspace(self, db: AsyncSession, workspace_id: UUID) -> None:
        ws = await self.get_workspace(db, workspace_id)
        if ws:
            await db.delete(ws)
            await db.commit()

    async def list_workspace_members(self, db: AsyncSession, workspace_id: UUID) -> list[dict]:
        stmt = (
            select(
                User.id.label("user_id"),
                User.name,
                User.email,
                User.avatar_color,
                WorkspaceMember.role,
                WorkspaceMember.joined_at,
            )
            .join(WorkspaceMember, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.joined_at.asc())
        )
        result = await db.execute(stmt)
        return [dict(r._mapping) for r in result.all()]

    async def create_invite(
        self, db: AsyncSession, workspace_id: UUID, token: str, created_by: UUID, expires_at: datetime
    ) -> WorkspaceInvite:
        invite = WorkspaceInvite(
            workspace_id=workspace_id,
            token=token,
            created_by=created_by,
            expires_at=expires_at,
        )
        db.add(invite)
        await db.commit()
        await db.refresh(invite)
        return invite

    async def get_invite_by_token(self, db: AsyncSession, token: str) -> WorkspaceInvite | None:
        stmt = select(WorkspaceInvite).where(WorkspaceInvite.token == token)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def add_workspace_member(
        self, db: AsyncSession, workspace_id: UUID, user_id: UUID, role: str = "member"
    ) -> None:
        # Check if already member
        check_stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        existing = (await db.execute(check_stmt)).scalar_one_or_none()
        if not existing:
            member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role)
            db.add(member)
        else:
            # Preserve owner role if owner, otherwise set specified role
            if existing.role != "owner":
                existing.role = role

        # Also add to default #general channel
        gen_stmt = select(Channel).where(
            Channel.workspace_id == workspace_id, Channel.name == "general"
        )
        gen_channel = (await db.execute(gen_stmt)).scalar_one_or_none()
        if gen_channel:
            ch_check = select(ChannelMember).where(
                ChannelMember.channel_id == gen_channel.id,
                ChannelMember.user_id == user_id,
            )
            existing_ch = (await db.execute(ch_check)).scalar_one_or_none()
            if not existing_ch:
                db.add(ChannelMember(channel_id=gen_channel.id, user_id=user_id))

        await db.commit()

    async def create_channel(
        self, db: AsyncSession, workspace_id: UUID, name: str, description: str | None, created_by: UUID
    ) -> Channel:
        channel = Channel(
            workspace_id=workspace_id,
            name=name,
            description=description,
            created_by=created_by,
        )
        db.add(channel)
        await db.flush()

        # Add creator to channel_members
        db.add(ChannelMember(channel_id=channel.id, user_id=created_by))

        await db.commit()
        await db.refresh(channel)
        return channel

    async def get_channel_by_name(
        self, db: AsyncSession, workspace_id: UUID, name: str
    ) -> Channel | None:
        stmt = select(Channel).where(
            Channel.workspace_id == workspace_id, Channel.name == name
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_channel(self, db: AsyncSession, channel_id: UUID) -> Channel | None:
        stmt = select(Channel).where(Channel.id == channel_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_workspace_channels(
        self, db: AsyncSession, workspace_id: UUID
    ) -> list[Channel]:
        stmt = select(Channel).where(Channel.workspace_id == workspace_id).order_by(Channel.created_at.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def add_channel_member(
        self, db: AsyncSession, channel_id: UUID, user_id: UUID
    ) -> None:
        check = select(ChannelMember).where(
            ChannelMember.channel_id == channel_id, ChannelMember.user_id == user_id
        )
        existing = (await db.execute(check)).scalar_one_or_none()
        if not existing:
            db.add(ChannelMember(channel_id=channel_id, user_id=user_id))
            await db.commit()

    async def remove_channel_member(
        self, db: AsyncSession, channel_id: UUID, user_id: UUID
    ) -> None:
        stmt = select(ChannelMember).where(
            ChannelMember.channel_id == channel_id, ChannelMember.user_id == user_id
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            await db.delete(existing)
            await db.commit()

    async def list_channel_members(
        self, db: AsyncSession, channel_id: UUID
    ) -> list[dict]:
        stmt = (
            select(
                User.id.label("user_id"),
                User.name,
                User.email,
                User.avatar_color,
                ChannelMember.joined_at,
            )
            .join(ChannelMember, User.id == ChannelMember.user_id)
            .where(ChannelMember.channel_id == channel_id)
            .order_by(ChannelMember.joined_at.asc())
        )
        result = await db.execute(stmt)
        return [dict(r._mapping) for r in result.all()]


workspace_repository = WorkspaceRepository()
