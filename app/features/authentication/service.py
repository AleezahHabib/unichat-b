import hashlib
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.features.authentication.models import User
from app.features.authentication.repository import user_repository
from app.features.authentication.schemas import (
    AuthResponse,
    LoginRequest,
    SignupRequest,
    UserResponse,
)

AVATAR_PALETTE = [
    "#2F6BFF",  # Primary Blue
    "#7C5CFF",  # AI Purple
    "#16C79A",  # Live Emerald
    "#FF6B6F",  # Coral Red
    "#F59E0B",  # Amber
    "#EC4899",  # Pink
    "#8B5CF6",  # Violet
    "#06B6D4",  # Cyan
]


def generate_avatar_color(email: str) -> str:
    normalized = email.lower().strip()
    hash_val = int(hashlib.md5(normalized.encode("utf-8")).hexdigest(), 16)
    return AVATAR_PALETTE[hash_val % len(AVATAR_PALETTE)]


class AuthService:
    async def signup(self, db: AsyncSession, req: SignupRequest) -> AuthResponse:
        existing = await user_repository.get_by_email(db, req.email)
        if existing:
            raise AppError(
                message="An account with this email already exists",
                code="email_taken",
                status_code=409,
            )

        hashed_pw = hash_password(req.password)
        avatar_color = generate_avatar_color(req.email)

        user = User(
            name=req.name.strip(),
            email=req.email.lower().strip(),
            password_hash=hashed_pw,
            avatar_color=avatar_color,
        )

        created_user = await user_repository.create_user(db, user)
        token = create_access_token(str(created_user.id))

        return AuthResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse.model_validate(created_user),
        )

    async def login(self, db: AsyncSession, req: LoginRequest) -> AuthResponse:
        user = await user_repository.get_by_email(db, req.email)
        if not user or not verify_password(req.password, user.password_hash):
            raise AppError(
                message="Invalid email or password",
                code="invalid_credentials",
                status_code=401,
            )

        token = create_access_token(str(user.id))
        return AuthResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )

    async def get_profile(self, db: AsyncSession, user_id: UUID) -> UserResponse:
        user = await user_repository.get_by_id(db, user_id)
        if not user:
            raise AppError(
                message="User profile not found",
                code="user_not_found",
                status_code=404,
            )
        return UserResponse.model_validate(user)


auth_service = AuthService()
