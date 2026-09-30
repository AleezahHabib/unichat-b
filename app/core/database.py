from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import normalize_database_url, settings


class Base(DeclarativeBase):
    pass


if not settings.DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not configured in backend/.env. "
        "UniChat requires a Neon Postgres connection string."
    )

clean_url, connect_args = normalize_database_url(settings.DATABASE_URL)

engine = create_async_engine(
    clean_url,
    echo=False,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,  # Crucial for Neon serverless idle suspend
    pool_recycle=300,    # Recycle connections older than 5 mins to prevent InterfaceError
    connect_args=connect_args,
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
