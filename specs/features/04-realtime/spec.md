# Feature 04: Realtime — Specification

## Overview
Low-latency bidirectional WebSocket communications (`GET /ws`) powering live message delivery, thread replies, typing indicators, and user presence status.

## Acceptance Criteria

### AC-04-01: WebSocket connection handshake and 5s authentication
- `GET /ws` establishes connection.
- First frame sent by client within 5.0 seconds must be `{"type":"auth","token":"..."}`.
- If no auth frame is received within 5s or token is invalid/expired, socket is closed with code `4401` (`Unauthorized`).
- On successful auth, server sends `ready` envelope containing user ID and list of subscribed workspaces.

### AC-04-02: Heartbeat ping/pong and presence tracking
- Client sends `{"type":"ping"}` frame every 25 seconds.
- Server responds with `{"type":"pong","workspace_id":null,"channel_id":null,"data":{},"ts":"..."}`.
- Setting presence key in Redis `unichat:presence:{user_id}` with 60s TTL on connect and ping.
- When local connection count goes 0 -> 1, publishes `presence.update` (`status: "online"`).
- When local connection count goes 1 -> 0, publishes `presence.update` (`status: "offline"`).

### AC-04-03: Realtime message event broadcasting
- When a message is created (`message.created`), edited (`message.updated`), deleted (`message.deleted`), or replied to (`thread.reply`), an event is published to `unichat:ws:{workspace_id}`.
- Process listener forwards event to all locally connected sockets subscribed to that `workspace_id`.

### AC-04-04: Typing indicator events
- Client sends `{"type":"typing","channel_id":"..."}` throttled to max 1 event every 2.0 seconds per channel.
- Server broadcasts `typing` envelope to channel members in that workspace.
- Frontend clears typing indicator 3 seconds after the last received typing event.

### AC-04-05: Multi-tenant workspace isolation
- Connected clients only receive events for workspaces they are active members of.
- Clients connected to workspace A never receive messages or typing events originating from workspace B.
