import asyncio
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings, normalize_database_url

async def main():
    url, args = normalize_database_url(settings.DATABASE_URL)
    engine = create_async_engine(url, connect_args=args)
    async with engine.connect() as conn:
        ext = await conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector';"))
        ext_rows = ext.fetchall()
        print("Vector Extension:", ext_rows)
        
        idx = await conn.execute(text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'message_embeddings';"))
        idx_rows = idx.fetchall()
        print("Indexes on message_embeddings:")
        for r in idx_rows:
            print(" -", r[0], ":", r[1])
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
