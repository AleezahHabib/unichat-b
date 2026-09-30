# Feature 04: Realtime — Plan

## Architecture & Modules (`backend/app/features/realtime/`)
- `events.py` — Envelope builders for `ready`, `message.created`, `message.updated`, `message.deleted`, `thread.reply`, `typing`, `presence.update`, `pong`.
- `connections.py` — In-process `ConnectionManager` mapping active sockets to `user_id` and subscribed `workspace_ids`. Tracks per-user connection count.
- `pubsub.py` — `publish(workspace_id, event)` publishing to Redis `unichat:ws:{workspace_id}`; global process listener on `PSUBSCRIBE unichat:ws:*` forwarding events to local sockets.
- `presence.py` — Presence manager setting `unichat:presence:{user_id}` EX 60, detecting 0->1 and 1->0 state transitions to trigger `presence.update`.
- `routes.py` — `/ws` WebSocket endpoint enforcing 5-second auth window, ping/pong, typing frame handling.

## Changes to Messaging Service (`backend/app/features/messaging/service.py`)
- Publish realtime events to `unichat:ws:{workspace_id}` after every `create_message`, `update_message`, `delete_message`.

## Frontend (`frontend/`)
- `src/lib/websocket.ts` — Single WebSocket client, auth frame, auto-reconnect with exponential backoff, typed event listener.
- `src/features/realtime/RealtimeProvider.tsx` & `useRealtime.ts` — Context wrapping workspace layout.
- `src/features/realtime/components/TypingIndicator.tsx` — Displays "X is typing..." clearing after 3s.
- `src/features/realtime/components/OnlineDot.tsx` — Renders online status indicator.

## Testing Strategy (`backend/tests/test_realtime.py` & `conftest.py`)
- Starlette's sync `TestClient` runs the FastAPI ASGI app in a separate background thread with its own asyncio event loop.
- To prevent `asyncpg` cross-event-loop errors ("attached to a different loop") and ensure `fakeredis` pub/sub events are delivered across REST and WebSocket handlers:
  - We use a dedicated `websocket_client` fixture in `conftest.py` that constructs an event-loop-isolated SQLAlchemy `AsyncEngine` / `AsyncSession` factory and a `fakeredis.FakeServer()` inside `TestClient`'s thread loop context.
  - Dependency overrides for `get_db` and `get_redis` deliver thread-local connections to the test client.

