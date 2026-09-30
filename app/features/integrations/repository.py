from uuid import UUID
from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.integrations.models import ChannelLink, ConnectedPlatform
from app.features.messaging.models import Message


class IntegrationRepository:
    async def create_platform(
        self,
        db: AsyncSession,
        workspace_id: UUID,
        platform: str,
        encrypted_tokens: str,
        bot_identity: str | None,
        display_name: str,
    ) -> ConnectedPlatform:
        cp = ConnectedPlatform(
            workspace_id=workspace_id,
            platform=platform,
            encrypted_tokens=encrypted_tokens,
            bot_identity=bot_identity,
            display_name=display_name,
        )
        db.add(cp)
        await db.commit()
        await db.refresh(cp)
        return cp

    async def get_platform(self, db: AsyncSession, platform_id: UUID) -> ConnectedPlatform | None:
        stmt = select(ConnectedPlatform).where(ConnectedPlatform.id == platform_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_workspace_platforms(
        self, db: AsyncSession, workspace_id: UUID
    ) -> list[ConnectedPlatform]:
        stmt = select(ConnectedPlatform).where(ConnectedPlatform.workspace_id == workspace_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def delete_platform(self, db: AsyncSession, platform_id: UUID) -> None:
        stmt = delete(ConnectedPlatform).where(ConnectedPlatform.id == platform_id)
        await db.execute(stmt)
        await db.commit()

    async def create_channel_link(
        self,
        db: AsyncSession,
        channel_id: UUID,
        platform_id: UUID,
        platform: str,
        external_channel_id: str,
        external_channel_name: str,
        encrypted_webhook_url: str | None = None,
        webhook_id: str | None = None,
        last_synced_external_id: str | None = None,
    ) -> ChannelLink:
        link = ChannelLink(
            channel_id=channel_id,
            platform_id=platform_id,
            platform=platform,
            external_channel_id=external_channel_id,
            external_channel_name=external_channel_name,
            encrypted_webhook_url=encrypted_webhook_url,
            webhook_id=webhook_id,
            last_synced_external_id=last_synced_external_id,
        )
        db.add(link)
        await db.commit()
        await db.refresh(link)
        return link

    async def get_channel_links(self, db: AsyncSession, channel_id: UUID) -> list[ChannelLink]:
        stmt = select(ChannelLink).where(ChannelLink.channel_id == channel_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_platform_links(self, db: AsyncSession, platform_id: UUID) -> list[ChannelLink]:
        stmt = select(ChannelLink).where(ChannelLink.platform_id == platform_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_workspace_channel_links(
        self, db: AsyncSession, workspace_id: UUID
    ) -> list[ChannelLink]:
        from app.features.workspaces_and_channels.models import Channel
        stmt = (
            select(ChannelLink)
            .join(Channel, Channel.id == ChannelLink.channel_id)
            .where(Channel.workspace_id == workspace_id)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def remove_channel_link(
        self, db: AsyncSession, channel_id: UUID, platform: str
    ) -> None:
        stmt = delete(ChannelLink).where(
            ChannelLink.channel_id == channel_id, ChannelLink.platform == platform
        )
        await db.execute(stmt)
        await db.commit()



    async def get_link_by_external_channel(
        self, db: AsyncSession, platform: str, external_channel_id: str
    ) -> ChannelLink | None:
        stmt = select(ChannelLink).where(
            ChannelLink.platform == platform,
            ChannelLink.external_channel_id == external_channel_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_last_synced_id(
        self, db: AsyncSession, link_id: UUID, last_external_id: str
    ) -> None:
        stmt = select(ChannelLink).where(ChannelLink.id == link_id)
        link = (await db.execute(stmt)).scalar_one_or_none()
        if link:
            link.last_synced_external_id = last_external_id
            await db.commit()

    async def save_external_message(
        self,
        db: AsyncSession,
        channel_id: UUID,
        external_author_name: str,
        body: str,
        source: str,
        external_id: str,
        external_channel_id: str,
        parent_id: UUID | None = None,
    ) -> Message | None:
        """
        Inserts message using ON CONFLICT DO NOTHING to guarantee layer-2 echo prevention backstop.
        """
        query = text(
            """
            INSERT INTO messages (channel_id, external_author_name, body, source, external_id, external_channel_id, parent_id)
            VALUES (:ch_id, :ext_name, :body, :source, :ext_id, :ext_ch_id, :p_id)
            ON CONFLICT (external_channel_id, external_id) WHERE external_id IS NOT NULL DO NOTHING
            RETURNING id;
            """
        )
        result = await db.execute(
            query,
            {
                "ch_id": str(channel_id),
                "ext_name": external_author_name,
                "body": body,
                "source": source,
                "ext_id": external_id,
                "ext_ch_id": external_channel_id,
                "p_id": str(parent_id) if parent_id else None,
            },
        )
        await db.commit()
        row = result.fetchone()
        if not row:
            return None
        
        # Fetch the newly created message
        msg_stmt = select(Message).where(Message.id == row[0])
        return (await db.execute(msg_stmt)).scalar_one_or_none()


integration_repository = IntegrationRepository()
