# Feature 06: AI Assistant — Tasks

- [ ] Create `backend/app/features/ai_assistant/models.py`
- [ ] Create `backend/app/features/ai_assistant/schemas.py`
- [ ] Create `backend/app/features/ai_assistant/repository.py`
- [ ] Create `backend/app/features/ai_assistant/embeddings.py`
- [ ] Create `backend/app/features/ai_assistant/agents/` (agents & prompts)
- [ ] Create `backend/app/features/ai_assistant/service.py`
- [ ] Create `backend/app/features/ai_assistant/routes.py`
- [ ] Mount AI assistant router in `app/main.py`
- [ ] Update `specs/api/openapi.yaml` and regenerate `frontend/src/types/api.ts`
- [ ] Write `tests/test_ai_assistant.py` covering AC-06-01..AC-06-05
- [ ] Create frontend `src/features/ai-assistant/api.ts`
- [ ] Create components `AssistantChat.tsx`, `CitationChip.tsx`, `SummaryPanel.tsx`, `SummaryButton.tsx`, `DraftReplyButton.tsx`, `SearchResults.tsx`
- [ ] Create pages `/workspace/[workspaceId]/assistant/page.tsx` and `/workspace/[workspaceId]/search/page.tsx`
- [ ] Verify `pytest tests/test_ai_assistant.py`
