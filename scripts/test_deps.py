import asyncio
from uuid import UUID
from app.core.database import async_session
from app.core.deps import require_workspace_member

async def main():
    ws_id = UUID("ec495e48-5ab6-4750-aa65-9d785f71a458")
    user_payload = {"sub": "91fefb29-7fa5-4f22-b11f-c1e7ce1764c9"}
    async with async_session() as s:
        res = await require_workspace_member(ws_id, user_payload, s)
        print("MEMBER CHECK RESULT:", res)

if __name__ == "__main__":
    asyncio.run(main())
