import argparse
import asyncio
from pathlib import Path
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import normalize_database_url, settings


async def run_migrations(test_mode: bool = False) -> int:
    target_url = settings.TEST_DATABASE_URL if test_mode else settings.DATABASE_URL
    if not target_url:
        print(f"Error: {'TEST_DATABASE_URL' if test_mode else 'DATABASE_URL'} is not set in environment.", file=sys.stderr)
        return 1

    clean_url, connect_args = normalize_database_url(target_url)
    engine = create_async_engine(clean_url, connect_args=connect_args)

    migrations_dir = Path(__file__).resolve().parent.parent / "db" / "migrations"
    if not migrations_dir.exists():
        print(f"Error: Migrations directory not found: {migrations_dir}", file=sys.stderr)
        return 1

    sql_files = sorted(migrations_dir.glob("*.sql"))

    applied_count = 0
    async with engine.begin() as conn:
        # Create schema_migrations tracker table if not exists
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

        # Get list of already applied migrations
        result = await conn.execute(text("SELECT filename FROM schema_migrations;"))
        applied_files = {row[0] for row in result.fetchall()}

        for sql_file in sql_files:
            if sql_file.name in applied_files:
                continue

            content = sql_file.read_text(encoding="utf-8")
            # Split into individual SQL statements to avoid asyncpg multi-statement error
            statements = [s.strip() for s in content.split(";") if s.strip()]
            for stmt in statements:
                await conn.execute(text(stmt))
            await conn.execute(
                text("INSERT INTO schema_migrations (filename) VALUES (:fname);"),
                {"fname": sql_file.name},
            )
            print(f"Applied: {sql_file.name}")
            applied_count += 1

    await engine.dispose()
    print(f"Migrations finished: {applied_count} applied.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="UniChat SQL Migration Runner")
    parser.add_argument("--test", action="store_true", help="Run migrations against TEST_DATABASE_URL")
    args = parser.parse_args()

    exit_code = asyncio.run(run_migrations(test_mode=args.test))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
