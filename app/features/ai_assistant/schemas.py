from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class Citation(BaseModel):
    message_id: UUID
    author_name: str
    channel_name: str
    created_at: datetime
    snippet: str


class AssistantChatRequest(BaseModel):
    workspace_id: UUID
    session_id: str = Field(..., min_length=1, max_length=64)
    message: str = Field(..., min_length=1, max_length=4000)


class AssistantChatResponse(BaseModel):
    id: UUID
    session_id: str
    role: str
    content: str
    citations: list[Citation] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class SummarizeRequest(BaseModel):
    channel_id: UUID
    since_hours: int = Field(24, ge=1, le=168)


class SummarizeResponse(BaseModel):
    summary: str
    key_decisions: list[str] = []
    action_items: list[str] = []
    message_count: int


class DraftReplyRequest(BaseModel):
    message_id: UUID


class DraftReplyResponse(BaseModel):
    draft: str


class SearchResult(BaseModel):
    message_id: UUID
    channel_id: UUID
    channel_name: str
    author_name: str
    body: str
    created_at: datetime
    score: float = 1.0
    is_semantic: bool = False
