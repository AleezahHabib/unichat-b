from datetime import datetime, timezone
from typing import Any
from uuid import UUID


def make_envelope(
    event_type: str,
    data: dict[str, Any],
    workspace_id: UUID | str | None = None,
    channel_id: UUID | str | None = None,
) -> dict[str, Any]:
    return {
        "type": event_type,
        "workspace_id": str(workspace_id) if workspace_id else None,
        "channel_id": str(channel_id) if channel_id else None,
        "data": data,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def ready_event(user_id: UUID | str, workspace_ids: list[str]) -> dict[str, Any]:
    return make_envelope(
        "ready",
        {
            "user_id": str(user_id),
            "workspaces": workspace_ids,
        },
    )


def pong_event() -> dict[str, Any]:
    return make_envelope("pong", {})


def message_created_event(
    workspace_id: UUID | str, channel_id: UUID | str, message_data: dict[str, Any]
) -> dict[str, Any]:
    return make_envelope("message.created", message_data, workspace_id, channel_id)


def message_updated_event(
    workspace_id: UUID | str, channel_id: UUID | str, message_id: UUID | str, body: str, edited_at: str
) -> dict[str, Any]:
    return make_envelope(
        "message.updated",
        {
            "id": str(message_id),
            "body": body,
            "edited_at": edited_at,
        },
        workspace_id,
        channel_id,
    )


def message_deleted_event(
    workspace_id: UUID | str, channel_id: UUID | str, message_id: UUID | str
) -> dict[str, Any]:
    return make_envelope(
        "message.deleted",
        {
            "id": str(message_id),
            "is_deleted": True,
        },
        workspace_id,
        channel_id,
    )


def thread_reply_event(
    workspace_id: UUID | str,
    channel_id: UUID | str,
    parent_id: UUID | str,
    reply_data: dict[str, Any],
    reply_count: int,
    last_reply_at: str | None,
) -> dict[str, Any]:
    return make_envelope(
        "thread.reply",
        {
            "parent_id": str(parent_id),
            "reply": reply_data,
            "reply_count": reply_count,
            "last_reply_at": last_reply_at,
        },
        workspace_id,
        channel_id,
    )


def typing_event(
    workspace_id: UUID | str,
    channel_id: UUID | str,
    user_id: UUID | str,
    user_name: str,
) -> dict[str, Any]:
    return make_envelope(
        "typing",
        {
            "user_id": str(user_id),
            "user_name": user_name,
        },
        workspace_id,
        channel_id,
    )


def presence_update_event(
    workspace_id: UUID | str | None, user_id: UUID | str, status: str
) -> dict[str, Any]:
    return make_envelope(
        "presence.update",
        {
            "user_id": str(user_id),
            "status": status,
        },
        workspace_id,
    )


