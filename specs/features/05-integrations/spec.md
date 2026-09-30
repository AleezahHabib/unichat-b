# Feature 05: Integrations — Specification

## Overview
Connect Slack and Discord to UniChat channels for seamless two-way message synchronization, author identity preservation, thread mapping, and echo prevention.

## Acceptance Criteria

### AC-05-01: Connect platform integrations (Owner-only & encrypted)
- `POST /integrations/slack/connect` accepts `{workspace_id, bot_token, app_token}`. Validates Slack tokens via `auth.test`. Restricts action to workspace owner (403 `forbidden`). Stores tokens Fernet-encrypted in `connected_platforms`. Saves `bot_identity` and `display_name`.
- `POST /integrations/discord/connect` accepts `{workspace_id, bot_token}`. Validates Discord token via `GET /users/@me`. Restricts to workspace owner (403 `forbidden`). Stores Fernet-encrypted.
- `GET /integrations?workspace_id=...` lists connected integrations. Tokens are **NEVER** returned by any endpoint.
- `DELETE /integrations/{id}` stops active listeners/pollers and removes all associated channel links.

### AC-05-02: External channel discovery and linking
- `GET /integrations/{id}/external-channels` lists live channels available on the connected platform and opportunistically refreshes cached `external_channel_name` values on existing `channel_links`.
- `POST /channels/{id}/link` links a UniChat channel to an external channel (`{platform_id, external_channel_id, external_channel_name}`).
  - For Slack: joins the channel via `conversations.join`.
  - For Discord: creates a webhook (`POST /channels/{id}/webhooks`), saves `encrypted_webhook_url` and `webhook_id`, sets `last_synced_external_id` to current newest message ID.
- `DELETE /channels/{id}/link` unlinks the channel.

### AC-05-03: Slack two-way sync & Socket Mode
- Outbound: `unichat` messages posted to a linked channel are relayed via Slack `chat.postMessage` with `username="<Name> (via UniChat)"`. Thread replies are mapped to Slack `thread_ts`. Returns `ts` saved as `external_id`.
- Inbound: Socket Mode listener acknowledges within 3 seconds, handles `message` events without subtype or `thread_broadcast`, resolves sender names via `users.info` with 10-minute in-memory caching, maps `thread_ts` to `parent_id`, saves message with `source='slack'`, and publishes realtime WS event.

### AC-05-04: Discord two-way sync & REST polling
- Outbound: `unichat` messages are relayed to Discord webhook with `?wait=true`, `username="<Name> (via UniChat)"`, and `allowed_mentions:{parse:[]}`. Thread replies are prefixed with `↪ replying to <author>: "<first 60 chars>"`. Returns Discord message ID as `external_id`.
- Inbound: Background poller runs every `DISCORD_POLL_SECONDS` (default 3s). Fetches `GET /channels/{id}/messages?after=<cursor>&limit=50` for each Discord link (oldest first). Maps `message_reference.message_id` to `parent_id`, resolves author name (`nick` -> `global_name` -> `username`), saves with `source='discord'`, publishes realtime WS event, and advances cursor. Respects HTTP 429 `retry_after`.

### AC-05-05: Three-layer echo prevention (Echo Guard)
- Layer 1: Identity Filter — ignores messages sent by UniChat's own bot ID or webhook ID.
- Layer 2: Database Constraint — partial unique index `uq_messages_external` on `(external_channel_id, external_id)` with `INSERT ... ON CONFLICT DO NOTHING`.
- Layer 3: Race Window Guard — 30-second Redis key set per outbound message to ignore echoes that arrive before `send()` returns.

### AC-05-06: Cross-platform relaying
- A message originating from Slack in a channel linked to BOTH Slack and Discord is relayed to Discord, and vice versa. Outbound relay only skips returning the message back to the platform it originated from.

### AC-05-07: Background worker lifecycle & leader lock
- Slack SocketModeClient listeners and Discord pollers run under `core/leader.py` Redis leader lock (`SET unichat:leader <id> NX EX 30`).
- Integrations start/stop immediately when connected or deleted via API.

### AC-05-08: Health endpoint reporting
- `GET /health` reports `"background": "leader"`, `"follower"`, or `"off"` based on leader lock status.
