from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.ai_assistant.models import AssistantChat, MessageEmbedding
from app.features.authentication.models import User
from app.features.messaging.models import Message
from app.features.workspaces_and_channels.models import Channel, Workspace


class AIAssistantRepository:
    async def create_chat_entry(
        self,
        db: AsyncSession,
        user_id: UUID,
        workspace_id: UUID,
        session_id: str,
        role: str,
        content: str,
        citations: list[dict] | None = None,
    ) -> AssistantChat:
        entry = AssistantChat(
            user_id=user_id,
            workspace_id=workspace_id,
            session_id=session_id,
            role=role,
            content=content,
            citations=citations,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry

    async def get_session_history(
        self, db: AsyncSession, user_id: UUID, workspace_id: UUID, session_id: str
    ) -> list[AssistantChat]:
        stmt = (
            select(AssistantChat)
            .where(
                AssistantChat.user_id == user_id,
                AssistantChat.workspace_id == workspace_id,
                AssistantChat.session_id == session_id,
            )
            .order_by(AssistantChat.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_messages_by_ids(
        self, db: AsyncSession, message_ids: list[UUID]
    ) -> list[dict]:
        if not message_ids:
            return []
        stmt = (
            select(
                Message.id.label("message_id"),
                Message.channel_id,
                Channel.name.label("channel_name"),
                User.name.label("author_name"),
                Message.external_author_name,
                Message.body,
                Message.created_at,
            )
            .join(Channel, Message.channel_id == Channel.id)
            .outerjoin(User, Message.author_id == User.id)
            .where(Message.id.in_(message_ids))
        )
        rows = (await db.execute(stmt)).all()
        return [
            {
                "message_id": r.message_id,
                "channel_id": r.channel_id,
                "channel_name": r.channel_name,
                "author_name": r.author_name or r.external_author_name or "Unknown",
                "body": r.body,
                "created_at": r.created_at,
            }
            for r in rows
        ]

    async def vector_search(
        self,
        db: AsyncSession,
        workspace_id: UUID,
        allowed_channel_ids: set[UUID],
        query_vector: list[float],
        limit: int = 20,
    ) -> list[dict]:
        if not allowed_channel_ids:
            return []

        try:
            distance_col = MessageEmbedding.embedding.cosine_distance(query_vector)
            stmt = (
                select(
                    Message.id.label("message_id"),
                    Message.channel_id,
                    Channel.name.label("channel_name"),
                    User.name.label("author_name"),
                    Message.external_author_name,
                    Message.body,
                    Message.created_at,
                    distance_col.label("distance"),
                )
                .join(MessageEmbedding, Message.id == MessageEmbedding.message_id)
                .join(Channel, Message.channel_id == Channel.id)
                .outerjoin(User, Message.author_id == User.id)
                .where(
                    Channel.workspace_id == workspace_id,
                    Message.channel_id.in_(allowed_channel_ids),
                    Message.deleted_at.is_(None),
                )
                .order_by(distance_col.asc())
                .limit(limit)
            )
            result = await db.execute(stmt)
            rows = result.all()
            return [
                {
                    "message_id": r.message_id,
                    "channel_id": r.channel_id,
                    "channel_name": r.channel_name,
                    "author_name": r.author_name or r.external_author_name or "Unknown",
                    "body": r.body,
                    "created_at": r.created_at,
                    "score": round(1.0 - float(r.distance), 4),
                }
                for r in rows
            ]
        except Exception:
            return []

    async def keyword_search(
        self,
        db: AsyncSession,
        workspace_id: UUID,
        allowed_channel_ids: set[UUID],
        query_str: str,
        limit: int = 20,
    ) -> list[dict]:
        if not allowed_channel_ids:
            return []

        stmt = (
            select(
                Message.id.label("message_id"),
                Message.channel_id,
                Channel.name.label("channel_name"),
                User.name.label("author_name"),
                Message.external_author_name,
                Message.body,
                Message.created_at,
            )
            .join(Channel, Message.channel_id == Channel.id)
            .outerjoin(User, Message.author_id == User.id)
            .where(
                Channel.workspace_id == workspace_id,
                Message.channel_id.in_(allowed_channel_ids),
                Message.deleted_at.is_(None),
                Message.body.ilike(f"%{query_str}%"),
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = result.all()
        return [
            {
                "message_id": r.message_id,
                "channel_id": r.channel_id,
                "channel_name": r.channel_name,
                "author_name": r.author_name or r.external_author_name or "Unknown",
                "body": r.body,
                "created_at": r.created_at,
                "score": 1.0,
            }
            for r in rows
        ]

    async def get_recent_messages(
        self, db: AsyncSession, channel_id: UUID, hours: int = 24
    ) -> list[dict]:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        stmt = (
            select(
                Message.id.label("message_id"),
                Message.channel_id,
                Channel.name.label("channel_name"),
                User.name.label("author_name"),
                Message.external_author_name,
                Message.body,
                Message.created_at,
            )
            .join(Channel, Message.channel_id == Channel.id)
            .outerjoin(User, Message.author_id == User.id)
            .where(
                Message.channel_id == channel_id,
                Message.created_at >= since,
                Message.deleted_at.is_(None),
            )
            .order_by(Message.created_at.asc())
        )
        result = await db.execute(stmt)
        return [
            {
                "message_id": r.message_id,
                "channel_id": r.channel_id,
                "channel_name": r.channel_name,
                "author_name": r.author_name or r.external_author_name or "Unknown",
                "body": r.body,
                "created_at": r.created_at,
            }
            for r in result.all()
        ]


ai_assistant_repository = AIAssistantRepository()
