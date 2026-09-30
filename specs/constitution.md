# UniChat Engineering Constitution

## 1. Core Principles & Philosophy
UniChat is built spec-first, robust, clean, and free of vendor lock-in. Every line of implementation code flows directly from documented requirements, formal OpenAPI contracts, and testable acceptance criteria.

1. **Free to Run**: Zero paid API dependencies. The sole external intelligence engine is Google Gemini using a free API key from Google AI Studio.
2. **Containerless Simplicity**: No Docker in development, CI, or deployment. The system runs cleanly on bare metal (Windows, macOS, Linux) with Python 3.11+ and Node 20+.
3. **Managed Cloud Infrastructure**:
   - Frontend: Vercel
   - Backend: Railway
   - Database: Neon PostgreSQL with `pgvector`
   - Cache / Realtime pub/sub: Upstash Redis
4. **Architectural Separation of Concerns**: Strict layering prevents spaghetti code.
   - Routes: Pure HTTP handling, status codes, and schema validation. Never call the database directly.
   - Services: Business rules, permissions, platform coordination, rate limits.
   - Repositories: Encapsulated SQL statements and database transactions.
5. **No Scope Creep**: Out-of-scope capabilities (SSO/2FA, video/voice, private DMs, file uploads, Microsoft Teams engine) are strictly avoided.
6. **Zero Secrets in Code**: Secrets reside exclusively in `.env` (backend) and `.env.local` (frontend), both git-ignored. Real tokens and webhook URLs are stored at rest using Fernet symmetric encryption and never returned in API payloads.

---

## 2. Cross-Platform Rigor
1. Paths must always use Python's `pathlib.Path` or POSIX-standard forward slashes in TypeScript. Never hardcode Windows backslashes `\` or OS-specific shells.
2. All build scripts must run through `npm run ...` or `python scripts/...`. Never introduce bash-only shell scripts or Makefiles.

---

## 3. Strict Backend Layering (The 5-File Rule)
Every backend feature under `backend/app/features/<feature_name>/` must contain exactly five files:
- `routes.py`: FastAPI endpoint routers. Handles request parsing, response serialization, and HTTP status codes.
- `schemas.py`: Pydantic v2 schemas for request bodies, query params, and serialized responses.
- `models.py`: SQLAlchemy 2.0 declarative database models.
- `service.py`: Business logic, authorization assertions, cryptographic transforms, external API calls.
- `repository.py`: Async SQLAlchemy database access, joins, queries, and vector similarity operations.

---

## 4. Frontend Standards
1. Next.js 15 App Router with React 19 and TypeScript in strict mode.
2. Styling strictly governed by Tailwind CSS v4 and the "Skyline" design tokens.
3. No arbitrary color classes. Consistent font hierarchy using Bricolage Grotesque and Geist Sans/Mono.
4. Rich interactive experience: responsive micro-interactions, accessible keyboard navigation, tab switching with ARIA standards, and strict reduction of autonomous motions when `prefers-reduced-motion` is active.

---

## 5. Unified Data Strategy
All conversational events—UniChat native messages, Slack events, Discord webhooks—live in the single `messages` table. This is non-negotiable as it guarantees unified timelines, single-query cursor pagination, single-vector-table semantic search, and robust deduplication via partial unique indexing.
