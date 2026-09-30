# Feature 01: Authentication — Plan

## Endpoints
| Method | Path | Auth | Status Codes |
|---|---|---|---|
| POST | `/auth/signup` | No | 201, 400, 409 |
| POST | `/auth/login` | No | 200, 401 |
| GET | `/auth/me` | Bearer JWT | 200, 401 |

## Backend Files (`backend/app/features/authentication/`)
- `models.py` — SQLAlchemy `User` model mirroring `002_users_and_workspaces.sql`.
- `schemas.py` — `SignupRequest`, `LoginRequest`, `UserResponse`, `AuthResponse`.
- `repository.py` — `get_user_by_email()`, `get_user_by_id()`, `create_user()`.
- `service.py` — `signup()` (hash, avatar_color, uniqueness check), `login()` (verify), `get_profile()`.
- `routes.py` — FastAPI router mounted at `/auth`.

## Frontend Files (`frontend/src/features/authentication/`)
- `api.ts` — `signup()`, `login()`, `getMe()` calling the backend.
- `AuthProvider.tsx` — React context providing user state, token management.
- `useAuth.ts` — Hook exposing `user`, `login`, `signup`, `logout`, `isLoading`.
- `components/LoginForm.tsx` — Login form with inline error display.
- `components/SignupForm.tsx` — Signup form with inline error display.

## Frontend Pages
- `src/app/(auth)/login/page.tsx`
- `src/app/(auth)/signup/page.tsx`
- `src/app/(app)/workspaces/page.tsx` — placeholder showing user name + logout.

## Key Design Decisions
- `avatar_color` is derived deterministically from `md5(email.lower())` against a fixed 8-color palette. No randomness, no user choice.
- JWT `sub` claim holds the user UUID as a string.
- `get_current_user` dependency decodes the JWT and returns a dict with `sub` (user_id). Routes that need full user profile query the repository.
