from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_workspace_member
from app.core.redis import get_redis
from app.features.ai_assistant.schemas import (
    AssistantChatRequest,
    AssistantChatResponse,
    DraftReplyRequest,
    DraftReplyResponse,
    SearchResult,
    SummarizeRequest,
    SummarizeResponse,
)
from app.features.ai_assistant.service import ai_assistant_service

router = APIRouter(tags=["ai_assistant"])


@router.post(
    "/assistant/chat",
    response_model=AssistantChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat with Gemini AI assistant",
)
async def chat_with_assistant(
    req: AssistantChatRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AssistantChatResponse:
    user_id = UUID(current_user["sub"])
    return await ai_assistant_service.chat(db, redis, user_id, req)


@router.get(
    "/assistant/history",
    response_model=list[AssistantChatResponse],
    summary="Get assistant chat session history",
)
async def get_assistant_history(
    workspace_id: UUID = Query(...),
    session_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
    _: UUID = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
) -> list[AssistantChatResponse]:
    user_id = UUID(current_user["sub"])
    return await ai_assistant_service.get_history(db, user_id, workspace_id, session_id)


@router.post(
    "/assistant/summarize",
    response_model=SummarizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Summarize recent channel messages",
)
async def summarize_channel(
    req: SummarizeRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> SummarizeResponse:
    user_id = UUID(current_user["sub"])
    return await ai_assistant_service.summarize(db, redis, user_id, req)


@router.post(
    "/assistant/draft-reply",
    response_model=DraftReplyResponse,
    status_code=status.HTTP_200_OK,
    summary="Draft an AI response to a message",
)
async def draft_reply(
    req: DraftReplyRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> DraftReplyResponse:
    user_id = UUID(current_user["sub"])
    return await ai_assistant_service.draft_reply(db, redis, user_id, req)


@router.get(
    "/search",
    response_model=list[SearchResult],
    summary="Semantic vector search across workspace messages",
)
async def search_messages(
    workspace_id: UUID = Query(...),
    q: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    _: UUID = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
) -> list[SearchResult]:
    user_id = UUID(current_user["sub"])
    return await ai_assistant_service.search(db, user_id, workspace_id, q, limit=limit)
