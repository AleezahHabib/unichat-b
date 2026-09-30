from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_channel_member
from app.core.redis import get_redis
from app.features.messaging.schemas import (
    CreateMessageRequest,
    MessageResponse,
    MessagesPageResponse,
    ThreadResponse,
    UpdateMessageRequest,
)
from app.features.messaging.service import message_service

router = APIRouter(tags=["messaging"])


@router.get(
    "/channels/{channel_id}/messages",
    response_model=MessagesPageResponse,
    summary="List messages in a channel (cursor pagination)",
)
async def get_channel_messages(
    channel_id: UUID,
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    _: UUID = Depends(require_channel_member),
    db: AsyncSession = Depends(get_db),
) -> MessagesPageResponse:
    return await message_service.get_channel_messages(
        db, channel_id=channel_id, limit=limit, cursor=cursor
    )


@router.post(
    "/channels/{channel_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Post a message to a channel",
)
async def create_message(
    channel_id: UUID,
    req: CreateMessageRequest,
    current_user: dict = Depends(get_current_user),
    _: UUID = Depends(require_channel_member),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> MessageResponse:
    user_id = UUID(current_user["sub"])
    return await message_service.create_message(
        db, redis, channel_id=channel_id, author_id=user_id, req=req
    )


@router.get(
    "/messages/{message_id}/thread",
    response_model=ThreadResponse,
    summary="Get thread replies for a message",
)
async def get_thread(
    message_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadResponse:
    return await message_service.get_thread(db, message_id)


@router.patch(
    "/messages/{message_id}",
    response_model=MessageResponse,
    summary="Edit a message",
)
async def update_message(
    message_id: UUID,
    req: UpdateMessageRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> MessageResponse:
    user_id = UUID(current_user["sub"])
    return await message_service.update_message(
        db, redis, message_id=message_id, author_id=user_id, req=req
    )


@router.delete(
    "/messages/{message_id}",
    response_model=MessageResponse,
    summary="Soft delete a message",
)
async def delete_message(
    message_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> MessageResponse:
    user_id = UUID(current_user["sub"])
    return await message_service.delete_message(
        db, redis, message_id=message_id, author_id=user_id
    )


