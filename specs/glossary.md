# FistaChat Glossary

This document establishes unambiguous definitions for domain concepts used across the specification, codebase, and API surfaces.

| Term | Definition |
| :--- | :--- |
| **Workspace** | An isolated organization or project space owned by a user, containing channels, members, invites, and external platform integrations. |
| **Channel** | A public topic-based message stream scoped within a workspace. Always starts with `#general`. |
| **Workspace Member** | A user who has joined a workspace, assigned either an `owner` or `member` role. |
| **Channel Member** | A workspace member who has subscribed to a specific channel. Non-members cannot read or post messages. |
| **Message** | A single communication item within a channel (max 4000 characters). May be native to FistaChat or synced from an external platform. |
| **Thread** | A nested conversation branch attached to a root message via `parent_id`. |
| **Soft Delete** | A deletion mechanism where `deleted_at` is set, clearing or masking the message content while preserving thread hierarchy. |
| **Connected Platform** | A workspace-level third-party integration credential record (`slack` or `discord`) containing encrypted authentication keys. |
| **Channel Link** | A 1:1 binding between a local FistaChat channel and an external Slack/Discord channel for bidirectional message forwarding. |
| **Echo Guard** | Multi-layer mechanism ensuring messages broadcasted from FistaChat to external platforms are not re-ingested back into FistaChat as new messages. |
| **Citation** | A reference attached to an AI assistant reply pointing directly to a specific source message (`message_id`, `channel_id`, `channel_name`, `author_name`, `source`, `snippet`). |
| **Draft Reply** | An AI-generated suggested response pre-populated into the user's message composer for manual review before sending. |
| **Semantic Search** | Natural language vector retrieval using high-dimensional cosine similarity embeddings (`vector(768)`) against PostgreSQL `pgvector`. |
| **Presence** | Ephemeral online/offline state of users managed via Redis TTL keys (60-second window refreshed on heartbeats). |
| **Cursor Pagination** | Pagination mechanism using opaque or timestamp/id-based cursors to fetch 50 messages per page without offset performance degradation. |
