# Feature 06: AI Assistant — Specification

## Overview
Grounded AI intelligence powered exclusively by Google Gemini via the OpenAI Agents SDK and `google-genai` embeddings. Functions include cited Q&A across messages, channel summarization, reply drafting, and pgvector semantic search.

## Acceptance Criteria

### AC-06-01: Q&A assistant with grounded source citations
- `POST /assistant/chat` accepts `{workspace_id, session_id, message}`.
- Uses Gemini agent to answer questions based strictly on workspace message context.
- Returns `{response, citations}` where each citation includes `{message_id, author_name, channel_name, created_at, snippet}`.
- History is saved in `assistant_chats` table.
- `GET /assistant/history?workspace_id=...&session_id=...` retrieves chat session history.

### AC-06-02: Channel summarization
- `POST /assistant/summarize` accepts `{channel_id, since_hours}` (default 24h).
- Fetches messages in that timeframe and invokes Gemini summarizer agent.
- Returns `{summary, key_decisions, action_items, message_count}`.

### AC-06-03: Reply drafting
- `POST /assistant/draft-reply` accepts `{message_id}`.
- Invokes Gemini drafter agent to construct a draft response based on the message thread context.
- Returns `{draft}`. Never sends the message automatically.

### AC-06-04: Semantic search with pgvector and keyword fallback
- `GET /search?workspace_id=...&q=...&limit=20`
- Generates 768-dim embedding via `google-genai` (model `gemini-embedding-001`).
- Queries `message_embeddings` using HNSW cosine distance (`<=>`).
- If `GEMINI_API_KEY` is not set, falls back to Postgres keyword ILIKE search across `messages.body`.
- Returns array of `{message_id, channel_name, author_name, body, created_at, score}`.

### AC-06-05: Rate limiting and graceful degradation
- AI endpoints rate limited to max 10 requests/min/user (returns 429 `rate_limited`).
- If `GEMINI_API_KEY` is empty, AI endpoints return 503 `ai_disabled`.
- If Gemini API budget/quota is exceeded, returns 503 `ai_busy` with `retry_after_seconds`.
