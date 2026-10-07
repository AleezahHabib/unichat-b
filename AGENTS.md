# AGENTS.md — UniChat

> Read this file before every task in this repository, in every session, even
> if a chat prompt already repeats part of it. This file is the persistent
> source of truth; a chat prompt only ever adds phase-specific instructions on
> top of what's here — it never overrides the rules below.

---

## 1. Hard constraints — never violate these

- **Free only.** The only AI provider is **Google Gemini** through a free
  Google AI Studio API key. Never add OpenAI or any other paid API, even as
  an optional fallback.
- **No Docker.** Not for development, not for deployment. Ever.
- **Hosting:** frontend on **Vercel**, backend on **Railway**, database on
  **Neon** (Postgres + pgvector), Redis on **Upstash**. Local development uses
  the SAME Neon and Upstash instances as production — never suggest
  installing Postgres or Redis locally.
- **Cross-platform.** The developer may be on Windows. Use Python or npm
  scripts for every task. Never write a bash-only script or a Makefile. Use
  `pathlib` for paths in Python.
- **Never commit secrets.** Real values live only in `backend/.env` and
  `frontend/.env.local`, both git-ignored. Never print a real key back in
  chat or a file.
- **No mock data in production code paths.** `backend/scripts/seed.py` is the
  one exception.
- **Protect the free tiers.** No busy-polling loops against Redis (Upstash's
  free tier has a monthly command cap). Every Gemini call goes through the
  shared limiter in `core/rate_limit.py`.

---

## 2. Sync rule — specs and code must never drift

This project is spec-driven: `spec.md` → `plan.md` → `tasks.md` → code →
tests, in that order, for every feature. That order applies to *changes* just
as much as it applies to new work. **Whenever you change anything in this
project — in this session or a future one, whether I asked for a new feature,
a bug fix, a refactor, or a small tweak — you must also update every spec
artifact that describes the thing you changed, in the same turn, before you
report the task as done.** Do not wait to be asked. Do not treat this as
optional cleanup for later.

Use this table to know what else to touch:

| If you change... | You must also update... |
|---|---|
| A REST endpoint, request/response shape, or status code | `specs/api/openapi.yaml`; the owning feature's `spec.md` (if behavior changed) and `plan.md` (endpoint list); regenerate frontend types with `npm run types` |
| A WebSocket event, its payload, or the connection protocol | `specs/api/events.md` |
| A database table, column, index, or constraint | A **new** migration file in `backend/db/migrations/` (never edit an applied one); `database/README.md`; `database/diagram.md`; the owning feature's `plan.md` |
| Any acceptance criterion or observable behavior | That feature's `spec.md` **first**, then `plan.md`, then the code and its tests — same order as a brand-new feature |
| A component, page, hook, or file added/renamed/removed in `frontend/src/` or `backend/app/` | The folder structure in section 6 of this file; the owning feature's `plan.md` |
| A design token, font, spacing rule, or motion rule | `specs/design/design-system.md` |
| An environment variable | `backend/.env.example` or `frontend/.env.example` (with a one-line comment) and the README's setup section |
| A task's status, or a new task | That feature's `tasks.md` (`- [x]` / add the new line) |
| A library, version, or the stack itself | The stack table in section 7 of this file, and `specs/constitution.md` |
| A completely new feature | Create `specs/features/NN-kebab-case-name/` (spec, plan, tasks) **before** writing any of its code — number continues from the highest existing feature |

**Before reporting any task as finished**, do a short spec-drift check: look
back at what you actually changed and confirm every row above that applies
has been handled. If you find something out of sync, fix it silently as part
of finishing the task — don't ask permission, don't defer it — then mention
in your report which spec files you updated as a result.

Two exceptions:
- **Never edit an applied migration file.** A schema change is always a new
  migration, numbered next in sequence, applied via `python -m scripts.migrate`.
- **If a requested change would contradict a hard constraint (section 1) or
  an existing acceptance criterion, stop and ask** instead of silently
  changing scope or silently rewriting the acceptance criterion to fit.

---

## 3. Process

- Build only what's asked for in the current phase or task. Never start a
  phase I haven't asked for.
- Spec-driven order for anything new: `spec.md` → `plan.md` → `tasks.md` →
  code → tests. Tick tasks in `tasks.md` as you finish them.
- At the end of a phase or a significant task: run the verification steps
  given, apply the sync-drift check above, report what was built/changed and
  verified, then stop and wait for confirmation before continuing.
- If a chat prompt conflicts with this file, point out the conflict instead
  of silently picking one side.
- If a library's real current API differs from what this file or a prompt
  assumed (`openai-agents`, `google-genai`, `slack_sdk`, Next.js 15,
  Tailwind v4, Railway's config format), use the library's actual current
  API and note the difference in your report — don't force code to match an
  outdated assumption, and update this file's relevant section if the
  difference is significant enough to matter for future sessions.

---

## 4. Product blueprint

**UniChat** — a unified team chat app. Users chat in workspaces and channels,
like Slack. A UniChat channel can be linked to a Slack channel and/or a
Discord channel so messages flow **both ways**. An AI assistant summarizes
channels, answers questions with **cited source messages**, drafts replies,
and searches by meaning across all three sources. Tagline: **"Chat. Connect.
Ask."**

### Scope

| In scope | Out of scope |
|---|---|
| Marketing landing page (light + dark) | SSO, 2FA, Slack/Discord OAuth app distribution |
| Sign up, log in, log out (JWT) | Voice/video, mobile app |
| Workspaces, invite links, public channels, join/leave | Private channels, DMs |
| Messages: send, edit, delete, threads | File uploads |
| Realtime: live delivery, typing indicator, presence | Admin analytics, audit logs |
| Slack two-way sync (Socket Mode) | Microsoft Teams (adapter-ready folder, not built) |
| Discord two-way sync (polling + webhook) | Syncing edits/deletes made in Slack/Discord back into UniChat |
| AI: summarize, ask with citations, draft reply, semantic search | Fine-tuning, any second AI provider |

---

## 5. Architecture

```
Browser (Vercel)  ──REST──►  FastAPI (Railway, 1 replica) ──► Neon Postgres + pgvector
       ▲                          │    │                  ──► Upstash Redis (pub/sub, presence, rate limits, leader lock)
       └────────WebSocket─────────┘    ├── Slack Socket Mode clients (outbound WebSocket, no public URL needed)
                                       ├── Discord poller + webhooks (REST)
                                       └── Gemini API (Agents SDK via OpenAI-compatible endpoint; google-genai for embeddings)
```

**Message flow:**
1. `POST /channels/{id}/messages` → service validates membership + rate limit → repository saves to Postgres.
2. Service calls `realtime.pubsub.publish(workspace_id, "message.created", payload)` → Redis pub/sub → every backend process delivers it to its connected browsers in that workspace.
3. If the channel has links, `integrations.service.relay_outbound(message)` runs as a background task: the adapter posts it to Slack/Discord and the returned external ID is saved on the message.
4. The message ID goes on the in-process embedding queue; the worker embeds it via Gemini. A sweep every 60s catches anything missed.

**Background jobs and scaling:** Slack Socket Mode, the Discord poller, and the embedding sweep must run in exactly one process. `core/leader.py` takes a Redis lock (`SET unichat:leader <id> NX EX 30`, renewed every 10s). Only the leader starts those jobs. WebSockets and pub/sub work on every replica.

**Graceful degradation:** if `GEMINI_API_KEY` is empty, chat and integrations work normally, `/search` falls back to keyword search (`ILIKE`), and AI endpoints return `503 {"code":"ai_disabled"}`.

---

## 6. Folder structure — the target shape of the repo

Keep the repo matching this shape. If section 2's sync rule adds/removes a
file, update this section too.

```
unichat/
├── README.md
├── AGENTS.md                     # this file
├── UNICHAT_BUILD_PROMPT.md
├── .gitignore
├── scripts/trace.py               # AC IDs in specs + test names → specs/traceability.md
│
├── specs/
│   ├── constitution.md
│   ├── overview.md
│   ├── glossary.md
│   ├── traceability.md            # generated by scripts/trace.py
│   ├── design/design-system.md
│   ├── api/openapi.yaml
│   ├── api/events.md
│   └── features/
│       ├── 01-authentication/            spec.md plan.md tasks.md
│       ├── 02-workspaces-and-channels/   spec.md plan.md tasks.md
│       ├── 03-messaging/                 spec.md plan.md tasks.md
│       ├── 04-realtime/                  spec.md plan.md tasks.md
│       ├── 05-integrations/              spec.md plan.md tasks.md
│       ├── 06-ai-assistant/              spec.md plan.md tasks.md
│       └── 07-landing-page/              spec.md plan.md tasks.md   # + evidence.md (Lighthouse)
│
├── database/
│   ├── README.md                  # every table in plain English + "why one messages table"
│   └── diagram.md                 # Mermaid erDiagram
│
├── backend/                       # Railway service root
│   ├── README.md
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── railway.json
│   ├── .python-version            # 3.11
│   ├── .env.example
│   ├── db/migrations/             # 001..007, see section 8
│   ├── scripts/
│   │   ├── migrate.py             # applies unapplied migrations, tracked in schema_migrations
│   │   ├── seed.py                # demo workspace/users/messages
│   │   └── check_ai.py            # one Gemini chat call + one embedding call
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_authentication.py
│   │   ├── test_workspaces_and_channels.py
│   │   ├── test_messaging.py
│   │   ├── test_realtime.py
│   │   ├── test_integrations.py
│   │   ├── test_ai_assistant.py
│   │   └── test_contract.py       # app.openapi() == specs/api/openapi.yaml
│   └── app/
│       ├── main.py                # app factory, CORS, routers, GET /health, lifespan
│       ├── core/
│       │   ├── config.py          # Settings + normalize_database_url()
│       │   ├── database.py        # async engine (SSL for Neon), session factory, Base, get_db
│       │   ├── redis.py           # redis client (rediss:// for Upstash), get_redis
│       │   ├── security.py        # bcrypt, JWT, Fernet
│       │   ├── deps.py            # get_current_user, require_workspace_member, require_channel_member
│       │   ├── errors.py          # AppError + handler → {"detail","code"}
│       │   ├── rate_limit.py      # Redis fixed-window limiter (per-user + global AI budget)
│       │   └── leader.py          # Redis lock, one leader process
│       ├── features/
│       │   ├── authentication/            routes schemas models service repository
│       │   ├── workspaces_and_channels/   routes schemas models service repository
│       │   ├── messaging/                 routes schemas models service repository
│       │   ├── realtime/
│       │   │   ├── routes.py  events.py  connections.py  pubsub.py  presence.py
│       │   ├── integrations/
│       │   │   ├── routes.py schemas.py models.py service.py repository.py
│       │   │   ├── echo_guard.py
│       │   │   └── adapters/  base.py  slack_adapter.py  discord_adapter.py
│       │   └── ai_assistant/
│       │       ├── routes.py schemas.py models.py service.py repository.py
│       │       ├── embeddings.py
│       │       └── agents/
│       │           ├── model_provider.py  context.py  assistant_agent.py
│       │           ├── summarizer_agent.py  qa_agent.py  drafter_agent.py
│       │           ├── tools.py  guardrails.py
│       │           └── instructions/  assistant.md summarizer.md qa.md drafter.md
│       └── background/  embed_worker.py  sync_external.py
│
└── frontend/                      # Vercel project root
    ├── README.md
    ├── package.json               # scripts: dev build start types test:e2e
    ├── tsconfig.json  next.config.ts  postcss.config.mjs  playwright.config.ts
    ├── .env.example                # NEXT_PUBLIC_API_URL, NEXT_PUBLIC_WS_URL, NEXT_PUBLIC_REPO_URL
    ├── public/                     # logo.svg favicon.svg og.svg — original artwork
    ├── tests/e2e/demo.spec.ts
    └── src/
        ├── app/
        │   ├── layout.tsx  globals.css  not-found.tsx
        │   ├── (marketing)/page.tsx          # landing page at "/"
        │   ├── privacy/page.tsx  terms/page.tsx
        │   ├── (auth)/login/page.tsx  signup/page.tsx
        │   ├── invite/[token]/page.tsx
        │   └── (app)/
        │       ├── workspaces/page.tsx
        │       └── workspace/[workspaceId]/
        │           ├── layout.tsx  page.tsx
        │           ├── channel/[channelId]/page.tsx
        │           ├── assistant/page.tsx  search/page.tsx
        │           └── settings/members/page.tsx  settings/integrations/page.tsx
        ├── features/
        │   ├── landing/components/    # Navbar Hero HeroTabs SyncDemo PlatformStrip HowItWorks
        │   │                          # FeatureGrid AssistantShowcase IntegrationsHub SpecFirst Faq FinalCta Footer
        │   ├── authentication/        # api.ts AuthProvider.tsx useAuth.ts components/{LoginForm,SignupForm}
        │   ├── workspaces-and-channels/ # api.ts components/{WorkspacePicker,ChannelList,CreateChannelModal,BrowseChannelsModal,InviteCard,MemberList,WorkspaceSettingsModal}
        │   ├── messaging/              # api.ts useMessages.ts components/{MessageList,MessageItem,MessageComposer,ThreadPanel}
        │   ├── realtime/               # RealtimeProvider.tsx useRealtime.ts components/{TypingIndicator,OnlineDot}
        │   ├── integrations/           # api.ts components/{ConnectCard,LinkChannelModal,PlatformBadge,SetupGuide}
        │   └── ai-assistant/           # api.ts components/{AssistantChat,CitationChip,SummaryPanel,SummaryButton,DraftReplyButton,SearchResults}
        ├── components/ui/    # Button Input Textarea Modal Avatar Badge Spinner Tabs Toast ThemeToggle EmptyState
        ├── components/layout/ # Sidebar TopBar
        ├── lib/               # api-client.ts websocket.ts theme.ts format.ts utils.ts
        └── types/api.ts       # GENERATED from specs/api/openapi.yaml, never hand-edited
```

---

## 7. Stack (exact — do not substitute libraries)

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 (App Router) + React 19 + TypeScript strict + Tailwind CSS v4 |
| Frontend libs (only these) | `motion`, `lucide-react`, `clsx`, `geist` (local), `@fontsource-variable/bricolage-grotesque` (local); dev: `openapi-typescript`, `@playwright/test` |
| Backend | Python 3.11, FastAPI, Uvicorn, Pydantic v2, pydantic-settings |
| Database access | SQLAlchemy 2.0 async + asyncpg + `pgvector` python package |
| Redis | `redis` (redis.asyncio); tests use `fakeredis` |
| Security | `bcrypt`, `PyJWT`, `cryptography` (Fernet) |
| Integrations | `slack_sdk` + `aiohttp` (Slack Socket Mode), `httpx` (Discord REST) |
| AI agents | `openai-agents` (OpenAI Agents SDK), pointed at Gemini's OpenAI-compatible endpoint |
| Embeddings | `google-genai`, model `gemini-embedding-001`, 768 dimensions |
| Tests | `pytest`, `pytest-asyncio`, `httpx`, `fakeredis`; Playwright for one e2e test |
| Hosting | Vercel (frontend), Railway (backend), Neon (Postgres+pgvector), Upstash (Redis) |

Fonts come from npm packages, never Google Fonts at build time.

### Naming
- Feature folders: **kebab-case** in `specs/features/` and `frontend/src/features/`; **snake_case** in `backend/app/features/` (`workspaces-and-channels` ↔ `workspaces_and_channels`). Feature numbers (`01-`…`07-`) exist only in `specs/features/`.
- Python: `snake_case` files/functions, `PascalCase` classes. TypeScript: `PascalCase.tsx` components, `camelCase.ts` hooks/helpers, hooks start with `use`.
- REST paths are plural nouns; JSON fields are `snake_case` on the wire.

### Backend rules
- Every feature module has exactly five files: `routes.py` (HTTP only), `schemas.py`, `models.py`, `service.py`, `repository.py`. Routes never touch the DB directly; repositories never hold business rules.
- `backend/db/migrations/*.sql` is the source of truth for the schema. SQLAlchemy models mirror it. Never call `Base.metadata.create_all()`.
- Every error returns `{"detail": "...", "code": "..."}` with the correct HTTP status.
- Type hints everywhere; `logging`, never `print`. Features call each other only through the other's `service.py`.

### Frontend rules
- Pages in `src/app/` stay thin and compose feature components.
- All HTTP goes through `src/lib/api-client.ts`; the only WebSocket lives in `src/lib/websocket.ts`.
- All API types come from `src/types/api.ts`, generated via `npm run types`. Never hand-edit it.
- Colors only through design tokens (section 11). No hex values in components except the Slack/Discord badge colors.
- Every interactive element is keyboard reachable with a visible focus ring; respect `prefers-reduced-motion`.
- No `localStorage` except the JWT and the theme choice.

### Testing rules
- Every acceptance criterion (section 12) has at least one test whose name contains its ID, e.g. `test_AC_05_05_no_echo_from_own_bot`.
- One backend test file per feature, plus `test_contract.py`.
- Backend tests use `TEST_DATABASE_URL` (a Neon database whose name must end in `_test` — tests refuse to run otherwise). Redis in tests is `fakeredis`. Gemini, Slack and Discord are always faked in tests.
- `python scripts/trace.py` must report 100% of acceptance criteria covered.

---

## 8. Database schema (12 tables) — ground truth

The SQL migrations are the source of truth; SQLAlchemy models mirror them.
A schema change is always a **new** migration file (never edit an applied
one) plus updates to `database/README.md` and `database/diagram.md` (sync rule).

```
users(id, name, email UNIQUE, password_hash, avatar_color, created_at)
workspaces(id, name, owner_id→users, created_at)
workspace_members(workspace_id, user_id, role owner|member, joined_at)
workspace_invites(id, workspace_id, token UNIQUE, created_by, expires_at, created_at)
channels(id, workspace_id, name, description, created_by, created_at, UNIQUE(workspace_id,name))
channel_members(channel_id, user_id, joined_at)
messages(id, channel_id, author_id NULLABLE→users, external_author_name, parent_id
  self-ref, body TEXT ≤4000, source unichat|slack|discord, external_id,
  external_channel_id, created_at, edited_at, deleted_at)
  — UNIQUE INDEX on (external_channel_id, external_id) WHERE external_id IS NOT NULL
  — external authors have no UniChat user; author_id is nullable, external_author_name
    carries their name. Storing external messages in the SAME table as native ones
    is why search and AI work across all platforms without extra effort.
connected_platforms(id, workspace_id, platform slack|discord, encrypted_tokens,
  bot_identity, display_name, created_at, UNIQUE(workspace_id,platform))
channel_links(id, channel_id, platform_id→connected_platforms, platform,
  external_channel_id, external_channel_name, encrypted_webhook_url NULLABLE
  [Discord], webhook_id NULLABLE, last_synced_external_id, created_at,
  UNIQUE(channel_id,platform), UNIQUE(platform,external_channel_id))
message_embeddings(message_id PK→messages, embedding vector(768), model,
  created_at) — HNSW index, vector_cosine_ops
assistant_chats(id, user_id, workspace_id, session_id, role user|assistant,
  content, citations JSONB, created_at)
channel_user_clears(user_id→users, channel_id→channels, cleared_at,
  PRIMARY KEY(user_id, channel_id))
```

Migration files, in order: `001_enable_pgvector.sql` (extensions vector,
pgcrypto), `002_users_and_workspaces.sql`, `003_channels_and_messages.sql`,
`004_integrations.sql`, `005_ai_assistant.sql`, `006_multiple_channel_links.sql`,
`007_restore_single_channel_links.sql`, `008_channel_user_clears.sql`.

---

## 9. REST API contract — ground truth (full detail in `specs/api/openapi.yaml`)

All endpoints need `Authorization: Bearer <jwt>` except signup/login/health/
invite-preview.

| Method + path | Notes |
|---|---|
| `GET /health` | `{status, database, redis, ai: enabled|disabled, background: leader|follower|off}` |
| `POST /auth/signup` / `POST /auth/login` / `GET /auth/me` | JWT 24h; 409 `email_taken`; 401 `invalid_credentials` |
| `GET/POST /workspaces` | Creating makes `#general` + creator is owner+member |
| `GET /workspaces/{id}/members` | `online` from Redis presence |
| `POST /workspaces/{id}/invites` | Owner only; 7-day expiry |
| `POST /workspaces/{id}/leave` | Removes user from workspace & all channels; owner cannot leave (403) |
| `DELETE /workspaces/{id}/members/{user_id}` | Owner only; removes member from workspace & all channels |
| `GET /invites/{token}` / `POST /invites/{token}/accept` | No auth on GET; accept is idempotent |
| `GET/POST /workspaces/{id}/channels` | Name normalized, unique per workspace |
| `POST /channels/{id}/join` / `leave` | Can't leave `#general` |
| `GET /channels/{id}/members` | |
| `GET/POST /channels/{id}/messages` | Cursor pagination, 50/page, newest first; 30/min/user → 429 `rate_limited` |
| `PATCH/DELETE /messages/{id}` | Author-only; UniChat-source only; soft delete |
| `POST /channels/{id}/clear` | Hides channel message history for current user only (purely local) |
| `GET/POST /messages/{id}/thread` | Replies oldest-first |
| `GET /integrations?workspace_id=` | Tokens never returned |
| `GET /integrations/slack/oauth/start?workspace_id=` | Owner only; creates state in Redis, 302 redirect to Slack |
| `GET /integrations/slack/oauth/callback?code=&state=` | Validates state, exchanges code, encrypts tokens, redirects |
| `POST /integrations/slack/connect` (bot_token, app_token) | Owner only; validated via `auth.test` |
| `POST /integrations/discord/connect` (bot_token) | Owner only; validated via `GET /users/@me` |
| `DELETE /integrations/{id}` | Stops listener/poller, removes links |
| `GET /integrations/{id}/external-channels` | Live list from the platform |
| `POST/DELETE /channels/{id}/link` | 1:1 per platform |
| `POST /assistant/chat` / `GET /assistant/history` | 10/min/user |
| `POST /assistant/summarize` (channel_id, since_hours) | One Gemini request |
| `POST /assistant/draft-reply` (message_id) | Never sends automatically |
| `GET /search` (workspace_id, q, limit) | Semantic, keyword fallback |

AI endpoints can also return `503 ai_disabled` (no key) or `503 ai_busy`
(`retry_after_seconds`).

## 10. WebSocket contract — ground truth (full detail in `specs/api/events.md`)

`GET /ws`. Client sends `{"type":"auth","token":...}` first, within 5s (else
close code 4401), then `{"type":"ping"}` every 25s and `{"type":"typing",
"channel_id"}` throttled to 1/2s. Server sends
`{"type","workspace_id","channel_id","data","ts"}` envelopes for: `ready`,
`message.created`, `message.updated`, `message.deleted`, `thread.reply`,
`typing`, `presence.update`, `pong`. One Redis subscriber per process on
`PSUBSCRIBE unichat:ws:*`, channel `unichat:ws:{workspace_id}`. Presence key
`unichat:presence:{user_id}` TTL 60s, refreshed on connect/ping.

---

## 11. Integrations design — ground truth

**Slack** (Socket Mode — no public URL needed): app manifest scopes
`channels:history channels:read channels:join chat:write chat:write.customize
users:read`, `socket_mode_enabled: true`. Adapter: `list_channels` via
`conversations.list`; join on link; `send()` via `chat.postMessage` with
`username="<Name> (via UniChat)"` and `thread_ts` when the parent maps to
this channel; a `SocketModeClient` listener resolves sender names via
`users.info` (10-min cache), maps `thread_ts≠ts` to `parent_id`.

**Discord** (bot token, polling + webhooks): requires **Message Content
Intent** enabled in the Developer Portal. Adapter: `list_channels` via guilds
+ channels; on link, create a webhook, store it encrypted, set
`last_synced_external_id` to skip old history; `send()` posts to the webhook
with a `"↪ replying to…"` prefix for thread replies; a poller runs every
`DISCORD_POLL_SECONDS` using `?after=<cursor>`, sleeping on 429.

**Echo guard** (`echo_guard.py`), three layers — this is what prevents
infinite loops and duplicates:
1. Identity filter: ignore events whose `bot_id`/`webhook_id`/author id
   matches our own.
2. Database uniqueness: `INSERT ... ON CONFLICT DO NOTHING` on the
   `(external_channel_id, external_id)` unique index — the hard backstop.
3. Race window: a 30s Redis key per outbound message catches the echo
   arriving before `send()` returns.

Outbound relay only ever runs for `source='unichat'` messages — never
re-post an inbound message back to its own platform — but a Slack-sourced
message DOES relay to a Discord link on the same channel, and vice versa.

## 12. AI design — ground truth (Gemini, free tier)

Gemini exposes an OpenAI-compatible endpoint at
`https://generativelanguage.googleapis.com/v1beta/openai/`; the OpenAI Agents
SDK's `OpenAIChatCompletionsModel` works against it with a normal AI Studio
key (`set_tracing_disabled(True)` — tracing would upload to OpenAI, which we
don't use).

**Agents:** `assistant_agent` (triage, hands off to `summarizer_agent` /
`qa_agent`, input guardrail, tool `list_channels`), `summarizer_agent`
(`output_type=SummaryOutput`, tools `list_channels`+`get_channel_history`),
`qa_agent` (`output_type=AnswerOutput{answer, citation_ids}`, tools
`search_messages`+`get_thread`+`get_channel_history`), `drafter_agent` (no
tools — context prefetched by the service, one Gemini call per draft).

**Security boundary:** every tool receives the run context's
`allowed_channel_ids` (the channels the user has JOINED, loaded fresh per
run) and filters every DB query by it — this is the real security boundary,
not the guardrails. `get_channel_history` on an unknown OR non-joined channel
returns the identical "You don't have access to that channel or it doesn't
exist." message either way, so existence isn't leaked.

**Guardrails** (`guardrails.py`, deterministic, no extra Gemini calls):
`scope_and_injection_guardrail` (input — trips on injection phrasing or a
channel name outside `allowed_channel_ids`, becomes a plain "I can only use
channels you've joined" reply); `citation_guardrail` (output — retries once
without a citation not in `seen_message_ids`, then strips citations and logs
a warning).

**Rate limiting:** a global `AI_REQUESTS_PER_MINUTE` budget (default 8)
across the whole app plus a per-user chat limit (10/min); over budget → 503
`ai_busy` with `retry_after_seconds`; retry once on HTTP 429 after the
suggested delay (max 10s) before giving up.

**Embeddings:** `google-genai`, `gemini-embedding-001`,
`output_dimensionality=768` (pgvector HNSW supports at most 2000 dims),
L2-normalized, `task_type` `RETRIEVAL_DOCUMENT`/`RETRIEVAL_QUERY`. Embed
`"#<channel> <author>: <body>"`. Search: cosine distance over
`message_embeddings`, filtered to the user's joined channels, falls back to
`ILIKE` keyword search if AI is disabled or the embedding call fails.

---

## 13. Design system — ground truth ("Skyline", full detail in `specs/design/design-system.md`)

Inspired by cap.so's bright, airy, confident feel — never a copy of its
assets, text, or layouts.

| Token | Light | Dark | Use |
|---|---|---|---|
| `bg` | #F6F9FF | #070B16 | Page background |
| `surface` | #FFFFFF | #0E1424 | Cards, windows |
| `surface-2` | #EEF3FC | #151D31 | Sidebar, inputs |
| `border` | #DDE5F2 | #22304A | Hairlines |
| `ink` | #0B1324 | #E8EEFA | Main text |
| `ink-muted` | #5A6A85 | #8C9AB5 | Secondary text |
| `primary` | #2F6BFF | #5B8CFF | Actions |
| `ai` | #7C5CFF | #9B84FF | Everything AI |
| `live` | #16C79A | #2EE0AE | Online/synced |
| `danger` | #E5484D | #FF6B6F | Destructive |
| `sky-top` | #DCE9FF | #0B1733 | Hero gradient top |

Platform badges only: Slack #4A154B, Discord #5865F2, white text.

Type: Bricolage Grotesque (display/headlines), Geist Sans (UI/body), Geist
Mono (code/terminal). Scale 14/16/18/22/28/40/64px (hero 72px desktop/44px
mobile). Radius 10px controls/14px cards/18px product windows. Motion
150–250ms ease-out on user-triggered changes; the only autonomous animation
anywhere is one hero sync-demo loop, which shows a static final frame under
`prefers-reduced-motion`.

Avoid: ALL-CAPS eyebrow labels, accenting one word of a headline, arrows
appended to buttons/links, middle-dot-joined meta strings, fade-slide-up on
every section, identical-shadow card grids, decorative gradient washes
outside the sky and AI elements.

---

## 14. Acceptance criteria — ground truth (full detail in each feature's `spec.md`)

Every test name must contain its ID. `python scripts/trace.py` checks this.

**01 Authentication:** AC-01-01 signup validation+unique email · AC-01-02
login→JWT, wrong creds 401 · AC-01-03 `/auth/me` returns profile+avatar_color
· AC-01-04 protected routes 401 without token, logout clears it.

**02 Workspaces/channels:** AC-02-01 create workspace→`#general`+owner ·
AC-02-02 only owner invites, 7-day expiry · AC-02-03 accept joins
workspace+`#general`, idempotent · AC-02-04 create/join/leave channels,
unique names, can't leave `#general` · AC-02-05 non-members get 403.

**03 Messaging:** AC-03-01 send ≤4000 chars, cursor pagination · AC-03-02
only author edits · AC-03-03 only author deletes, soft delete · AC-03-04
threads with reply_count/last_reply_at · AC-03-05 non-members blocked ·
AC-03-06 >30/min/user → 429.

**04 Realtime:** AC-04-01 message delivery <1s · AC-04-02 typing <500ms,
clears after 3s · AC-04-03 online/offline within 60s · AC-04-04 unauth'd
socket closes 4401 after 5s · AC-04-05 events never cross workspaces.

**05 Integrations:** AC-05-01 owner-only connect, tokens encrypted+never
returned · AC-05-02 real external channels, 1:1 links · AC-05-03 Slack→
UniChat <5s with badge+author · AC-05-04 same for Discord · AC-05-05 no
duplicates/echoes ever (all 3 guard layers) · AC-05-06 UniChat→external as
"Name (via UniChat)" · AC-05-07 Slack threads map both ways · AC-05-08
disconnect stops listener/poller, removes links.

**06 AI assistant:** AC-06-01 summary has key_points/decisions/
open_questions+citations · AC-06-02 answers cite sources that jump-to+
highlight · AC-06-03 draft reply never auto-sent · AC-06-04 search by
meaning across sources, keyword fallback · AC-06-05 assistant never reads/
cites a channel the user hasn't joined, even under a hostile prompt ·
AC-06-06 no key→`ai_disabled`, budget exhausted→`ai_busy`+retry time.

**07 Landing page:** AC-07-01 every section renders in order, CTA routes
correctly by auth state · AC-07-02 hero tabs work by click+arrow keys ·
AC-07-03 reduced motion shows a static frame · AC-07-04 theme persists on
reload · AC-07-05 (manual) Lighthouse desktop ≥90 all 4 categories.

If a future change adds, removes, or changes the meaning of any AC, update
this section as well as the owning feature's `spec.md` — they must always
agree (sync rule, section 2).

---

## 15. Environment variables — ground truth

**`backend/.env.example`:** `DATABASE_URL`, `TEST_DATABASE_URL` (must end in
`_test`), `REDIS_URL` (Upstash, `rediss://`), `JWT_SECRET`,
`JWT_EXPIRES_MINUTES`, `ENCRYPTION_KEY` (Fernet), `GEMINI_API_KEY`,
`GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/`,
`CHAT_MODEL=gemini-2.5-flash`, `EMBEDDING_MODEL=gemini-embedding-001`,
`EMBEDDING_DIM=768`, `AI_REQUESTS_PER_MINUTE=8`, `FRONTEND_URL`,
`ENABLE_BACKGROUND=true`, `DISCORD_POLL_SECONDS=3`, `LOG_LEVEL=INFO`. Slack/
Discord tokens are **never** env vars — pasted per-workspace in Settings,
stored encrypted.

**`frontend/.env.example`:** `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`,
`NEXT_PUBLIC_REPO_URL`.

---

## 16. Phases (reference only — instructions for each arrive via chat)

0 Specs only → 1 Foundation (Neon/Upstash/Gemini setup, core, tokens) → 2
Authentication → 3 Workspaces/channels/messaging → 4 Realtime → 5
Integrations (Slack then Discord) → 6 AI assistant + search → 7 Landing page
→ 8 Quality/traceability/docs → 9 Deploy (Railway + Vercel). Never jump
ahead of the phase currently requested, even if this file describes later
phases in detail — those details exist so that work done now stays
consistent with what's coming, not as permission to build it early.