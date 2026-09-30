# Feature 01: Authentication — Specification

## Overview
User registration, login, and session management via JWT tokens. No SSO/2FA (out of scope).

## Acceptance Criteria

### AC-01-01: Signup validation and unique email
- `POST /auth/signup` accepts `{name, email, password}`.
- Validates: name 1–100 chars, valid email format, password ≥ 8 chars.
- Returns 201 with `{access_token, token_type: "bearer", user}`.
- `avatar_color` is assigned deterministically from a hash of the email against a fixed palette.
- Duplicate email returns 409 `email_taken`.

### AC-01-02: Login returns JWT, wrong credentials return 401
- `POST /auth/login` accepts `{email, password}`.
- On success returns 200 with `{access_token, token_type: "bearer", user}`.
- JWT expires after `JWT_EXPIRES_MINUTES` (default 10080 = 7 days).
- Wrong password or nonexistent email returns 401 `invalid_credentials`.

### AC-01-03: GET /auth/me returns profile with avatar_color
- `GET /auth/me` with valid Bearer token returns the user's `{id, name, email, avatar_color, created_at}`.
- The `avatar_color` is a hex string from the deterministic palette.

### AC-01-04: Protected routes reject unauthenticated requests
- Any endpoint requiring auth returns 401 when no token or an invalid/expired token is provided.
- After logout (client removes the JWT from localStorage), the user cannot access protected pages or endpoints.
