# Feature 06: AI Assistant — Plan

## Endpoints
| Method | Path | Auth | Status Codes |
|---|---|---|---|
| POST | `/assistant/chat` | Bearer JWT | 200, 401, 403, 429, 503 |
| GET | `/assistant/history` | Bearer JWT | 200, 401, 403 |
| POST | `/assistant/summarize` | Bearer JWT | 200, 401, 403, 404, 429, 503 |
| POST | `/assistant/draft-reply` | Bearer JWT | 200, 401, 403, 404, 429, 503 |
| GET | `/search` | Bearer JWT | 200, 401, 403 |

## Database Models (`backend/app/features/ai_assistant/models.py`)
- `AssistantChat`: `id`, `user_id`, `workspace_id`, `session_id`, `role`, `content`, `citations` (JSONB), `created_at`
- `MessageEmbedding`: `message_id`, `embedding` (vector(768)), `model`, `created_at`

## Module Structure (`backend/app/features/ai_assistant/`)
- `models.py`
- `schemas.py`
- `repository.py`
- `embeddings.py` — `google-genai` embedding generation helper.
- `agents/` — OpenAI Agents SDK wrappers pointed at Gemini's OpenAI-compatible endpoint.
- `service.py` — Q&A, summary, reply drafting, semantic search.
- `routes.py`
