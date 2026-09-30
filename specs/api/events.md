# UniChat Realtime WebSocket Protocol Specification

## Overview
UniChat provides low-latency bidirectional realtime events using a single WebSocket endpoint: `GET /ws`.
The realtime layer handles live message delivery, thread reply broadcasting, instant typing indicators, and team member presence across distributed clients.

---

## 1. Connection Lifecycle & Authentication

### Handshake & Initial Auth
1. The client establishes a standard WebSocket connection to `/ws`.
2. **5-Second Auth Window**: The client must transmit an authentication frame within **5.0 seconds** of socket connection:
   ```json
   {
     "type": "auth",
     "token": "<jwt_access_token>"
   }
   ```
3. If no auth frame is received within 5 seconds, or if the JWT is invalid/expired, the server abruptly closes the connection with code `4401` (`Unauthorized`).
4. Upon successful validation:
   - The user's active session is mapped to their workspaces.
   - The connection subscribes to all workspaces the user belongs to.
   - The server responds with a `ready` event envelope containing user context and presence snapshot.

### Heartbeat & Ping/Pong
- To maintain socket liveness and update user presence, the client sends a ping frame every **25 seconds**:
  ```json
  {
     "type": "ping"
  }
  ```
- The server replies with:
  ```json
  {
     "type": "pong",
     "ts": "2026-09-25T15:20:00Z"
  }
  ```

---

## 2. Client-to-Server Events

### `auth`
Sent once upon socket opening.
```json
{
  "type": "auth",
  "token": "eyJhbGciOi..."
}
```

### `ping`
Keepalive ping sent every 25 seconds. Refreshes presence TTL.
```json
{
  "type": "ping"
}
```

### `typing`
Indicates the active user is typing in a channel.
*Client-side throttling rule*: Must be throttled to at most **1 event every 2.0 seconds** per channel.
```json
{
  "type": "typing",
  "channel_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

---

## 3. Server-to-Client Event Envelope
All server broadcasts adhere to a strict envelope structure:

```json
{
  "type": "<event_type>",
  "workspace_id": "<uuid | null>",
  "channel_id": "<uuid | null>",
  "data": { ... },
  "ts": "2026-09-25T15:20:00.000Z"
}
```

### Event Types

#### 1. `ready`
Sent immediately following successful auth.
```json
{
  "type": "ready",
  "workspace_id": null,
  "channel_id": null,
  "data": {
    "user_id": "usr_9812",
    "workspaces": ["ws_123"]
  },
  "ts": "2026-09-25T15:20:00.000Z"
}
```

#### 2. `message.created`
Broadcasted when a new top-level message is posted (native or synced).
```json
{
  "type": "message.created",
  "workspace_id": "ws_123",
  "channel_id": "ch_456",
  "data": {
    "id": "msg_001",
    "channel_id": "ch_456",
    "author": {
      "id": "usr_9812",
      "name": "Alex",
      "avatar_color": "#2F6BFF",
      "is_external": false
    },
    "body": "Hello team!",
    "source": "unichat",
    "parent_id": null,
    "created_at": "2026-09-25T15:20:01.000Z",
    "edited_at": null,
    "is_deleted": false,
    "reply_count": 0,
    "last_reply_at": null
  },
  "ts": "2026-09-25T15:20:01.000Z"
}
```

#### 3. `message.updated`
Broadcasted when an author updates an existing message.
```json
{
  "type": "message.updated",
  "workspace_id": "ws_123",
  "channel_id": "ch_456",
  "data": {
    "id": "msg_001",
    "body": "Hello team! Updated text.",
    "edited_at": "2026-09-25T15:21:00.000Z"
  },
  "ts": "2026-09-25T15:21:00.000Z"
}
```

#### 4. `message.deleted`
Broadcasted when a message is soft-deleted.
```json
{
  "type": "message.deleted",
  "workspace_id": "ws_123",
  "channel_id": "ch_456",
  "data": {
    "id": "msg_001",
    "is_deleted": true
  },
  "ts": "2026-09-25T15:22:00.000Z"
}
```

#### 5. `thread.reply`
Broadcasted when a reply is added to a thread. Updates root reply count and last reply timestamp.
```json
{
  "type": "thread.reply",
  "workspace_id": "ws_123",
  "channel_id": "ch_456",
  "data": {
    "parent_id": "msg_001",
    "reply": {
      "id": "msg_002",
      "author": { "name": "Sarah", "avatar_color": "#7C5CFF" },
      "body": "Acknowledged."
    },
    "reply_count": 1,
    "last_reply_at": "2026-09-25T15:23:00.000Z"
  },
  "ts": "2026-09-25T15:23:00.000Z"
}
```

#### 6. `typing`
Broadcasted to channel members when someone is actively typing. Clears automatically after 3 seconds without new typing events.
```json
{
  "type": "typing",
  "workspace_id": "ws_123",
  "channel_id": "ch_456",
  "data": {
    "user_id": "usr_9812",
    "user_name": "Alex"
  },
  "ts": "2026-09-25T15:23:10.000Z"
}
```

#### 7. `presence.update`
Broadcasted when a user transitions between online and offline.
```json
{
  "type": "presence.update",
  "workspace_id": "ws_123",
  "channel_id": null,
  "data": {
    "user_id": "usr_9812",
    "status": "online"
  },
  "ts": "2026-09-25T15:23:15.000Z"
}
```

#### 8. `pong`
Sent in response to a client `ping`.
```json
{
  "type": "pong",
  "workspace_id": null,
  "channel_id": null,
  "data": {},
  "ts": "2026-09-25T15:23:25.000Z"
}
```


---

## 4. Server Architecture & Scalability Design

### Single Redis Subscriber per Process
- In multi-worker or cloud deployments (FastAPI on Railway), each backend process boots **one** global background listener that runs `PSUBSCRIBE unichat:ws:*`.
- Internal message bus channels are formatted as:
  `unichat:ws:{workspace_id}`
- When an API endpoint commits a message or state change, it publishes the event payload to `unichat:ws:{workspace_id}`.
- The process listener receives the event from Redis and dispatches it strictly to locally connected client WebSockets that have joined `{workspace_id}`.
- This guarantees **O(1) Redis pub/sub connections per server process** rather than O(N) connections per connected client.

### Presence Tracking Design
- Key pattern: `unichat:presence:{user_id}` in Upstash Redis.
- **TTL**: Keys are stored with a **60-second TTL**.
- Every socket connection or `ping` received refreshes `SET unichat:presence:{user_id} 1 EX 60`.
- Users remain "online" as long as any active tab continues pinging.
- When all tabs close, the key naturally expires in <= 60 seconds. A periodic presence checker or disconnect handler broadcasts `presence.update` (`status: "offline"`) when no active socket remains for that user.
- **Workspace Isolation**: Events are strictly verified against `workspace_id`. A user never receives an event from a workspace they are not an active member of.
