import asyncio
import asyncpg
import os
import json
from dotenv import load_dotenv

load_dotenv('backend/.env')

async def main():
    db_url = os.getenv('DATABASE_URL').replace('postgresql+asyncpg://', 'postgresql://')
    test_db_url = os.getenv('TEST_DATABASE_URL').replace('postgresql+asyncpg://', 'postgresql://')
    
    print('=== MAIN DB schema_migrations ===')
    conn = await asyncpg.connect(db_url)
    rows = await conn.fetch('SELECT version, applied_at FROM schema_migrations ORDER BY version')
    for r in rows:
        print(f"{r['version']} | {r['applied_at']}")
    
    print('\n=== MAIN DB channel_links rows ===')
    links = await conn.fetch('''
        SELECT cl.id, c.name as channel_name, cl.platform, cl.external_channel_id, cl.external_channel_name 
        FROM channel_links cl 
        JOIN channels c ON cl.channel_id = c.id
    ''')
    for l in links:
        print(dict(l))
    await conn.close()

    print('\n=== TEST DB schema_migrations ===')
    test_conn = await asyncpg.connect(test_db_url)
    t_rows = await test_conn.fetch('SELECT version, applied_at FROM schema_migrations ORDER BY version')
    for r in t_rows:
        print(f"{r['version']} | {r['applied_at']}")
    await test_conn.close()

if __name__ == '__main__':
    asyncio.run(main())
