import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings

# Configure logging so application and integration logs are visible in uvicorn / console
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)
logger = logging.getLogger("unichat")
from app.core.database import engine
from app.core.errors import AppError, app_error_handler
from app.core.redis import get_redis_client
from app.core.leader import start_leader_election, stop_leader_election
from app.background.sync_external import get_background_status, sync_external_loop
from app.background.embed_worker import embed_worker_loop, embedding_sweep_loop
from app.features.ai_assistant.routes import router as ai_assistant_router
from app.features.authentication.routes import router as auth_router
from app.features.integrations.routes import router as integrations_router
from app.features.messaging.routes import router as messaging_router
from app.features.realtime.routes import router as realtime_router
from app.features.realtime.pubsub import start_pubsub_subscriber
from app.features.workspaces_and_channels.routes import router as workspaces_and_channels_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = get_redis_client()
    leader_task = start_leader_election(redis)
    pubsub_task = asyncio.create_task(start_pubsub_subscriber(redis))
    embed_task = asyncio.create_task(embed_worker_loop())
    sweep_task = asyncio.create_task(embedding_sweep_loop())
    sync_task = asyncio.create_task(sync_external_loop())
    yield
    pubsub_task.cancel()
    embed_task.cancel()
    sweep_task.cancel()
    sync_task.cancel()
    await stop_leader_election(redis)
    await engine.dispose()
    await redis.aclose()


app = FastAPI(
    title="UniChat API",
    version="1.0.0",
    description="UniChat unified communication platform API",
    lifespan=lifespan,
)

from fastapi import Request
from fastapi.responses import JSONResponse

# Exception handlers
app.add_exception_handler(AppError, app_error_handler)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled server exception at %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal server error occurred", "code": "internal_error"},
    )

app.include_router(auth_router)
app.include_router(workspaces_and_channels_router)
app.include_router(messaging_router)
app.include_router(realtime_router)
app.include_router(integrations_router)
app.include_router(ai_assistant_router)

# CORS configuration
origins = [settings.FRONTEND_URL]
if "http://localhost:3000" not in origins:
    origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r'https://.*\.vercel\.app',
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, Any]:
    db_ok = False
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1;"))
            db_ok = result.scalar() == 1
    except Exception:
        db_ok = False

    redis_ok = False
    try:
        redis = get_redis_client()
        pong = await redis.ping()
        redis_ok = pong is True or pong == "PONG"
    except Exception:
        redis_ok = False

    ai_status = "enabled" if bool(settings.GEMINI_API_KEY) else "disabled"

    return {
        "status": "ok",
        "database": db_ok,
        "redis": redis_ok,
        "ai": ai_status,
        "background": get_background_status(),
    }
