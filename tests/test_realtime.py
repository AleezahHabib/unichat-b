import uuid
import pytest
from starlette.testclient import TestClient


def create_user_and_login(client: TestClient, name: str) -> tuple[dict, str]:
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/auth/signup",
        json={"name": name, "email": email, "password": "Password123!"},
    )
    data = resp.json()
    return data["user"], data["access_token"]


def receive_event(ws, expected_type: str, max_frames: int = 15) -> dict:
    """Helper to drain transient presence.update frames and wait for target event type."""
    for _ in range(max_frames):
        evt = ws.receive_json()
        if evt.get("type") == expected_type:
            return evt
    pytest.fail(f"Did not receive expected event '{expected_type}' within {max_frames} frames")


def test_AC_04_01_handshake_and_5s_auth_timeout(websocket_client: TestClient):
    user, token = create_user_and_login(websocket_client, "RT User 1")

    # 1. Invalid token frame -> connection closed / error
    with pytest.raises(Exception):
        with websocket_client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "auth", "token": "invalid_jwt_token"})
            ws.receive_json()

    # 2. Valid token frame -> receives ready event
    with websocket_client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": token})
        ready_frame = receive_event(ws, "ready")
        assert ready_frame["data"]["user_id"] == user["id"]


def test_AC_04_02_ping_pong_heartbeat(websocket_client: TestClient):
    user, token = create_user_and_login(websocket_client, "RT User 2")

    with websocket_client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "auth", "token": token})
        _ready = receive_event(ws, "ready")

        # Send ping
        ws.send_json({"type": "ping"})
        pong_frame = receive_event(ws, "pong")
        assert pong_frame["type"] == "pong"


def test_AC_04_03_realtime_message_broadcasting(websocket_client: TestClient):
    user, token = create_user_and_login(websocket_client, "RT User 3")
    headers = {"Authorization": f"Bearer {token}"}
    ws = websocket_client.post("/workspaces", json={"name": "RT WS"}, headers=headers).json()
    channels = websocket_client.get(f"/workspaces/{ws['id']}/channels", headers=headers).json()
    gen_ch = next(c for c in channels if c["name"] == "general")

    with websocket_client.websocket_connect("/ws") as ws_conn:
        ws_conn.send_json({"type": "auth", "token": token})
        _ready = receive_event(ws_conn, "ready")

        # Post message via REST API
        msg_resp = websocket_client.post(
            f"/channels/{gen_ch['id']}/messages",
            json={"body": "Realtime Hello!"},
            headers=headers,
        )
        assert msg_resp.status_code == 201

        # Socket should receive message.created event
        evt = receive_event(ws_conn, "message.created")
        assert evt["workspace_id"] == ws["id"]
        assert evt["data"]["body"] == "Realtime Hello!"


def test_AC_04_04_typing_indicators(websocket_client: TestClient):
    user, token = create_user_and_login(websocket_client, "Typer User")
    headers = {"Authorization": f"Bearer {token}"}
    ws = websocket_client.post("/workspaces", json={"name": "Type WS"}, headers=headers).json()
    channels = websocket_client.get(f"/workspaces/{ws['id']}/channels", headers=headers).json()
    gen_ch = next(c for c in channels if c["name"] == "general")

    with websocket_client.websocket_connect("/ws") as ws_conn:
        ws_conn.send_json({"type": "auth", "token": token})
        _ready = receive_event(ws_conn, "ready")

        # Send typing frame
        ws_conn.send_json({"type": "typing", "channel_id": gen_ch["id"]})
        evt = receive_event(ws_conn, "typing")
        assert evt["channel_id"] == gen_ch["id"]
        assert evt["data"]["user_id"] == user["id"]


def test_AC_04_05_multi_tenant_workspace_isolation(websocket_client: TestClient):
    u1, token1 = create_user_and_login(websocket_client, "User WS A1")
    u2, token2 = create_user_and_login(websocket_client, "User WS A2")
    u3, token3 = create_user_and_login(websocket_client, "User WS B")

    h1 = {"Authorization": f"Bearer {token1}"}
    h2 = {"Authorization": f"Bearer {token2}"}
    h3 = {"Authorization": f"Bearer {token3}"}

    # Workspace A with u1 and u2
    wsA = websocket_client.post("/workspaces", json={"name": "Workspace A"}, headers=h1).json()
    invA = websocket_client.post(f"/workspaces/{wsA['id']}/invites", headers=h1).json()
    websocket_client.post(f"/invites/{invA['token']}/accept", headers=h2)

    # Workspace B with u3 only
    wsB = websocket_client.post("/workspaces", json={"name": "Workspace B"}, headers=h3).json()

    chA = websocket_client.get(f"/workspaces/{wsA['id']}/channels", headers=h1).json()[0]

    with websocket_client.websocket_connect("/ws") as ws1:
        ws1.send_json({"type": "auth", "token": token1})
        _r1 = receive_event(ws1, "ready")

        with websocket_client.websocket_connect("/ws") as ws2:
            ws2.send_json({"type": "auth", "token": token2})
            _r2 = receive_event(ws2, "ready")

            with websocket_client.websocket_connect("/ws") as ws3:
                ws3.send_json({"type": "auth", "token": token3})
                _r3 = receive_event(ws3, "ready")

                # User 1 posts message in Workspace A
                websocket_client.post(
                    f"/channels/{chA['id']}/messages",
                    json={"body": "Secret WS A Message"},
                    headers=h1,
                )

                # ws1 should receive event
                evt1 = receive_event(ws1, "message.created")
                assert evt1["workspace_id"] == wsA["id"]

                # ws2 should receive event
                evt2 = receive_event(ws2, "message.created")
                assert evt2["workspace_id"] == wsA["id"]

                # ws3 (in Workspace B) must NOT receive event
                ws3.send_json({"type": "ping"})
                evt3 = receive_event(ws3, "pong")
                assert evt3["type"] == "pong"
