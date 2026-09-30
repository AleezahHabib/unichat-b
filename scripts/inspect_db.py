import asyncio
from sqlalchemy import text
from app.core.database import async_session

async def main():
    async with async_session() as s:
        res = await s.execute(text("SELECT workspace_id, user_id, role FROM workspace_members"))
        rows = res.all()
        print("WORKSPACE_MEMBERS:", rows)
        if rows:
            w_id, u_id, _ = rows[0]
            print("Types:", type(w_id), type(u_id))
            print("Values:", repr(w_id), repr(u_id))

if __name__ == "__main__":
    asyncio.run(main())
