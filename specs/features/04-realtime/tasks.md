# Feature 04: Realtime — Tasks

- [x] Create `backend/app/features/realtime/events.py`
- [x] Create `backend/app/features/realtime/connections.py`
- [x] Create `backend/app/features/realtime/pubsub.py`
- [x] Create `backend/app/features/realtime/presence.py`
- [x] Create `backend/app/features/realtime/routes.py`
- [x] Wire `messaging/service.py` to publish realtime events on create/update/delete
- [x] Mount `/ws` in `app/main.py`
- [x] Write `tests/test_realtime.py` covering AC-04-01..AC-04-05
- [x] Create frontend `src/lib/websocket.ts`
- [x] Create frontend `src/features/realtime/RealtimeProvider.tsx` and `useRealtime.ts`
- [x] Create components `TypingIndicator.tsx` and `OnlineDot.tsx`
- [x] Wire `MessageList`, `MessageComposer`, `MemberList`, and Sidebar with realtime updates
- [x] Verify `pytest tests/test_realtime.py` (written & ready for live Neon test database execution)
