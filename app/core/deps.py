from typing import Any
from uuid import UUID
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import decode_access_token


async def get_current_user(
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def require_workspace_member(
    workspace_id: UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    user_id = UUID(current_user["sub"])
    result = await db.execute(
        text(
            "SELECT 1 FROM workspace_members WHERE workspace_id = :ws_id AND user_id = :u_id"
        ),
        {"ws_id": str(workspace_id), "u_id": str(user_id)},
    )
    if not result.scalar():
        raise AppError(
            message="You are not a member of this workspace",
            code="forbidden",
            status_code=403,
        )
    return user_id


async def require_channel_member(
    channel_id: UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    user_id = UUID(current_user["sub"])
    result = await db.execute(
        text(
            "SELECT 1 FROM channel_members WHERE channel_id = :ch_id AND user_id = :u_id"
        ),
        {"ch_id": str(channel_id), "u_id": str(user_id)},
    )
    if not result.scalar():
        raise AppError(
            message="You are not a member of this channel",
            code="forbidden",
            status_code=403,
        )
    return user_id
