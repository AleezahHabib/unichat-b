# Feature 03: Messaging — Tasks

- [x] Create `backend/app/features/messaging/models.py`
- [x] Create `backend/app/features/messaging/schemas.py`
- [x] Create `backend/app/features/messaging/repository.py`
- [x] Create `backend/app/features/messaging/service.py`
- [x] Create `backend/app/features/messaging/routes.py`
- [x] Mount messaging router in `app/main.py`
- [x] Write `tests/test_messaging.py` covering AC-03-01..AC-03-04
- [x] Create frontend `src/features/messaging/api.ts`
- [x] Create frontend `src/features/messaging/useMessages.ts`
- [x] Create components: `MessageList`, `MessageItem`, `MessageComposer`, `ThreadPanel`
- [x] Create page `/workspace/[workspaceId]/channel/[channelId]/page.tsx`
- [ ] Verify `pytest tests/test_messaging.py`

- [x] Clear Chat For Me: `POST /channels/{id}/clear` (AC-03-07)
- [x] Outbound Relay background task resilience (Slack/Discord non-blocking)
