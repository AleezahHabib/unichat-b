import json
import logging
from typing import Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # socket -> { "user_id": str, "workspace_ids": set[str] }
        self.active_connections: dict[WebSocket, dict[str, Any]] = {}
        # user_id -> count of active sockets in this process
        self.user_connection_counts: dict[str, int] = {}

    def connect(
        self, websocket: WebSocket, user_id: str, workspace_ids: list[str]
    ) -> bool:
        """
        Registers socket. Returns True if this is the user's FIRST local connection (0 -> 1).
        """
        self.active_connections[websocket] = {
            "user_id": user_id,
            "workspace_ids": set(workspace_ids),
        }

        prev_count = self.user_connection_counts.get(user_id, 0)
        self.user_connection_counts[user_id] = prev_count + 1
        return prev_count == 0

    def disconnect(self, websocket: WebSocket) -> tuple[str | None, bool]:
        """
        Unregisters socket. Returns (user_id, is_last_connection).
        is_last_connection is True if user count drops 1 -> 0 locally.
        """
        conn_info = self.active_connections.pop(websocket, None)
        if not conn_info:
            return None, False

        user_id = conn_info["user_id"]
        count = self.user_connection_counts.get(user_id, 1) - 1

        if count <= 0:
            self.user_connection_counts.pop(user_id, None)
            return user_id, True
        else:
            self.user_connection_counts[user_id] = count
            return user_id, False

    def get_user_workspaces(self, websocket: WebSocket) -> set[str]:
        conn_info = self.active_connections.get(websocket)
        return conn_info["workspace_ids"] if conn_info else set()

    def get_user_id(self, websocket: WebSocket) -> str | None:
        conn_info = self.active_connections.get(websocket)
        return conn_info["user_id"] if conn_info else None

    async def send_personal_message(
        self, websocket: WebSocket, message: dict[str, Any]
    ) -> None:
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.warning(f"Error sending message to websocket: {e}")

    async def broadcast_to_workspace(
        self, workspace_id: str, message: dict[str, Any]
    ) -> None:
        payload = json.dumps(message)
        for ws, info in list(self.active_connections.items()):
            if workspace_id in info["workspace_ids"]:
                try:
                    await ws.send_text(payload)
                except Exception as e:
                    logger.warning(f"Error broadcasting to socket: {e}")


connection_manager = ConnectionManager()
