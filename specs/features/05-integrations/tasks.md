# Feature 05: Integrations — Tasks

- [x] Create `backend/app/features/integrations/models.py`
- [x] Create `backend/app/features/integrations/schemas.py`
- [x] Create `backend/app/features/integrations/repository.py`
- [x] Create `backend/app/features/integrations/echo_guard.py`
- [x] Create `backend/app/features/integrations/adapters/base.py`
- [x] Create `backend/app/features/integrations/adapters/slack_adapter.py`
- [x] Create `backend/app/features/integrations/adapters/discord_adapter.py`
- [x] Create `backend/app/features/integrations/service.py`
- [x] Create `backend/app/features/integrations/routes.py`
- [x] Create `backend/app/background/sync_external.py` with Redis leader lock
- [x] Update `/health` endpoint in `app/main.py` to report leader/follower/off status
- [x] Update `specs/api/openapi.yaml` and regenerate `frontend/src/types/api.ts`
- [x] Write `tests/test_integrations.py` covering AC-05-01..AC-05-08 with fakes
- [x] Create frontend `src/features/integrations/api.ts`
- [x] Create components `ConnectCard.tsx`, `SetupGuide.tsx`, `LinkChannelModal.tsx`, `PlatformBadge.tsx`
- [x] Create page `/workspace/[workspaceId]/settings/integrations/page.tsx`
- [x] Verify `pytest tests/test_integrations.py`
