# Feature 02: Workspaces and Channels — Plan

## Endpoints
| Method | Path | Auth | Status Codes |
|---|---|---|---|
| GET | `/workspaces` | Bearer JWT | 200, 401 |
| POST | `/workspaces` | Bearer JWT | 201, 400, 401 |
| DELETE | `/workspaces/{id}` | Bearer JWT | 200, 401, 403, 404 |
| GET | `/workspaces/{id}/members` | Bearer JWT | 200, 401, 403 |
| POST | `/workspaces/{id}/invites` | Bearer JWT | 201, 401, 403 |
| GET | `/invites/{token}` | None | 200, 404 |
| POST | `/invites/{token}/accept` | Bearer JWT | 200, 400, 401, 404 |
| GET | `/workspaces/{id}/channels` | Bearer JWT | 200, 401, 403 |
| POST | `/workspaces/{id}/channels` | Bearer JWT | 201, 400, 401, 403, 409 |
| POST | `/channels/{id}/join` | Bearer JWT | 200, 401, 403, 404 |
| POST | `/channels/{id}/leave` | Bearer JWT | 200, 400, 401, 403, 404 |
| GET | `/channels/{id}/members` | Bearer JWT | 200, 401, 403, 404 |

## Database Models (`backend/app/features/workspaces_and_channels/models.py`)
- `Workspace`: `id`, `name`, `owner_id`, `created_at`
- `WorkspaceMember`: `workspace_id`, `user_id`, `role`, `joined_at`
- `WorkspaceInvite`: `id`, `workspace_id`, `token`, `created_by`, `expires_at`, `created_at`
- `Channel`: `id`, `workspace_id`, `name`, `description`, `created_by`, `created_at`
- `ChannelMember`: `channel_id`, `user_id`, `joined_at`

## Module Structure (`backend/app/features/workspaces_and_channels/`)
- `models.py`
- `schemas.py`
- `repository.py`
- `service.py`
- `routes.py`

## Dependencies (`backend/app/core/deps.py`)
- Implement `require_workspace_member(workspace_id, current_user, db)`
- Implement `require_channel_member(channel_id, current_user, db)`
