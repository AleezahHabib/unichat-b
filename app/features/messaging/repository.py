from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import func, select, and_, or_, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.features.authentication.models import User
from app.features.messaging.models import Message, ChannelUserClear


class MessageRepository:
    async def create_message(
        self,
        db: AsyncSession,
        channel_id: UUID,
        author_id: UUID,
        body: str,
        parent_id: UUID | None = None,
    ) -> Message:
        msg = Message(
            channel_id=channel_id,
            author_id=author_id,
            body=body,
            parent_id=parent_id,
            source="unichat",
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg

    async def get_message_by_id(self, db: AsyncSession, message_id: UUID) -> Message | None:
        stmt = select(Message).where(Message.id == message_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_cleared_at(
        self, db: AsyncSession, user_id: UUID, channel_id: UUID
    ) -> datetime | None:
        stmt = select(ChannelUserClear.cleared_at).where(
            ChannelUserClear.user_id == user_id, ChannelUserClear.channel_id == channel_id
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_user_cleared_at(
        self, db: AsyncSession, user_id: UUID, channel_id: UUID
    ) -> datetime:
        now = datetime.now(timezone.utc)
        stmt = (
            insert(ChannelUserClear)
            .values(user_id=user_id, channel_id=channel_id, cleared_at=now)
            .on_conflict_do_update(
                index_elements=["user_id", "channel_id"],
                set_={"cleared_at": now},
            )
        )
        await db.execute(stmt)
        await db.commit()
        return now

    async def get_channel_messages(
        self,
        db: AsyncSession,
        channel_id: UUID,
        limit: int = 50,
        cursor: str | None = None,
        user_id: UUID | None = None,
    ) -> tuple[list[dict], str | None]:
        # Subquery for reply counts and last reply time
        reply_sub = (
            select(
                Message.parent_id,
                func.count(Message.id).label("reply_count"),
                func.max(Message.created_at).label("last_reply_at"),
            )
            .where(Message.parent_id.is_not(None))
            .group_by(Message.parent_id)
            .subquery()
        )

        query = (
            select(
                Message,
                User.name.label("author_name"),
                User.avatar_color.label("author_avatar_color"),
                func.coalesce(reply_sub.c.reply_count, 0).label("reply_count"),
                reply_sub.c.last_reply_at.label("last_reply_at"),
            )
            .outerjoin(User, Message.author_id == User.id)
            .outerjoin(reply_sub, Message.id == reply_sub.c.parent_id)
            .where(Message.channel_id == channel_id, Message.parent_id.is_(None))
        )

        # Per-user clear chat filter
        if user_id:
            cleared_at = await self.get_user_cleared_at(db, user_id, channel_id)
            if cleared_at:
                query = query.where(Message.created_at > cleared_at)

        if cursor:
            # Parse cursor (timestamp_iso|id)
            try:
                parts = cursor.split("|")
                raw_dt = parts[0].replace(" ", "+")
                cursor_dt = datetime.fromisoformat(raw_dt)
                cursor_id = UUID(parts[1]) if len(parts) > 1 else None

                if cursor_id:
                    query = query.where(
                        or_(
                            Message.created_at < cursor_dt,
                            and_(Message.created_at == cursor_dt, Message.id < cursor_id),
                        )
                    )
                else:
                    query = query.where(Message.created_at < cursor_dt)
            except Exception:
                raise AppError("Invalid pagination cursor", code="invalid_cursor", status_code=400)

        query = query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)
        result = await db.execute(query)
        rows = result.all()

        has_more = len(rows) > limit
        items_raw = rows[:limit]

        next_cursor = None
        if has_more and items_raw:
            last_msg = items_raw[-1][0]
            next_cursor = f"{last_msg.created_at.isoformat()}|{last_msg.id}"

        formatted = []
        for row in items_raw:
            msg, author_name, avatar_color, r_count, l_reply = row
            formatted.append({
                "message": msg,
                "author_name": author_name or msg.external_author_name or "Unknown",
                "avatar_color": avatar_color,
                "reply_count": r_count,
                "last_reply_at": l_reply,
            })

        return formatted, next_cursor

    async def get_thread(self, db: AsyncSession, parent_id: UUID) -> tuple[dict | None, list[dict]]:
        parent_raw = await self.get_message_by_id(db, parent_id)
        if not parent_raw:
            return None, []

        parent_author = await db.execute(select(User).where(User.id == parent_raw.author_id))
        p_user = parent_author.scalar_one_or_none()

        p_dict = {
            "message": parent_raw,
            "author_name": p_user.name if p_user else (parent_raw.external_author_name or "Unknown"),
            "avatar_color": p_user.avatar_color if p_user else None,
            "reply_count": 0,
            "last_reply_at": None,
        }

        replies_query = (
            select(Message, User.name.label("author_name"), User.avatar_color.label("author_avatar_color"))
            .outerjoin(User, Message.author_id == User.id)
            .where(Message.parent_id == parent_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        replies_res = await db.execute(replies_query)
        replies_rows = replies_res.all()

        replies_formatted = [
            {
                "message": msg,
                "author_name": a_name or msg.external_author_name or "Unknown",
                "avatar_color": a_color,
                "reply_count": 0,
                "last_reply_at": None,
            }
            for msg, a_name, a_color in replies_rows
        ]

        p_dict["reply_count"] = len(replies_formatted)
        if replies_formatted:
            p_dict["last_reply_at"] = replies_formatted[-1]["message"].created_at

        return p_dict, replies_formatted

    async def update_message(self, db: AsyncSession, message: Message, body: str) -> Message:
        message.body = body
        message.edited_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(message)
        return message

    async def delete_message(self, db: AsyncSession, message: Message) -> Message:
        message.deleted_at = datetime.now(timezone.utc)
        message.body = "This message was deleted"
        await db.commit()
        await db.refresh(message)
        return message


message_repository = MessageRepository()
