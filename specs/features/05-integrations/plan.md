# Feature 05: Integrations — Plan

## Endpoints
| Method | Path | Auth | Status Codes |
|---|---|---|---|
| GET | `/integrations` | Bearer JWT | 200, 401 |
| GET | `/workspaces/{workspace_id}/channel-links` | Bearer JWT | 200, 401, 403 |
| GET | `/channels/{channel_id}/links` | Bearer JWT | 200, 401, 403 |
| GET | `/integrations/slack/oauth/start` | Bearer JWT | 302, 401, 403, 404 |
| GET | `/integrations/slack/oauth/callback` | None (OAuth redirect) | 302 |
| POST | `/integrations/slack/connect` | Bearer JWT | 201, 400, 401, 403 |
| POST | `/integrations/discord/connect` | Bearer JWT | 201, 400, 401, 403 |
| DELETE | `/integrations/{id}` | Bearer JWT | 200, 401, 403, 404 |
| GET | `/integrations/{id}/external-channels` | Bearer JWT | 200, 401, 403, 404 |
| POST | `/channels/{id}/link` | Bearer JWT | 201, 400, 401, 403, 404, 409 |
| DELETE | `/channels/{id}/link` | Bearer JWT | 200, 401, 403, 404 |

## Database Models (`backend/app/features/integrations/models.py`)
- `ConnectedPlatform`: `id`, `workspace_id`, `platform`, `encrypted_tokens`, `bot_identity`, `display_name`, `created_at`
- `ChannelLink`: `id`, `channel_id`, `platform_id`, `platform`, `external_channel_id`, `external_channel_name`, `encrypted_webhook_url`, `webhook_id`, `last_synced_external_id`, `created_at`

## Module Structure (`backend/app/features/integrations/`)
- `models.py`
- `schemas.py`
- `repository.py`
- `service.py`
- `routes.py`
- `echo_guard.py` — Identity filter, DB uniqueness backstop, 30s Redis race window guard.
- `adapters/`
  - `base.py` — `PlatformAdapter` abstract base class.
  - `slack_adapter.py` — Slack Socket Mode, `chat.postMessage`, `auth.test`, user cache.
  - `discord_adapter.py` — Discord REST API, Webhooks, polling worker.
- `background/sync_external.py` — Redis leader lock background manager.
