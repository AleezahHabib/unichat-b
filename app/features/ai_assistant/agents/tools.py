import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID
from agents import RunContextWrapper, function_tool
from sqlalchemy import select

from app.features.ai_assistant.agents.context import AssistantContext
from app.features.ai_assistant.embeddings import embed_query, is_ai_enabled
from app.features.ai_assistant.models import MessageEmbedding
from app.features.authentication.models import User
from app.features.messaging.models import Message
from app.features.workspaces_and_channels.models import Channel

logger = logging.getLogger(__name__)

ACCESS_DENIED_TEXT = "You don't have access to that channel or it doesn't exist."


def format_xml_message(
    msg_id: str, channel_name: str, author_name: str, source: str, created_at: str, body: str
) -> str:
    return (
        f'<message id="{msg_id}" channel="#{channel_name}" author="{author_name}" '
        f'source="{source}" at="{created_at}">{body}</message>'
    )


@function_tool
async def list_channels(wrapper: RunContextWrapper[AssistantContext]) -> str:
    """List all public channels that the user has joined in the current workspace."""
    ctx = wrapper.context
    async with ctx.session_factory() as db:
        stmt = (
            select(Channel)
            .where(
                Channel.workspace_id == ctx.workspace_id,
                Channel.id.in_(ctx.allowed_channel_ids),
            )
            .order_by(Channel.name.asc())
        )
        channels = (await db.execute(stmt)).scalars().all()
        if not channels:
            return "No joined channels found in workspace."
        names = [f"#{c.name}" for c in channels]
        return f"Joined channels: {', '.join(names)}"


@function_tool
async def get_channel_history(
    wrapper: RunContextWrapper[AssistantContext],
    channel_name: str,
    since_hours: int = 24,
    limit: int = 80,
) -> str:
    """Get recent message history for a specific channel by name."""
    ctx = wrapper.context
    clean_name = channel_name.lstrip("#").strip().lower()

    async with ctx.session_factory() as db:
        # Check channel existence and user membership
        stmt = select(Channel).where(
            Channel.workspace_id == ctx.workspace_id,
            Channel.name == clean_name,
        )
        channel = (await db.execute(stmt)).scalar_one_or_none()

        if not channel or channel.id not in ctx.allowed_channel_ids:
            return ACCESS_DENIED_TEXT

        cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, since_hours))

        msg_stmt = (
            select(
                Message,
                User.name.label("user_name"),
            )
            .outerjoin(User, Message.author_id == User.id)
            .where(
                Message.channel_id == channel.id,
                Message.created_at >= cutoff,
                Message.deleted_at.is_(None),
            )
            .order_by(Message.created_at.asc())
            .limit(min(100, max(1, limit)))
        )
        rows = (await db.execute(msg_stmt)).all()

        if not rows:
            return f"No messages found in #{clean_name} within the last {since_hours} hours."

        formatted_list: list[str] = []
        for msg, u_name in rows:
            ctx.seen_message_ids.add(msg.id)
            author = u_name or msg.external_author_name or "Unknown"
            formatted_list.append(
                format_xml_message(
                    msg_id=str(msg.id),
                    channel_name=clean_name,
                    author_name=author,
                    source=msg.source,
                    created_at=msg.created_at.isoformat(),
                    body=msg.body,
                )
            )

        return "\n".join(formatted_list)


@function_tool
async def search_messages(
    wrapper: RunContextWrapper[AssistantContext],
    query: str,
    limit: int = 8,
) -> str:
    """Perform semantic search across workspace messages that the user has access to."""
    ctx = wrapper.context
    if not query or not query.strip():
        return "Search query empty."

    if not ctx.allowed_channel_ids:
        return "No accessible messages found."

    clean_limit = min(20, max(1, limit))

    async with ctx.session_factory() as db:
        results = []
        # Try semantic search if AI is enabled
        query_vec = await embed_query(query) if is_ai_enabled() else None

        if query_vec:
            try:
                distance_col = MessageEmbedding.embedding.cosine_distance(query_vec)
                stmt = (
                    select(Message, Channel.name.label("ch_name"), User.name.label("user_name"))
                    .join(MessageEmbedding, Message.id == MessageEmbedding.message_id)
                    .join(Channel, Message.channel_id == Channel.id)
                    .outerjoin(User, Message.author_id == User.id)
                    .where(
                        Message.channel_id.in_(ctx.allowed_channel_ids),
                        Message.deleted_at.is_(None),
                    )
                    .order_by(distance_col.asc())
                    .limit(clean_limit)
                )
                results = (await db.execute(stmt)).all()
            except Exception as e:
                logger.warning(f"Vector search failed, falling back to ILIKE: {e}")
                results = []

        # ILIKE Fallback if semantic returned nothing
        if not results:
            stmt = (
                select(Message, Channel.name.label("ch_name"), User.name.label("user_name"))
                .join(Channel, Message.channel_id == Channel.id)
                .outerjoin(User, Message.author_id == User.id)
                .where(
                    Message.channel_id.in_(ctx.allowed_channel_ids),
                    Message.deleted_at.is_(None),
                    Message.body.ilike(f"%{query}%"),
                )
                .order_by(Message.created_at.desc())
                .limit(clean_limit)
            )
            results = (await db.execute(stmt)).all()

        if not results:
            return f"No messages matching '{query}' were found in your joined channels."

        formatted_list: list[str] = []
        for msg, ch_name, u_name in results:
            ctx.seen_message_ids.add(msg.id)
            author = u_name or msg.external_author_name or "Unknown"
            formatted_list.append(
                format_xml_message(
                    msg_id=str(msg.id),
                    channel_name=ch_name,
                    author_name=author,
                    source=msg.source,
                    created_at=msg.created_at.isoformat(),
                    body=msg.body,
                )
            )

        return "\n".join(formatted_list)


@function_tool
async def get_thread(
    wrapper: RunContextWrapper[AssistantContext],
    message_id: str,
) -> str:
    """Retrieve full discussion thread for a specific message ID."""
    ctx = wrapper.context
    try:
        msg_uuid = UUID(message_id)
    except Exception:
        return "Invalid message ID format."

    async with ctx.session_factory() as db:
        # Fetch parent
        parent_stmt = (
            select(Message, Channel.name.label("ch_name"), User.name.label("user_name"))
            .join(Channel, Message.channel_id == Channel.id)
            .outerjoin(User, Message.author_id == User.id)
            .where(Message.id == msg_uuid, Message.deleted_at.is_(None))
        )
        p_row = (await db.execute(parent_stmt)).first()
        if not p_row:
            return ACCESS_DENIED_TEXT

        p_msg, ch_name, p_uname = p_row

        if p_msg.channel_id not in ctx.allowed_channel_ids:
            return ACCESS_DENIED_TEXT

        # Fetch replies
        replies_stmt = (
            select(Message, User.name.label("user_name"))
            .outerjoin(User, Message.author_id == User.id)
            .where(Message.parent_id == msg_uuid, Message.deleted_at.is_(None))
            .order_by(Message.created_at.asc())
        )
        r_rows = (await db.execute(replies_stmt)).all()

        formatted_list: list[str] = []
        ctx.seen_message_ids.add(p_msg.id)
        p_author = p_uname or p_msg.external_author_name or "Unknown"
        formatted_list.append(
            format_xml_message(
                msg_id=str(p_msg.id),
                channel_name=ch_name,
                author_name=p_author,
                source=p_msg.source,
                created_at=p_msg.created_at.isoformat(),
                body=p_msg.body,
            )
        )

        for r_msg, r_uname in r_rows:
            ctx.seen_message_ids.add(r_msg.id)
            r_author = r_uname or r_msg.external_author_name or "Unknown"
            formatted_list.append(
                format_xml_message(
                    msg_id=str(r_msg.id),
                    channel_name=ch_name,
                    author_name=r_author,
                    source=r_msg.source,
                    created_at=r_msg.created_at.isoformat(),
                    body=r_msg.body,
                )
            )

        return "\n".join(formatted_list)
