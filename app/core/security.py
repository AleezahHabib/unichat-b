from datetime import datetime, timedelta, timezone
from typing import Any
import bcrypt
from cryptography.fernet import Fernet
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(
    subject: str | dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRES_MINUTES)

    to_encode: dict[str, Any] = {
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    if isinstance(subject, dict):
        to_encode.update(subject)
    else:
        to_encode["sub"] = str(subject)

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.PyJWTError:
        return {}


def get_fernet() -> Fernet:
    if not settings.ENCRYPTION_KEY:
        # Fallback to a deterministic key for dev/testing if not set yet
        return Fernet(b"t9kS7V9g2wz0jLq7xV1y4m8n3p5r7t9kS7V9g2wz0jL=")
    key = settings.ENCRYPTION_KEY.encode("utf-8")
    return Fernet(key)


def encrypt_secret(plain_text: str) -> str:
    if not plain_text:
        return ""
    fernet = get_fernet()
    return fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: str) -> str:
    if not cipher_text:
        return ""
    fernet = get_fernet()
    return fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
