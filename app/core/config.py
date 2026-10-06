from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from typing import Any
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> tuple[str, dict[str, Any]]:
    """
    Normalizes database URLs:
    - Converts postgres:// or postgresql:// to postgresql+asyncpg://
    - Strips sslmode and channel_binding query params (asyncpg rejects these in query string)
    - Returns (clean_url, connect_args) where connect_args has ssl="require" if host is not localhost/127.0.0.1
    """
    if not url:
        return "", {}

    parsed = urlparse(url)
    scheme = parsed.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"

    query_params = parse_qsl(parsed.query)
    clean_params = [
        (k, v)
        for k, v in query_params
        if k.lower() not in ("sslmode", "channel_binding")
    ]
    new_query = urlencode(clean_params)

    clean_parsed = parsed._replace(scheme=scheme, query=new_query)
    clean_url = urlunparse(clean_parsed)

    connect_args: dict[str, Any] = {}
    hostname = (parsed.hostname or "").lower()
    if hostname not in ("localhost", "127.0.0.1", ""):
        connect_args["ssl"] = "require"

    return clean_url, connect_args


class Settings(BaseSettings):
    DATABASE_URL: str = ""
    TEST_DATABASE_URL: str = ""
    REDIS_URL: str = ""
    JWT_SECRET: str = "default-insecure-dev-jwt-secret-replace-in-env"
    JWT_EXPIRES_MINUTES: int = 10080
    ENCRYPTION_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    CHAT_MODEL: str = "gemini-2.5-flash"
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIM: int = 768
    AI_REQUESTS_PER_MINUTE: int = 8
    FRONTEND_URL: str = "http://localhost:3000"
    ENABLE_BACKGROUND: bool = True
    DISCORD_POLL_SECONDS: int = 3
    LOG_LEVEL: str = "INFO"
    SLACK_CLIENT_ID: str = ""
    SLACK_CLIENT_SECRET: str = ""
    SLACK_REDIRECT_URI: str = "http://localhost:8000/integrations/slack/oauth/callback"
    SLACK_APP_TOKEN: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
