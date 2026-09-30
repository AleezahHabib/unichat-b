from collections.abc import AsyncGenerator
from pathlib import Path
import fakeredis.aioredis
import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import normalize_database_url, settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def assert_test_database_url_safety():
    """
    CRITICAL SAFETY CHECK:
    Ensure TEST_DATABASE_URL ends with _test to prevent wiping real databases!
    """
    test_url = settings.TEST_DATABASE_URL
    if not test_url:
        pytest.fail(
            "TEST_DATABASE_URL environment variable is not set. "
            "UniChat tests require a Neon Postgres test database connection string ending in '_test'."
        )

    # Strip query parameters before checking database name
    base_url = test_url.split("?")[0]
    db_name = base_url.rsplit("/", 1)[-1]
    if not db_name.endswith("_test"):
        pytest.fail(
            f"SAFETY CHECK FAILED: TEST_DATABASE_URL database name '{db_name}' "
            "does not end with '_test'. The test suite refuses to run against production data!"
        )


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """
    Drops and recreates test DB tables / schema using migration scripts.
    """
    test_url = settings.TEST_DATABASE_URL
    if not test_url:
        pytest.fail("TEST_DATABASE_URL environment variable is not set.")

    clean_url, connect_args = normalize_database_url(test_url)
    engine = create_async_engine(clean_url, connect_args=connect_args)

    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE;"))
        await conn.execute(text("CREATE SCHEMA public;"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))

        # Re-apply migrations
        migrations_dir = Path(__file__).resolve().parent.parent / "db" / "migrations"
        sql_files = sorted(migrations_dir.glob("*.sql"))

        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        )

        for sql_file in sql_files:
            content = sql_file.read_text(encoding="utf-8")
            statements = [s.strip() for s in content.split(";") if s.strip()]
            for stmt in statements:
                await conn.execute(text(stmt))
            await conn.execute(
                text("INSERT INTO schema_migrations (filename) VALUES (:fname);"),
                {"fname": sql_file.name},
            )

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    test_url = settings.TEST_DATABASE_URL
    if not test_url:
        pytest.fail("TEST_DATABASE_URL environment variable is not set.")

    clean_url, connect_args = normalize_database_url(test_url)
    engine = create_async_engine(clean_url, connect_args=connect_args)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def fake_redis():
    server = fakeredis.FakeServer()
    client = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def client(fake_redis, db_session) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_get_db():
        yield db_session

    async def override_get_redis():
        yield fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def websocket_client():
    from starlette.testclient import TestClient
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    import fakeredis.aioredis

    clean_url, connect_args = normalize_database_url(settings.TEST_DATABASE_URL)
    test_engine = create_async_engine(clean_url, connect_args=connect_args)
    test_session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    fake_server = fakeredis.FakeServer()

    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    async def override_get_redis():
        r = fakeredis.aioredis.FakeRedis(server=fake_server, decode_responses=True)
        try:
            yield r
        finally:
            await r.aclose()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    with TestClient(app) as tc:
        yield tc

    app.dependency_overrides.clear()

