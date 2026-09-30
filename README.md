# UniChat

> Chat. Connect. Ask.

UniChat is a unified team chat application designed for modern distributed teams. It links UniChat channels directly to Slack and Discord channels for bi-directional message synchronization, augmented with a Google Gemini-powered AI assistant that summarizes channel activity, drafts responses, answers queries with cited source messages, and performs semantic search across all platforms.

## Architecture Highlights
- **Specs First**: Complete specification-driven design with OpenAPI 3.1 contracts, Mermaid DB ERDs, and traceability.
- **Frontend**: Next.js 15 (App Router), React 19, TypeScript strict mode, Tailwind CSS v4.
- **Backend**: FastAPI (Python), SQLAlchemy 2.0 async, asyncpg, Redis (asyncio), Gemini Embeddings (`gemini-embedding-001`), and OpenAI Agents SDK pointing to Gemini's OpenAI-compatible endpoint.
- **Database**: PostgreSQL with `pgvector` extension (hosted on Neon), Upstash Redis for realtime and caching.

## Status
Phase 0 (System Specifications, Architecture, and Data Modeling) initialized.
