# Feature 03: Messaging — Plan

## Endpoints
| Method | Path | Auth | Status Codes |
|---|---|---|---|
| GET | `/channels/{id}/messages` | Bearer JWT | 200, 401, 403, 404 |
| POST | `/channels/{id}/messages` | Bearer JWT | 201, 400, 401, 403, 404, 429 |
| PATCH | `/messages/{id}` | Bearer JWT | 200, 400, 401, 403, 404 |
| DELETE | `/messages/{id}` | Bearer JWT | 200, 401, 403, 404 |
| GET | `/messages/{id}/thread` | Bearer JWT | 200, 401, 403, 404 |

## Database Models (`backend/app/features/messaging/models.py`)
- `Message`: `id`, `channel_id`, `author_id`, `external_author_name`, `parent_id`, `body`, `source`, `external_id`, `external_channel_id`, `created_at`, `edited_at`, `deleted_at`

## Module Structure (`backend/app/features/messaging/`)
- `models.py`
- `schemas.py`
- `repository.py`
- `service.py` — Calls `pubsub.publish(workspace_id, event)` for `message.created`, `message.updated`, `message.deleted`, and `thread.reply`.
- `routes.py`
