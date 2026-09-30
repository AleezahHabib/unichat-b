from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.features.authentication.schemas import (
    AuthResponse,
    LoginRequest,
    SignupRequest,
    UserResponse,
)
from app.features.authentication.service import auth_service

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Sign up a new user",
)
async def signup(
    req: SignupRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    return await auth_service.signup(db, req)


@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Log in user",
)
async def login(
    req: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    return await auth_service.login(db, req)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
)
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user_id = UUID(current_user["sub"])
    return await auth_service.get_profile(db, user_id)
