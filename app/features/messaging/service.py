from datetime import datetime
from uuid import UUID
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.background.embed_worker import enqueue_message_embedding
from app.core.errors import AppError
from app.core.rate_limit import check_rate_limit
from app.features.authentication.repository import user_repository
from app.features.messaging.models import Message
from app.features.messaging.repository import message_repository
from app.features.messaging.schemas import (
    CreateMessageRequest,
    MessageAuthor,
    MessageResponse,
    MessagesPageResponse,
    ThreadResponse,
    UpdateMessageRequest,
)
from app.features.realtime.events import (
    message_created_event,
    message_deleted_event,
    message_updated_event,
    thread_reply_event,
)
from app.features.realtime.pubsub import publish_event
from app.features.workspaces_and_channels.repository import workspace_repository



def format_message_response(item: dict) -> MessageResponse:
    msg: Message = item["message"]
    is_deleted = msg.deleted_at is not None
    return MessageResponse(
        id=msg.id,
        channel_id=msg.channel_id,
        author=MessageAuthor(
            id=msg.author_id,
            name=item["author_name"],
            avatar_color=item["avatar_color"],
            is_external=msg.source != "unichat",
        ),
        body=msg.body if not is_deleted else "This message was deleted",
        source=msg.source,
        parent_id=msg.parent_id,
        external_id=msg.external_id,
        external_channel_id=msg.external_channel_id,
        created_at=msg.created_at,
        edited_at=msg.edited_at,
        is_deleted=is_deleted,
        reply_count=item.get("reply_count", 0),
        last_reply_at=item.get("last_reply_at"),
    )


class MessageService:
    async def create_message(
        self,
        db: AsyncSession,
        redis: Redis,
        channel_id: UUID,
        author_id: UUID,
        req: CreateMessageRequest,
    ) -> MessageResponse:
        # Rate limit check: 30 msgs / min
        allowed, retry_after = await check_rate_limit(
            redis, key=f"rate_limit:msg:{author_id}", limit=30, window_seconds=60
        )
        if not allowed:
            raise AppError(
                message=f"Rate limit exceeded. Try again in {retry_after}s",
                code="rate_limited",
                status_code=429,
            )

        body = req.body.strip()
        if not body or len(body) > 4000:
            raise AppError("Message body must be between 1 and 4000 characters", code="invalid_body", status_code=400)

        if req.parent_id:
            parent = await message_repository.get_message_by_id(db, req.parent_id)
            if not parent:
                raise AppError("Parent message not found", code="parent_not_found", status_code=404)

        msg = await message_repository.create_message(
            db, channel_id=channel_id, author_id=author_id, body=body, parent_id=req.parent_id
        )

        user = await user_repository.get_by_id(db, author_id)
        item = {
            "message": msg,
            "author_name": user.name if user else "Unknown",
            "avatar_color": user.avatar_color if user else None,
            "reply_count": 0,
            "last_reply_at": None,
        }
        resp = format_message_response(item)

        # Look up workspace_id for realtime event publishing
        ch = await workspace_repository.get_channel(db, channel_id)
        if ch and redis:
            ws_id = str(ch.workspace_id)
            if req.parent_id:
                # Thread reply event
                p_item, replies = await message_repository.get_thread(db, req.parent_id)
                evt = thread_reply_event(
                    workspace_id=ws_id,
                    channel_id=channel_id,
                    parent_id=req.parent_id,
                    reply_data=resp.model_dump(mode="json"),
                    reply_count=p_item["reply_count"] if p_item else 1,
                    last_reply_at=p_item["last_reply_at"].isoformat() if p_item and p_item.get("last_reply_at") else msg.created_at.isoformat(),
                )
            else:
                # Top-level message created event
                evt = message_created_event(ws_id, channel_id, resp.model_dump(mode="json"))
            await publish_event(redis, ws_id, evt)

            # Relay outbound to linked external platforms (Slack, Discord)
            from app.features.integrations.service import integration_service
            author_name_relay = user.name if user else "Unknown"
            await integration_service.relay_outbound(db, redis, msg, author_name_relay)

        # Enqueue embedding for AI vector search
        ch_name = ch.name if ch else "general"
        author_name = user.name if user else "Unknown"
        enqueue_message_embedding(msg.id, ch_name, author_name, body)

        return resp

    async def get_channel_messages(
        self,
        db: AsyncSession,
        channel_id: UUID,
        limit: int = 50,
        cursor: str | None = None,
    ) -> MessagesPageResponse:
        items_raw, next_cursor = await message_repository.get_channel_messages(
            db, channel_id=channel_id, limit=limit, cursor=cursor
        )
        items = [format_message_response(item) for item in items_raw]
        return MessagesPageResponse(items=items, next_cursor=next_cursor)

    async def get_thread(self, db: AsyncSession, message_id: UUID) -> ThreadResponse:
        p_item, replies_raw = await message_repository.get_thread(db, message_id)
        if not p_item:
            raise AppError("Message not found", code="message_not_found", status_code=404)

        parent = format_message_response(p_item)
        replies = [format_message_response(r) for r in replies_raw]
        return ThreadResponse(parent=parent, replies=replies)

    async def update_message(
        self,
        db: AsyncSession,
        redis: Redis,
        message_id: UUID,
        author_id: UUID,
        req: UpdateMessageRequest,
    ) -> MessageResponse:
        msg = await message_repository.get_message_by_id(db, message_id)
        if not msg or msg.deleted_at is not None:
            raise AppError("Message not found", code="message_not_found", status_code=404)

        if msg.author_id != author_id or msg.source != "unichat":
            raise AppError("Only the original author can edit this message", code="forbidden", status_code=403)

        body = req.body.strip()
        if not body or len(body) > 4000:
            raise AppError("Message body must be between 1 and 4000 characters", code="invalid_body", status_code=400)

        updated_msg = await message_repository.update_message(db, msg, body)
        user = await user_repository.get_by_id(db, author_id)
        item = {
            "message": updated_msg,
            "author_name": user.name if user else "Unknown",
            "avatar_color": user.avatar_color if user else None,
        }
        resp = format_message_response(item)

        ch = await workspace_repository.get_channel(db, msg.channel_id)
        if ch and redis:
            evt = message_updated_event(
                workspace_id=str(ch.workspace_id),
                channel_id=str(msg.channel_id),
                message_id=str(msg.id),
                body=resp.body,
                edited_at=resp.edited_at.isoformat() if resp.edited_at else datetime.now().isoformat(),
            )
            await publish_event(redis, str(ch.workspace_id), evt)

        return resp

    async def delete_message(
        self, db: AsyncSession, redis: Redis, message_id: UUID, author_id: UUID
    ) -> MessageResponse:
        msg = await message_repository.get_message_by_id(db, message_id)
        if not msg:
            raise AppError("Message not found", code="message_not_found", status_code=404)

        # Check permissions: original author or workspace owner
        ch = await workspace_repository.get_channel(db, msg.channel_id)
        is_author = msg.author_id == author_id and msg.source == "unichat"
        is_owner = False
        if ch:
            ws = await workspace_repository.get_workspace(db, ch.workspace_id)
            if ws and ws.owner_id == author_id:
                is_owner = True

        if not is_author and not is_owner:
            raise AppError("Only the original author or workspace owner can delete this message", code="forbidden", status_code=403)

        deleted_msg = await message_repository.delete_message(db, msg)
        user = await user_repository.get_by_id(db, author_id)
        item = {
            "message": deleted_msg,
            "author_name": user.name if user else "Unknown",
            "avatar_color": user.avatar_color if user else None,
        }
        resp = format_message_response(item)

        if ch and redis:
            evt = message_deleted_event(
                workspace_id=str(ch.workspace_id),
                channel_id=str(msg.channel_id),
                message_id=str(msg.id),
            )
            await publish_event(redis, str(ch.workspace_id), evt)

        return resp


message_service = MessageService()


