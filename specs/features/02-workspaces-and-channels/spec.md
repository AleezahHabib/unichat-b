# Feature 02: Workspaces and Channels — Specification

## Overview
Workspaces are isolated containers for team communication. Each workspace contains channels, members, and invites.

## Acceptance Criteria

### AC-02-01: Workspace creation and default #general channel
- `POST /workspaces` accepts `{name}`.
- Creates workspace with `owner_id = current_user.id`.
- Automatically creates `#general` channel in that workspace.
- Automatically adds creator as `owner` member in `workspace_members` and as member in `channel_members` for `#general`.
- Returns 201 with `{id, name, owner_id, created_at}`.

### AC-02-02: Workspace listing and membership details
- `GET /workspaces` returns array of workspaces the current user is a member of with `{id, name, owner_id, created_at, member_count}`.
- `GET /workspaces/{id}/members` returns list of members in the workspace with `{id, user_id, name, email, avatar_color, role, joined_at, online}`.
- Non-members attempting to access workspace details receive 403 `forbidden`.

### AC-02-03: Workspace invites (generation and acceptance)
- `POST /workspaces/{id}/invites` is restricted to workspace owner. Returns invite object with token and 7-day `expires_at`. Non-owners receive 403 `forbidden`.
- `GET /invites/{token}` (unauthenticated) returns `{workspace_name, inviter_name, expires_at, is_expired}`.
- `POST /invites/{token}/accept` adds authenticated user to `workspace_members` (strictly as `member`, never as `owner`) and to `#general` `channel_members`. Is idempotent (re-accepting returns success). Returns 200 with `{workspace_id}`.

### AC-02-04: Channel creation and naming rules
- `POST /workspaces/{id}/channels` accepts `{name, description}`. Requires workspace membership.
- Normalizes `name` to lowercase kebab-case (alphanumeric and hyphens only).
- Unique `(workspace_id, name)`. Duplicate name in same workspace returns 409 `channel_exists`.
- Returns 201 with channel details.
- `GET /workspaces/{id}/channels` lists all channels in the workspace.

### AC-02-05: Joining, leaving, and listing channel members
- `POST /channels/{id}/join` adds current user to `channel_members`. Idempotent.
- `POST /channels/{id}/leave` removes user from `channel_members`. Attempting to leave `#general` returns 400 `cannot_leave_general`.
- `GET /channels/{id}/members` lists members of the channel.

### AC-02-06: Workspace deletion
- `DELETE /workspaces/{id}` deletes the workspace and cascades deletion of channels, members, messages, and connected platform links.
- Restricted to workspace owner (`owner_id == current_user.id`). Non-owners receive 403 `forbidden`.
- Non-existent workspace returns 404 `workspace_not_found`.
- Returns 200 `{"status": "ok"}`.

