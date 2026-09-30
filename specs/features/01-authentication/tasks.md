# Feature 01: Authentication — Tasks

- [x] Create `backend/app/features/authentication/models.py`
- [x] Create `backend/app/features/authentication/schemas.py`
- [x] Create `backend/app/features/authentication/repository.py`
- [x] Create `backend/app/features/authentication/service.py`
- [x] Create `backend/app/features/authentication/routes.py`
- [x] Wire `deps.get_current_user` to decode JWT properly
- [x] Mount auth router in `app/main.py`
- [x] Update `specs/api/openapi.yaml` (signup path, 409 response)
- [x] Write `tests/test_authentication.py` covering AC-01-01..AC-01-04
- [x] Create frontend `src/features/authentication/api.ts`
- [x] Create frontend `src/features/authentication/AuthProvider.tsx`
- [x] Create frontend `src/features/authentication/useAuth.ts`
- [x] Create frontend `src/features/authentication/components/LoginForm.tsx`
- [x] Create frontend `src/features/authentication/components/SignupForm.tsx`
- [x] Create frontend `src/app/(auth)/login/page.tsx`
- [x] Create frontend `src/app/(auth)/signup/page.tsx`
- [x] Create frontend `src/app/(app)/workspaces/page.tsx` placeholder
- [x] Regenerate frontend types with `npm run types`
- [x] Run `pytest tests/test_authentication.py` — requires `backend/.env` with `TEST_DATABASE_URL`
- [x] Manual verification: signup, reload persistence, logout redirect, duplicate email error

