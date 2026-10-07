# Feature 02: Workspaces and Channels — Tasks

- [x] Create `backend/app/features/workspaces_and_channels/models.py`
- [x] Create `backend/app/features/workspaces_and_channels/schemas.py`
- [x] Create `backend/app/features/workspaces_and_channels/repository.py`
- [x] Create `backend/app/features/workspaces_and_channels/service.py`
- [x] Create `backend/app/features/workspaces_and_channels/routes.py`
- [x] Update `backend/app/core/deps.py` for `require_workspace_member` and `require_channel_member`
- [x] Mount workspace & channel router in `app/main.py`
- [x] Write `tests/test_workspaces_and_channels.py` covering AC-02-01..AC-02-05
- [x] Create frontend `src/features/workspaces-and-channels/api.ts`
- [x] Create components: `WorkspacePicker`, `ChannelList`, `CreateChannelModal`, `BrowseChannelsModal`, `InviteCard`, `MemberList`
- [x] Create pages: `/workspaces`, `/workspace/[workspaceId]/layout.tsx`, `/workspace/[workspaceId]/page.tsx`, `/workspace/[workspaceId]/settings/members/page.tsx`, `/invite/[token]/page.tsx`
- [x] Implement `DELETE /workspaces/{workspace_id}` (owner-only deletion) & member count visibility
- [x] Verify invite acceptance explicitly joins as role `member`
- [ ] Verify `pytest tests/test_workspaces_and_channels.py`


- [x] Leave Workspace: `POST /workspaces/{id}/leave` (AC-02-07)
- [x] Remove Member: `DELETE /workspaces/{id}/members/{user_id}` (AC-02-08)
