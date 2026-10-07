# Feature 03: Messaging — Specification

## Overview
Core messaging capabilities including message creation, editing, soft deletion, cursor pagination, and threaded replies across UniChat channels.

## Acceptance Criteria

### AC-03-01: Message creation, authorization, and rate limiting
- `POST /channels/{id}/messages` accepts `{body, parent_id}`.
- Requires channel membership (returns 403 `forbidden` if non-member).
- `body` must be 1 to 4000 characters.
- User rate limit: max 30 messages/min/user (returns 429 `rate_limited` when exceeded).
- Source is `unichat`, author is `current_user.id`.
- Returns 201 Created with `MessageResponse`.

### AC-03-02: Cursor pagination for channel messages
- `GET /channels/{id}/messages?cursor=...&limit=50`
- Requires channel membership.
- Returns messages sorted newest-first by `created_at`.
- Includes `reply_count` and `last_reply_at` for parent messages.
- Returns `{items, next_cursor}`.

### AC-03-03: Editing and soft deleting messages
- `PATCH /messages/{id}` accepts `{body}`. Only author can edit, only `unichat` source. Sets `edited_at = CURRENT_TIMESTAMP`. Non-author returns 403 `forbidden`.
- `DELETE /messages/{id}` soft deletes. Only author can delete, only `unichat` source. Sets `deleted_at = CURRENT_TIMESTAMP`, clears `body` or flags `is_deleted = true`. Non-author returns 403 `forbidden`.

### AC-03-04: Threaded replies
- Messages with `parent_id` set act as thread replies.
- `GET /messages/{id}/thread` returns parent message plus all replies in oldest-first order.
- Replies increment `reply_count` on the parent message.


### AC-03-07: Clear Chat for Me (Per-User Local Clear)
- User can clear chat history for themselves in a channel (`POST /channels/{channel_id}/clear`).
- Upserts timestamp in `channel_user_clears(user_id, channel_id, cleared_at)`.
- Channel message list queries (`GET /channels/{channel_id}/messages`) for that user filter out messages where `created_at <= cleared_at`.
- Messages remain intact in database; other members and owner see all messages unaffected.
- No realtime event is broadcast to other users.
- New messages sent after the clear appear normally for all users.
