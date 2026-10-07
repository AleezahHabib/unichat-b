# FistaChat Product Overview

## Tagline
> **Chat. Connect. Ask.**

FistaChat bridges the fragmentation between modern collaboration tools. While organizations frequently find themselves fractured across Slack channels, Discord communities, and internal chat applications, FistaChat acts as the unified conversational hub.

---

## Key Pillars

### 1. Unified Team Chat (Chat)
- Workspaces with invite link sharing.
- Public channels (starting with mandatory `#general`).
- Full message lifecycle: rich text formatting (up to 4000 chars), cursor pagination (50 msgs/page), edit tracking (`edited_at`), soft deletes, and deep thread discussions (`reply_count`, `last_reply_at`).
- Low-latency realtime updates over WebSockets: live message delivery (<1s), typing indicators (<500ms), and presence synchronization backed by Upstash Redis.

### 2. Bidirectional External Sync (Connect)
- Seamless 1:1 channel links to Slack channels (via Slack Socket Mode) and Discord channels (via Discord REST polling and incoming webhooks).
- Full two-way message relay: Slack/Discord events appear in FistaChat with author identification and platform badges; FistaChat messages post into external channels marked as `Name (via FistaChat)`.
- Bulletproof multi-layer deduplication and echo prevention to eliminate infinite loop rebroadcasts.
- Thread mapping between FistaChat and Slack threads.

### 3. Grounded Intelligence (Ask)
- **Channel Summarization**: Generates structured recaps categorizing Key Points, Decisions Made, and Open Questions—every item backed by clickable message citations.
- **Cited Q&A**: Answers questions about discussions, automatically citing exact source messages with deep links that scroll to and highlight the original context.
- **Draft Reply**: Composes context-aware replies directly inserted into the message composer for human review—never auto-sent.
- **Semantic Search**: Searches meaning and intent across native messages, Slack messages, and Discord discussions using 768-dimensional vector embeddings (`gemini-embedding-001` + pgvector HNSW cosine indexing), falling back gracefully to keyword search.

---

## Target Audience & Scope
FistaChat is built for engineering teams, open-source communities, and hybrid remote organizations that coordinate across heterogeneous chat networks.

- **In Scope**: Marketing landing page (light + dark mode), JWT auth, workspaces, invite links, public channels, messaging & threads, WebSocket realtime, Slack two-way sync, Discord two-way sync, Gemini AI assistant (summarize, Q&A, draft reply, semantic search).
- **Out of Scope**: SSO/2FA, audio/video streaming, mobile native clients, private channels/DMs, file attachments, admin analytics dashboards, Microsoft Teams sync (adapter interface only), external edit/delete propagation.
