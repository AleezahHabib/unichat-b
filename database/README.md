# UniChat Database Architecture & Schema

## Overview
UniChat uses PostgreSQL (hosted on free Neon with the `pgvector` extension) to power transactional chat, team memberships, two-way third-party platform synchronization (Slack and Discord), and vector embeddings for semantic search and AI assistance.

The database consists of **11 primary tables**:
1. `users`
2. `workspaces`
3. `workspace_members`
4. `workspace_invites`
5. `channels`
6. `channel_members`
7. `messages`
8. `connected_platforms`
9. `channel_links`
10. `message_embeddings`
11. `assistant_chats`

---

## Architectural Decision: Why One Unified `messages` Table?

A central design choice in UniChat is storing all messages—whether originated natively in UniChat or synced from Slack or Discord—inside the **exact same `messages` table**.

### 1. Zero-Friction Cross-Platform AI and Semantic Search
If external messages were kept in separate tables (e.g. `slack_messages`, `discord_messages`), vector indexing, full-text retrieval, and AI summarization would require multi-table unions, divergent schemas, and complex join cascades. By keeping all conversational flow in a single `messages` table:
- A single `message_embeddings` table references `messages.id` with a 1:1 foreign key.
- Retrieval queries for AI context and semantic search simply filter by `channel_id` (and verify member access) without caring what protocol or app delivered the bytes.
- AI assistant prompts receive uniform message logs formatted identically regardless of platform origin.

### 2. Single-Timeline UI & Pagination
A UniChat channel linked to Slack and Discord displays a single, coherent, chronologically ordered timeline. Using cursor pagination (`created_at`, `id`) on one table guarantees constant-time page fetches without needing in-memory sorting or complex zip-merges across multiple heterogeneous streams.

### 3. Database-Level Duplicate & Echo Guard
Cross-platform synchronization carries the critical risk of message echoes and duplicated webhooks.
In the unified table:
- External messages leave `author_id` as `NULL` and set `external_author_name` with the author's real external identity (e.g. "Jane Doe").
- `external_id` (the Slack `ts` or Discord message ID) and `external_channel_id` are populated.
- A **partial unique index** enforces deduplication:
  ```sql
  CREATE UNIQUE INDEX uq_messages_external_dedup 
  ON messages (external_channel_id, external_id) 
  WHERE external_id IS NOT NULL;
  ```
Any duplicate delivery attempt (e.g. from network retries, dual Socket Mode sockets, or race conditions) is cleanly rejected by PostgreSQL with an integrity violation before it can propagate to UI sockets.

---

## Table Specifications (in Plain English)

### 1. `users`
Stores user authentication profiles and baseline settings.
- `id` (UUID, Primary Key): Unique user identifier.
- `name` (VARCHAR(100)): User display name.
- `email` (VARCHAR(255), UNIQUE): User email address used for login.
- `password_hash` (VARCHAR(255)): Bcrypt-hashed password.
- `avatar_color` (VARCHAR(20)): Deterministic or chosen color hex (e.g. `#2F6BFF`) for avatar placeholder rendering.
- `created_at` (TIMESTAMPTZ): User registration timestamp.

### 2. `workspaces`
Represents isolated team workspaces (analogous to a Slack team or Discord guild).
- `id` (UUID, Primary Key): Workspace identifier.
- `name` (VARCHAR(100)): Workspace title.
- `owner_id` (UUID, FK -> `users.id`): The creator and owner with administrative rights.
- `created_at` (TIMESTAMPTZ): Workspace creation timestamp.

### 3. `workspace_members`
Join table tracking workspace membership and permission levels.
- `workspace_id` (UUID, FK -> `workspaces.id`, Composite PK)
- `user_id` (UUID, FK -> `users.id`, Composite PK)
- `role` (VARCHAR(20)): User role within workspace (`owner` | `member`).
- `joined_at` (TIMESTAMPTZ): When the user entered the workspace.

### 4. `workspace_invites`
Contains cryptographically secure tokens used to invite team members.
- `id` (UUID, Primary Key): Invite identifier.
- `workspace_id` (UUID, FK -> `workspaces.id`): Target workspace.
- `token` (VARCHAR(64), UNIQUE): Secure URL token string.
- `created_by` (UUID, FK -> `users.id`): The workspace owner who generated the invite.
- `expires_at` (TIMESTAMPTZ): Expiration timestamp (default: 7 days after creation).
- `created_at` (TIMESTAMPTZ): Creation timestamp.

### 5. `channels`
Public discussion channels scoped to a workspace.
- `id` (UUID, Primary Key): Channel identifier.
- `workspace_id` (UUID, FK -> `workspaces.id`): Parent workspace.
- `name` (VARCHAR(80)): Channel handle (e.g., `general`, `engineering`).
- `description` (VARCHAR(255)): Optional channel topic or summary.
- `created_by` (UUID, FK -> `users.id`): User who created the channel.
- `created_at` (TIMESTAMPTZ): Creation timestamp.
- *Constraint*: `UNIQUE(workspace_id, name)` ensures channels cannot have conflicting names within a workspace.

### 6. `channel_members`
Tracks users subscribed to a channel.
- `channel_id` (UUID, FK -> `channels.id`, Composite PK)
- `user_id` (UUID, FK -> `users.id`, Composite PK)
- `joined_at` (TIMESTAMPTZ): Time user joined the channel.
- *Rule*: Users cannot leave `#general`. Non-members of a channel cannot read or post messages.

### 7. `messages`
The unified storage table for all conversational messages, replies, and sync records.
- `id` (UUID, Primary Key): Message identifier.
- `channel_id` (UUID, FK -> `channels.id`): Destination channel.
- `author_id` (UUID, NULLABLE, FK -> `users.id`): UniChat author ID. Null for external platform messages.
- `external_author_name` (VARCHAR(100), NULLABLE): Name of author if synced from Slack/Discord.
- `parent_id` (UUID, NULLABLE, FK -> `messages.id`): Self-referential thread parent identifier.
- `body` (TEXT): Message markdown/text payload (constrained to <= 4000 characters).
- `source` (VARCHAR(20)): Origin platform (`unichat` | `slack` | `discord`).
- `external_id` (VARCHAR(128), NULLABLE): External message identifier (e.g. Slack timestamp `1711234567.890123` or Discord snowflake).
- `external_channel_id` (VARCHAR(128), NULLABLE): External platform channel identifier.
- `created_at` (TIMESTAMPTZ): Timestamp when created.
- `edited_at` (TIMESTAMPTZ, NULLABLE): Timestamp of last edit.
- `deleted_at` (TIMESTAMPTZ, NULLABLE): Soft-delete tombstone timestamp. Soft-deleted messages retain their place for thread context but have content redacted.
- *Unique Index*: `(external_channel_id, external_id) WHERE external_id IS NOT NULL`.

### 8. `connected_platforms`
Stores workspace-level credentials and connection tokens for external services.
- `id` (UUID, Primary Key): Connection record identifier.
- `workspace_id` (UUID, FK -> `workspaces.id`): Associated workspace.
- `platform` (VARCHAR(20)): Platform type (`slack` | `discord`).
- `encrypted_tokens` (TEXT): Fernet-symmetric encrypted payload storing bot and app tokens. Real values are never returned to clients.
- `bot_identity` (VARCHAR(100)): External platform bot ID or user ID (used to filter out the bot's own posts).
- `display_name` (VARCHAR(100)): Friendly name of the connected team/guild.
- `created_at` (TIMESTAMPTZ): Connection time.
- *Constraint*: `UNIQUE(workspace_id, platform)` limits a workspace to one active connection per platform type.

### 9. `channel_links`
Maps an internal UniChat channel to an external channel for bidirectional synchronization.
- `id` (UUID, Primary Key): Link record identifier.
- `channel_id` (UUID, FK -> `channels.id`): Local UniChat channel.
- `platform_id` (UUID, FK -> `connected_platforms.id`): Target platform configuration.
- `platform` (VARCHAR(20)): Platform type (`slack` | `discord`).
- `external_channel_id` (VARCHAR(128)): External channel ID (e.g. `C0123456789`).
- `external_channel_name` (VARCHAR(128)): Human-readable external channel title.
- `encrypted_webhook_url` (TEXT, NULLABLE): Fernet-encrypted incoming webhook for Discord fast message relay.
- `webhook_id` (VARCHAR(128), NULLABLE): ID of registered webhook (Discord).
- `last_synced_external_id` (VARCHAR(128), NULLABLE): Checkpoint for polling/sync workers.
- `created_at` (TIMESTAMPTZ): Timestamp link was created.
- *Constraints*:
  - `UNIQUE(channel_id, platform)`: A local channel can link to at most one Slack and one Discord channel.
  - `UNIQUE(platform, external_channel_id)`: Enforces 1:1 mapping so an external channel cannot be bound to multiple UniChat channels.


### 10. `message_embeddings`
Stores high-dimensional vectors for semantic search and retrieval-augmented generation.
- `message_id` (UUID, PK, FK -> `messages.id` ON DELETE CASCADE): Target message.
- `embedding` (vector(768)): 768-dimensional L2-normalized vector generated by `gemini-embedding-001`.
- `model` (VARCHAR(50)): Model identifier tag (`gemini-embedding-001`).
- `created_at` (TIMESTAMPTZ): Embedding generation timestamp.
- *Index*: `CREATE INDEX idx_message_embeddings_hnsw ON message_embeddings USING hnsw (embedding vector_cosine_ops)`.

### 11. `assistant_chats`
Maintains conversational context sessions with the UniChat AI Assistant.
- `id` (UUID, Primary Key): Turn identifier.
- `user_id` (UUID, FK -> `users.id`): User holding the conversation.
- `workspace_id` (UUID, FK -> `workspaces.id`): Scoped workspace.
- `session_id` (VARCHAR(64)): Session grouping key for chat threads.
- `role` (VARCHAR(20)): Dialogue role (`user` | `assistant`).
- `content` (TEXT): Dialogue turn content.
- `citations` (JSONB, NULLABLE): Structured JSON list of cited source messages for grounded answers.
- `created_at` (TIMESTAMPTZ): Interaction timestamp.
