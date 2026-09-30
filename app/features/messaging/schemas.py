from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class CreateMessageRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)
    parent_id: UUID | None = None


class UpdateMessageRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


class MessageAuthor(BaseModel):
    id: UUID | None = None
    name: str
    avatar_color: str | None = None
    is_external: bool = False


class MessageResponse(BaseModel):
    id: UUID
    channel_id: UUID
    author: MessageAuthor
    body: str
    source: str
    parent_id: UUID | None = None
    external_id: str | None = None
    external_channel_id: str | None = None
    created_at: datetime
    edited_at: datetime | None = None
    is_deleted: bool = False
    reply_count: int = 0
    last_reply_at: datetime | None = None


class MessagesPageResponse(BaseModel):
    items: list[MessageResponse]
    next_cursor: str | None = None


class ThreadResponse(BaseModel):
    parent: MessageResponse
    replies: list[MessageResponse]
