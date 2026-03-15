# Business Buddy — Project Context for Claude Code

This document is the single source of truth for the Claude Code agent working on this codebase.
Read it fully before making any changes.

---

## What this product is

**Business Buddy** is a multi-tenant SaaS platform that gives each business its own
dedicated AI consultant. The AI learns everything about a specific business — its
products, customers, history, priorities, financials, operations — and answers every
question grounded in that specific context. It never gives generic advice. If it doesn't
know something, it asks rather than guessing.

The key differentiator: **persistent, evolving knowledge**. Every conversation, uploaded
document, and connected data source enriches the business's knowledge base. When a user
comes back a week later, the buddy remembers everything.

---

## What has been built (Phases 1–3, complete)

### Phase 1 — Foundation
- Self-serve signup: one form creates a User + Business + empty KnowledgeBase in one shot
- JWT auth (7-day tokens, bcrypt passwords)
- Async PostgreSQL via SQLAlchemy + asyncpg
- **Knowledge engine**: every Claude response returns structured `knowledge_updates` JSON
  which is deep-merged into the `knowledge_bases` table — persisting across sessions
- **Dynamic system prompt**: on every chat call, the full KB is serialised and injected
  into Claude's system prompt so it "knows" the business from turn one
- Two-phase buddy behaviour: **Discovery** (asks focused questions to fill KB gaps) →
  **Consulting** (grounds every answer in known facts, references specifics)
- **Hat auto-detection**: keyword classifier detects CFO / Marketing / Ops / HR / Strategy
  intent and injects a role persona; user can override manually
- Conversation history: full message history stored per conversation, last 40 messages
  sent to Claude on each call
- Three-panel React frontend: conversation list (left) + chat (centre) + knowledge panel (right)

### Phase 2 — Document pipeline + RAG
- Upload endpoint (PDF, PPTX, DOCX, TXT) — returns 202 immediately, processes in background
- **Document pipeline** (BackgroundTask):
  1. Text extraction: PyMuPDF (PDF), python-pptx (PPTX), python-docx (DOCX)
  2. Chunking: ~1400-char windows with 200-char overlap, paragraph-aware splitting
  3. Embedding: fastembed `BAAI/bge-small-en-v1.5` (384-dim, local CPU, ~45 MB model)
  4. pgvector storage: `document_chunks` table (raw SQL — pgvector operators require this)
  5. KB summary: Claude Haiku reads the document, extracts structured facts, deep-merges
     into `knowledge_bases`
- **RAG at query time**: user message is embedded → cosine search → top 4 chunks injected
  into system prompt alongside the KB. Only active in consulting phase. Min similarity 0.25.
- pgvector IVFFlat index on embeddings for fast approximate nearest-neighbour search
- Right panel in dashboard toggles between Knowledge view and Documents view
- Document status polling (every 3s while processing)

### Phase 3 — Billing + Team + Integrations
- **Stripe billing**: Checkout sessions, Customer Portal, webhook receiver. Three tiers:
  - Free: 1 user, 5 documents, no integrations
  - Pro ($49/mo): 5 users, 100 documents, email + Slack
  - Business ($149/mo): unlimited everything
- **`plan_guard.py`**: FastAPI dependencies (`require_can_add_document`,
  `require_can_add_member`, `require_integrations`) enforced at endpoint level
- **Team invites**: secure 7-day tokens, SMTP email (console fallback if unconfigured),
  public `/invite/:token` accept page, role-based access (owner / admin / member)
- **Email ingestion (IMAP)**: incremental sync via `last_uid`, per-email ingestion through
  the same Phase 2 pipeline. Supports Gmail App Passwords + any IMAP provider.
- **Slack ingestion**: Slack Web API, channel history, incremental via `last_ts`, batched
  by channel, same pipeline. Requires `channels:history` bot scope.
- Both integrations: connection tested before saving, credentials stored in `Integration.config`
  (never exposed in API responses), manual sync trigger, background task processing
- Settings page (`/settings`): three-tab UI — Billing, Team, Integrations
- `/invite/:token` public route (no auth required)

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  React SPA (Vite)                           │
│  /dashboard  /settings  /invite/:token      │
│  /login  /signup                            │
└────────────────────┬────────────────────────┘
                     │ REST (proxied via Nginx / Vite dev proxy)
┌────────────────────▼────────────────────────┐
│  FastAPI (Python 3.12)  — port 8000         │
│                                             │
│  Routers:                                   │
│    /auth        /business    /chat          │
│    /documents   /billing     /team          │
│    /integrations                            │
│                                             │
│  Core services:                             │
│    knowledge.py      → system prompt builder│
│    embeddings.py     → fastembed singleton  │
│    vector_store.py   → pgvector ops         │
│    document_processor.py → full pipeline   │
│    ingestion/base.py → shared text→vector  │
│    billing.py        → Stripe client        │
│    plan_guard.py     → tier enforcement     │
│    email_service.py  → SMTP / console       │
└────────────────────┬────────────────────────┘
                     │ asyncpg
┌────────────────────▼────────────────────────┐
│  PostgreSQL 16 + pgvector                   │
│                                             │
│  Tables (ORM):                              │
│    businesses   users          knowledge_bases│
│    conversations  messages     documents    │
│    subscriptions  invites      integrations │
│                                             │
│  Raw SQL table:                             │
│    document_chunks  (vector(384) column)    │
│                                             │
│  File system: /uploads/{business_id}/*.ext  │
└─────────────────────────────────────────────┘
```

---

## Key design decisions (do not change without good reason)

1. **`document_chunks` is raw SQL** — pgvector's `<=>` cosine operator does not work
   correctly through SQLAlchemy ORM column types. All vector operations use
   `sqlalchemy.text()` with literal SQL.

2. **Knowledge base is a JSON column** (`knowledge_bases.data`) keyed by category:
   `overview | products | customers | revenue | team | competition | history | now | future | ops`.
   Always use `deep_merge()` from `knowledge.py` — never overwrite the whole dict.

3. **System prompt is rebuilt on every request** — Claude has no memory between API calls.
   The full KB + relevant RAG chunks + hat persona are assembled fresh each time in
   `knowledge.py:build_system_prompt()`.

4. **Claude returns JSON, not plain text** — the chat endpoint expects Claude to respond
   with `{"reply": "...", "knowledge_updates": {...}, "phase": "...", "knowledge_gaps": [...]}`.
   `_parse_claude_response()` in `chat_router.py` handles malformed responses gracefully.

5. **Multi-tenancy via `business_id`** — every DB query that touches user data includes
   `WHERE business_id = current_user.business_id`. Never omit this filter.

6. **Stripe is optional** — all `STRIPE_*` env vars can be blank. `billing.py:get_client()`
   raises `RuntimeError` if called without a key, but endpoints check `settings.stripe_enabled`
   first and return 503 cleanly. Without Stripe, all users are effectively on Free plan.

7. **SMTP is optional** — `email_service.py` logs invite links to console if `SMTP_HOST`
   is not set. The invite URL is also returned in the API response and shown in the UI.

8. **Embedding model is local** — fastembed downloads `BAAI/bge-small-en-v1.5` (~45 MB)
   on first startup and caches it. No external embedding API calls, no cost per document.
   The model outputs 384-dimensional vectors.

9. **Background tasks use their own DB sessions** — FastAPI's `BackgroundTasks` runs after
   the response is sent. Document processing and integration syncs create a new
   `AsyncSessionLocal()` session — never reuse the request session.

10. **Plan limits are enforced at dependency level** — `plan_guard.py` provides FastAPI
    `Depends()` functions. Wire them into the endpoint signature, not inside the body.

---

## File map

```
backend/
├── main.py                          # FastAPI app, lifespan, CORS, router mounts
├── requirements.txt
├── .env.example                     # all env vars documented
├── Dockerfile
└── app/
    ├── config.py                    # Settings (pydantic-settings, .env)
    ├── database.py                  # engine, Base, get_db, create_tables
    ├── models.py                    # all SQLAlchemy ORM models
    ├── schemas.py                   # Pydantic request/response models
    ├── auth.py                      # JWT, bcrypt, get_current_user dep
    ├── knowledge.py                 # deep_merge, build_system_prompt, detect_hat
    ├── embeddings.py                # fastembed singleton, embed(), embed_one()
    ├── vector_store.py              # store_chunks(), search_chunks() — raw SQL
    ├── document_processor.py        # extract_text, chunk_text, process_document
    ├── billing.py                   # Stripe helpers, PLAN_LIMITS dict
    ├── plan_guard.py                # require_can_add_document/member/integrations
    ├── email_service.py             # send_invite_email (SMTP or console)
    ├── ingestion/
    │   ├── base.py                  # ingest_text_as_document (shared pipeline)
    │   ├── email_ingestion.py       # sync_email_integration (IMAP)
    │   └── slack_ingestion.py       # sync_slack_integration (Slack API)
    └── routers/
        ├── __init__.py              # exports all routers
        ├── auth_router.py           # POST /auth/signup, /login · GET /auth/me
        ├── business_router.py       # GET/PATCH /business · GET /business/knowledge
        ├── chat_router.py           # POST /chat · GET /chat/conversations[/{id}]
        ├── document_router.py       # POST/GET/DELETE /documents[/{id}]
        ├── billing_router.py        # GET/POST /billing/* · POST /billing/webhook
        ├── team_router.py           # GET/POST/DELETE /team/*
        └── integration_router.py    # GET/POST/DELETE /integrations/*

frontend/
├── index.html
├── vite.config.js                   # dev proxy: /api → localhost:8000
├── package.json
├── nginx.conf                       # SPA fallback + /api proxy for Docker
├── Dockerfile
└── src/
    ├── main.jsx                     # BrowserRouter, all routes, AuthProvider
    ├── api.js                       # api, billingApi, teamApi, integrationApi, uploadDocument
    ├── knowledge.js                 # client-side deepMerge (mirrors backend)
    ├── styles.css                   # shared tokens, auth card styles, form styles
    ├── context/
    │   └── AuthContext.jsx          # user state, login/signup/logout, /auth/me on load
    ├── pages/
    │   ├── LoginPage.jsx
    │   ├── SignupPage.jsx           # creates user + business in one form
    │   ├── DashboardPage.jsx        # 3-panel: Sidebar + ChatWindow + KB/Docs panel
    │   ├── SettingsPage.jsx         # 3-tab: Billing + Team + Integrations
    │   └── InviteAcceptPage.jsx     # public /invite/:token accept flow
    └── components/
        ├── Sidebar.jsx              # conversation list + new chat button
        ├── ChatWindow.jsx           # messages, input, gap chips, hat selector
        ├── KnowledgePanel.jsx       # live KB visualisation, progress bar
        └── DocumentPanel.jsx        # drag-drop upload, status polling, doc list

postgres/
└── init.sql                         # CREATE EXTENSION IF NOT EXISTS vector

docker-compose.yml                   # pgvector/pgvector:pg16, backend, frontend
.env.example                         # root-level for Docker Compose
```

---

## Environment variables

| Variable                  | Required | Default                  | Notes                                  |
|---------------------------|----------|--------------------------|----------------------------------------|
| `DATABASE_URL`            | Yes      | local postgres URL       | asyncpg format                        |
| `SECRET_KEY`              | Yes      | dev default              | `openssl rand -hex 32`                |
| `ANTHROPIC_API_KEY`       | Yes      | —                        | Claude Sonnet (chat) + Haiku (docs)   |
| `ENVIRONMENT`             | No       | `development`            | `production` disables SQL echo        |
| `CORS_ORIGINS`            | No       | localhost:5173,3000      | comma-separated                       |
| `FRONTEND_URL`            | No       | `http://localhost:5173`  | used in invite links                  |
| `UPLOAD_DIR`              | No       | `/tmp/...`               | persist via Docker volume in prod     |
| `MAX_UPLOAD_MB`           | No       | `50`                     |                                        |
| `STRIPE_SECRET_KEY`       | No       | —                        | leave blank to disable billing        |
| `STRIPE_WEBHOOK_SECRET`   | No       | —                        |                                        |
| `STRIPE_PRICE_PRO`        | No       | —                        | `price_xxx` from Stripe dashboard     |
| `STRIPE_PRICE_BUSINESS`   | No       | —                        |                                        |
| `SMTP_HOST`               | No       | —                        | leave blank to log invites to console |
| `SMTP_PORT`               | No       | `587`                    |                                        |
| `SMTP_USER`               | No       | —                        |                                        |
| `SMTP_PASSWORD`           | No       | —                        |                                        |
| `SMTP_FROM`               | No       | `buddy@yourdomain.com`   |                                        |

---

## Running locally

```bash
# Postgres (one-time setup)
brew install postgresql@16 && brew services start postgresql@16
psql postgres -c "CREATE USER buddy WITH PASSWORD 'buddy'; CREATE DATABASE businessbuddy OWNER buddy;"
psql businessbuddy -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Backend
cd backend && python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend && npm install && npm run dev
# → http://localhost:5173
```

```bash
# Docker Compose (full stack)
cp .env.example .env   # set ANTHROPIC_API_KEY + SECRET_KEY
docker compose up --build
# → http://localhost
```

---

## Immediate next goals (what to build next)

These are the agreed priorities in order:

### 1. Scheduled background sync for integrations
Currently, email and Slack sync only when the user manually clicks "↻ Sync".
Add an APScheduler or asyncio-based scheduler that auto-syncs all active integrations
every N hours (configurable per integration). The scheduler should:
- Run inside the FastAPI process (APScheduler with AsyncIOScheduler)
- Load all `Integration` records with `status = 'active'`
- Respect per-integration `sync_interval_hours` config field (default: 6)
- Handle errors gracefully — update `last_error`, don't crash other syncs
- Be disabled in test environments

### 2. Alembic migrations
Currently `create_tables()` uses `metadata.create_all` which cannot handle schema changes
on existing databases. Replace with proper Alembic migrations:
- `alembic init alembic`
- Generate initial migration from current models
- All future model changes go through `alembic revision --autogenerate`
- Docker Compose should run `alembic upgrade head` before starting uvicorn

### 3. Admin dashboard (superuser)
A separate `/admin` route (not visible to regular users) for the platform operator:
- List all businesses + their plan + last activity
- Manually adjust a business's plan
- View system-wide stats: total users, documents, chunks, integrations
- Impersonate a business for debugging (read-only view of their KB)
- Requires a `is_superuser` flag on the `User` model

### 4. Knowledge base editing UI
Currently the KB is only written by the AI. Users should be able to:
- See all KB facts organised by category
- Edit or delete individual facts
- Manually add facts the AI hasn't picked up yet
- Mark certain facts as "locked" (AI cannot overwrite)
The backend already has `PATCH /business/knowledge` — the UI just needs to be built.

### 5. Conversation search
Add full-text search across all conversations for a business:
- `GET /chat/conversations/search?q=...`
- Uses PostgreSQL `tsvector` / `to_tsquery` on `messages.content`
- Show matching conversations with a snippet in the sidebar

### 6. Webhook for real-time sync (Slack)
Instead of polling Slack on a schedule, implement the Slack Events API:
- `POST /integrations/slack/events` — receives real-time message events
- Verify the Slack signing secret
- Ingest each new message immediately via `ingest_text_as_document`
- Only feasible with a publicly reachable server (not local dev)

---

## Code conventions

- **Python**: async everywhere (FastAPI + asyncpg). No sync DB calls in request handlers.
  Background tasks create their own `AsyncSessionLocal()` session.
- **Error handling**: raise `HTTPException` with descriptive `detail` strings. Never
  expose raw exception messages to clients in production.
- **Multi-tenancy**: every query touching user data must filter by `business_id`.
  Add `assert current_user.business_id == ...` checks where ownership matters.
- **Secrets**: never log or return passwords / tokens / API keys. `document_router.py`
  and `integration_router.py` have examples of stripping secrets from API responses.
- **Frontend**: no external CSS frameworks — plain inline styles with CSS variables from
  `styles.css`. Keep components self-contained.
- **Imports**: backend uses absolute imports (`from app.models import ...`), not relative.
- **Type hints**: use them everywhere in Python. Pydantic models for all API boundaries.

---

## Known limitations to address

- `Integration.config` stores credentials as plaintext JSON. For production, encrypt
  sensitive fields at rest using `cryptography` (Fernet) before storing.
- The IVFFlat index on `document_chunks.embedding` requires at least 100 rows to be
  useful — for small datasets `HNSW` (pgvector 0.5+) is better and has no minimum.
- `create_tables()` uses `CREATE IF NOT EXISTS` — safe for prototype but blocks Alembic.
  Switch to Alembic before any schema changes.
- The embedding model is downloaded at startup — in Docker this adds ~45s on first run.
  Pre-bake it into the Docker image for faster cold starts.
- No rate limiting on chat or upload endpoints — add `slowapi` before public launch.
