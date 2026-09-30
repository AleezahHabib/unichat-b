import asyncio
import json
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import decode_access_token
from app.features.authentication.repository import user_repository
from app.features.realtime.connections import connection_manager
from app.features.realtime.events import (
    pong_event,
    presence_update_event,
    ready_event,
    typing_event,
)
from app.features.realtime.presence import presence_manager
from app.features.realtime.pubsub import publish_event
from app.features.workspaces_and_channels.repository import workspace_repository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtime"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    await websocket.accept()
    authenticated = False
    user_id_str: str | None = None
    workspace_ids: list[str] = []

    # 1. 5.0-second auth window
    try:
        raw_msg = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
        auth_data = json.loads(raw_msg)
        if auth_data.get("type") != "auth" or not auth_data.get("token"):
            await websocket.close(code=4401, reason="Unauthorized")
            return

        token = auth_data["token"]
        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            await websocket.close(code=4401, reason="Unauthorized")
            return

        user_id_str = payload["sub"]
        authenticated = True
    except (asyncio.TimeoutError, json.JSONDecodeError, Exception):
        try:
            await websocket.close(code=4401, reason="Unauthorized")
        except Exception:
            pass
        return

    # 2. Get user's workspaces
    user_uuid = UUID(user_id_str)
    workspaces = await workspace_repository.list_user_workspaces(db, user_uuid)
    workspace_ids = [str(w["id"]) if isinstance(w, dict) else str(w.id) for w in workspaces]

    # 3. Register connection & presence
    is_first_conn = connection_manager.connect(websocket, user_id_str, workspace_ids)
    await presence_manager.set_online(redis, user_id_str)

    if is_first_conn:
        for ws_id in workspace_ids:
            p_evt = presence_update_event(ws_id, user_id_str, "online")
            await publish_event(redis, ws_id, p_evt)

    # Send ready event
    r_evt = ready_event(user_id_str, workspace_ids)
    await connection_manager.send_personal_message(websocket, r_evt)

    # 4. Main event loop
    try:
        while True:
            text_frame = await websocket.receive_text()
            try:
                frame = json.loads(text_frame)
                frame_type = frame.get("type")

                if frame_type == "ping":
                    await presence_manager.refresh_ping(redis, user_id_str)
                    await connection_manager.send_personal_message(websocket, pong_event())

                elif frame_type == "typing":
                    channel_id = frame.get("channel_id")
                    if channel_id:
                        ch = await workspace_repository.get_channel(db, UUID(channel_id))
                        if ch:
                            user = await user_repository.get_by_id(db, user_uuid)
                            u_name = user.name if user else "Someone"
                            t_evt = typing_event(
                                workspace_id=str(ch.workspace_id),
                                channel_id=channel_id,
                                user_id=user_id_str,
                                user_name=u_name,
                            )
                            await publish_event(redis, str(ch.workspace_id), t_evt)

            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WebSocket error for user {user_id_str}: {e}")
    finally:
        user_id, is_last_conn = connection_manager.disconnect(websocket)
        if is_last_conn and user_id:
            await presence_manager.set_offline(redis, user_id)
            for ws_id in workspace_ids:
                p_evt = presence_update_event(ws_id, user_id, "offline")
                await publish_event(redis, ws_id, p_evt)
