# Business Buddy — Complete Setup & Usage Guide

Business Buddy is a multi-tenant SaaS platform that gives each business its own
dedicated AI consultant. The AI learns everything about your business through
conversation and uploaded documents, and every answer is grounded in your specific
context — never generic advice.

---

## Table of Contents

1. [How it works — end to end](#how-it-works)
2. [Prerequisites](#prerequisites)
3. [Local setup (Mac)](#local-setup-mac)
4. [Docker setup](#docker-setup)
5. [Environment variables](#environment-variables)
6. [Using the app](#using-the-app)
7. [Document uploads](#document-uploads)
8. [Team management](#team-management)
9. [Integrations — Email & Slack](#integrations)
10. [Billing — Stripe](#billing)
11. [API reference](#api-reference)
12. [Known issues & fixes](#known-issues--fixes)
13. [Architecture overview](#architecture-overview)

---

## How it works

### The core loop

```
User sends message
      │
      ▼
Backend builds a system prompt:
  • Full knowledge base (JSON) for this business
  • Relevant document chunks (RAG — cosine search via pgvector)
  • Role persona ("hat") — CFO / Marketing / Ops / HR / Strategy
      │
      ▼
LLM (Groq or Anthropic) returns structured JSON:
  {
    "reply": "...",
    "knowledge_updates": { "revenue": { "arr": "$2M" } },
    "phase": "consulting",
    "knowledge_gaps": ["What is your target market?"]
  }
      │
      ▼
Backend:
  • Saves the reply as a Message
  • Deep-merges knowledge_updates into the KnowledgeBase
  • Updates phase (discovery → consulting)
  • Returns reply + gaps to frontend
```

### Two-phase buddy behaviour

| Phase | What the AI does |
|-------|-----------------|
| **Discovery** | Asks focused questions to fill knowledge gaps. No RAG search runs. |
| **Consulting** | Grounds every answer in known facts. RAG retrieves relevant document chunks. |

The AI decides when to move from discovery to consulting based on how much it knows.

### Knowledge base

Every business has one `knowledge_bases` row with a JSON `data` column structured as:

```json
{
  "overview":    {},
  "products":    {},
  "customers":   {},
  "revenue":     {},
  "team":        {},
  "competition": {},
  "history":     {},
  "now":         {},
  "future":      {},
  "ops":         {}
}
```

Every chat response and every uploaded document adds facts to this. Facts persist
forever — when you come back a week later, the AI still knows everything.

### RAG (document search)

When a document is uploaded:
1. Text is extracted (PDF, DOCX, PPTX, TXT)
2. Split into ~1400-char overlapping chunks
3. Each chunk is embedded with `fastembed` (local CPU model, 384 dimensions)
4. Chunks are stored in PostgreSQL via pgvector
5. Claude Haiku (or Groq's fast model) reads the document and extracts structured KB facts

When you chat in consulting phase:
1. Your message is embedded
2. Top 4 most similar chunks are retrieved (cosine similarity ≥ 0.25)
3. Chunks are injected into the system prompt alongside the full KB

---

## Prerequisites

### Required

- **Python 3.12** — other versions may work but are untested
- **Node.js 18+** — for the frontend
- **PostgreSQL 16 + pgvector** — the vector extension is mandatory

### Installing pgvector (macOS)

`brew install pgvector` does NOT place the extension in PostgreSQL 16's extension
directory. Build from source instead:

```bash
cd /tmp
git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector
export PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config
make
make install
```

Verify it worked:
```bash
psql businessbuddy -c "SELECT '[1,2,3]'::vector;"
# Should print: [1,2,3]
```

### LLM provider

You need **one** of the following:

| Provider | Where to get key | Cost |
|----------|-----------------|------|
| **Groq** (recommended) | [console.groq.com](https://console.groq.com) | Free tier available |
| **Anthropic** | [console.anthropic.com](https://console.anthropic.com) | Free credits on signup |

Set `LLM_PROVIDER=groq` or `LLM_PROVIDER=anthropic` in `.env`.

---

## Local Setup (Mac)

### Step 1 — Install system dependencies

```bash
brew install postgresql@16 python@3.12 node
brew services start postgresql@16
```

### Step 2 — Create the database

```bash
psql postgres -c "CREATE USER buddy WITH PASSWORD 'buddy';"
psql postgres -c "CREATE DATABASE businessbuddy OWNER buddy;"
psql businessbuddy -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

> If you get `connection to server on socket failed: database "yourname" does not exist`,
> use `psql postgres` (connect to the default postgres database, not your system username).

> If you get `extension "vector" is not available`, follow the pgvector build-from-source
> steps in the Prerequisites section above.

### Step 3 — Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **bcrypt compatibility fix** — `passlib 1.7.4` is incompatible with `bcrypt >= 4.0`:
> ```bash
> pip install "bcrypt==3.2.2"
> ```

Copy and configure the environment file:
```bash
cp .env.example .env
```

Open `backend/.env` and set at minimum:
```
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here
```

Start the backend:
```bash
uvicorn main:app --reload --port 8000
```

> First startup downloads the fastembed embedding model (~45 MB). This takes 30–60 seconds.
> Subsequent startups are instant (model is cached at `~/.cache/fastembed`).

API available at: http://localhost:8000
Interactive API docs: http://localhost:8000/docs

### Step 4 — Frontend

Open a new terminal:

```bash
cd frontend
npm install
npm run dev
```

App available at: http://localhost:5173

---

## Docker Setup

Docker Compose runs everything (Postgres + pgvector + backend + frontend + nginx) in
one command.

### Step 1 — Configure environment

```bash
cp .env.example .env
```

Edit the root `.env`:
```
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here
SECRET_KEY=run-openssl-rand-hex-32-and-paste-here
```

Generate a secure secret key:
```bash
openssl rand -hex 32
```

### Step 2 — Build and run

```bash
docker compose up --build
```

> First run: Docker pulls images (~500 MB) and downloads the fastembed model (~45 MB).
> Allow 3–5 minutes. Subsequent runs start in seconds.

App: http://localhost
API docs: http://localhost:8000/docs

### Useful Docker commands

```bash
docker compose down          # stop containers (data preserved)
docker compose down -v       # stop + wipe ALL data (database, uploads)
docker compose logs backend  # view backend logs
docker compose logs -f       # follow all logs
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | local postgres | asyncpg connection string |
| `SECRET_KEY` | Yes | dev default | JWT signing key — change in production |
| `LLM_PROVIDER` | No | `anthropic` | `anthropic` or `groq` |
| `ANTHROPIC_API_KEY` | If using Anthropic | — | From console.anthropic.com |
| `GROQ_API_KEY` | If using Groq | — | From console.groq.com |
| `GROQ_CHAT_MODEL` | No | `llama-3.3-70b-versatile` | Model for chat |
| `GROQ_DOC_MODEL` | No | `llama-3.1-8b-instant` | Model for document summarisation |
| `ENVIRONMENT` | No | `development` | `production` disables SQL echo |
| `CORS_ORIGINS` | No | localhost:5173,3000 | Comma-separated allowed origins |
| `FRONTEND_URL` | No | http://localhost:5173 | Used in invite links |
| `UPLOAD_DIR` | No | `/tmp/...` | Where uploaded files are stored |
| `MAX_UPLOAD_MB` | No | `50` | Max upload size |
| `STRIPE_SECRET_KEY` | No | — | Leave blank to disable billing |
| `STRIPE_WEBHOOK_SECRET` | No | — | From Stripe dashboard |
| `STRIPE_PRICE_PRO` | No | — | `price_xxx` for Pro plan |
| `STRIPE_PRICE_BUSINESS` | No | — | `price_xxx` for Business plan |
| `SMTP_HOST` | No | — | Leave blank — invite links shown in UI instead |
| `SMTP_PORT` | No | `587` | |
| `SMTP_USER` | No | — | |
| `SMTP_PASSWORD` | No | — | |
| `SMTP_FROM` | No | `buddy@yourdomain.com` | |

---

## Using the App

### Signing up

Go to http://localhost:5173/signup. One form creates:
- Your **user account** (email + password)
- Your **business profile** (name, industry, size, stage)
- An empty **knowledge base** for your business

> `buddy` / `buddy` are the PostgreSQL database credentials — **not** the app login.
> You must sign up through the UI to create an app account.

### The dashboard — 3 panels

```
┌─────────────────┬──────────────────────────┬────────────────────┐
│  Conversations  │      Chat Window         │  Knowledge / Docs  │
│                 │                          │                    │
│  • New chat     │  Messages appear here    │  Toggle between:   │
│  • Past chats   │                          │  • Knowledge panel │
│                 │  Gap chips show what     │  • Document panel  │
│                 │  the AI wants to know    │                    │
└─────────────────┴──────────────────────────┴────────────────────┘
```

### Knowledge gaps (gap chips)

After each response, the AI returns up to 4 "knowledge gaps" — things it needs to
know to give better advice. These appear as clickable chips below the chat input.
Click one to send it as your next message.

### Hat selector

The AI auto-detects which "hat" to wear based on your message keywords:

| Hat | Triggered by |
|-----|-------------|
| CFO | revenue, cost, budget, finance, cash |
| Marketing | brand, campaign, SEO, growth, customer |
| Ops | process, team, hiring, operations, system |
| HR | people, culture, hire, onboard, performance |
| Strategy | vision, compete, market, pivot, roadmap |

You can manually override the hat from the selector in the chat input area.

### Knowledge panel

The right panel shows your knowledge base, organised by category with a progress bar
showing how much the AI knows. Categories fill up as you chat and upload documents.

---

## Document Uploads

Supported formats: **PDF, DOCX, DOC, PPTX, PPT, TXT**

### Upload flow

1. Click the **Documents** tab in the right panel
2. Drag and drop a file or click to browse
3. Upload returns immediately with status `processing`
4. Every 3 seconds, the UI polls for status update
5. When processing completes, status changes to `ready`

### What happens in the background

1. Text extraction (PyMuPDF for PDF, python-pptx, python-docx)
2. Chunking into ~1400-character overlapping windows
3. Embedding each chunk with fastembed (local, no API cost)
4. Storing chunks in pgvector
5. Claude/Groq reads the document and extracts structured KB facts
6. KB facts are deep-merged into your knowledge base

### Plan limits

| Plan | Max documents |
|------|--------------|
| Free | 5 |
| Pro | 100 |
| Business | Unlimited |

---

## Team Management

Go to **Settings → Team** tab.

### Inviting a member

1. Enter their email address and select a role (Admin or Member)
2. Click **Send Invite**
3. If SMTP is not configured, the invite link is shown directly in the UI and logged
   to the backend console — copy and share it manually
4. The invite link is valid for **7 days**

### Roles

| Role | Permissions |
|------|------------|
| Owner | Full access, can manage billing |
| Admin | Can invite/remove members, upload documents |
| Member | Can chat and view knowledge base |

### Accepting an invite

The recipient opens `/invite/:token` (public page, no login required) and creates
their account. They are immediately added to your business.

### Plan limits

| Plan | Max team members |
|------|----------------|
| Free | 1 (just you) |
| Pro | 5 |
| Business | Unlimited |

---

## Integrations

Go to **Settings → Integrations** tab. Integrations sync external content through the
same document pipeline as file uploads — text is chunked, embedded, and stored in
pgvector, and facts are merged into the KB.

> Integrations require **Pro or Business plan** if Stripe is configured.

### Email (IMAP)

Works with Gmail and any IMAP provider.

**Gmail setup:**
1. Enable IMAP: Gmail → Settings → See all settings → Forwarding and POP/IMAP → Enable IMAP
2. Create an App Password (requires 2FA enabled):
   https://myaccount.google.com/apppasswords
3. In Business Buddy: Settings → Integrations → Connect Email
   - Host: `imap.gmail.com`
   - Port: `993`
   - Username: your full Gmail address
   - Password: the App Password (not your Gmail password)

The connection is tested before saving. Sync is incremental — only new emails since
last sync are processed.

### Slack

1. Go to https://api.slack.com/apps → Create New App → From scratch
2. Under **OAuth & Permissions**, add these Bot Token Scopes:
   - `channels:history`
   - `channels:read`
   - `groups:history`
   - `groups:read`
3. Click **Install to Workspace** → copy the **Bot User OAuth Token** (`xoxb-...`)
4. Invite the bot to each channel you want synced: `/invite @YourBotName`
5. Find channel IDs: right-click channel name → View channel details → bottom of modal

Enter the Bot Token and comma-separated channel IDs in Settings → Integrations → Connect Slack.

### Manual sync

Both integrations have a **↻ Sync** button for on-demand syncing.
Automated scheduled sync is a planned feature (not yet implemented).

---

## Billing

Go to **Settings → Billing** tab. Leave all `STRIPE_*` variables blank to run without
billing — all users are effectively on the Free plan.

### Plans

| | Free | Pro | Business |
|-|------|-----|----------|
| Price | $0 | $49/mo | $149/mo |
| Users | 1 | 5 | Unlimited |
| Documents | 5 | 100 | Unlimited |
| Integrations | — | Email + Slack | Email + Slack |

### Setting up Stripe

1. Create an account at https://stripe.com
2. Create two products with monthly prices (Pro at $49, Business at $149)
3. Copy the `price_xxx` IDs into `.env`
4. Add `STRIPE_SECRET_KEY` from https://dashboard.stripe.com/apikeys
5. For local webhook testing, install the Stripe CLI:
   ```bash
   stripe listen --forward-to localhost:8000/billing/webhook
   ```
6. Copy the webhook signing secret into `STRIPE_WEBHOOK_SECRET`

---

## API Reference

All endpoints are prefixed with `/`. Interactive docs: http://localhost:8000/docs

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/signup` | Create account + business (returns JWT) |
| POST | `/auth/login` | Login (returns JWT) |
| GET | `/auth/me` | Current user + business info |

All other endpoints require `Authorization: Bearer <token>` header.

### Chat

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Send message, get reply + KB update |
| GET | `/chat/conversations` | List all conversations |
| GET | `/chat/conversations/{id}` | Conversation + full message history |

**POST /chat request body:**
```json
{
  "message": "What should our pricing strategy be?",
  "conversation_id": "uuid-or-null-for-new",
  "hat": "auto"
}
```

**POST /chat response:**
```json
{
  "conversation_id": "uuid",
  "reply": "Based on your SaaS model...",
  "knowledge_updates": { "revenue": { "model": "subscription" } },
  "phase": "consulting",
  "knowledge_gaps": ["What is your current MRR?"]
}
```

### Business & Knowledge

| Method | Path | Description |
|--------|------|-------------|
| GET | `/business` | Business profile |
| PATCH | `/business` | Update business profile |
| GET | `/business/knowledge` | Full knowledge base JSON |
| PATCH | `/business/knowledge` | Manually update KB facts |

### Documents

| Method | Path | Description |
|--------|------|-------------|
| POST | `/documents` | Upload file (returns 202, processes async) |
| GET | `/documents` | List all documents with status |
| GET | `/documents/{id}` | Single document details |
| DELETE | `/documents/{id}` | Delete document + remove chunks |

### Team

| Method | Path | Description |
|--------|------|-------------|
| GET | `/team/members` | List active members |
| GET | `/team/invites` | List pending invites |
| POST | `/team/invite` | Create invite |
| GET | `/team/invite/{token}` | Look up invite (public, no auth) |
| POST | `/team/invite/{token}/accept` | Accept invite |
| DELETE | `/team/members/{id}` | Remove member |

### Integrations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/integrations` | List connected integrations |
| POST | `/integrations/email` | Connect IMAP email |
| POST | `/integrations/slack` | Connect Slack |
| POST | `/integrations/{id}/sync` | Trigger manual sync |
| DELETE | `/integrations/{id}` | Disconnect integration |

### Billing

| Method | Path | Description |
|--------|------|-------------|
| GET | `/billing/status` | Current plan + usage |
| POST | `/billing/checkout` | Create Stripe checkout session |
| POST | `/billing/portal` | Create Stripe customer portal |
| POST | `/billing/webhook` | Stripe webhook receiver |

---

## Known Issues & Fixes

### `psql: database "yourname" does not exist`
Connect to the default database: `psql postgres` (not just `psql`)

### `extension "vector" is not available`
`brew install pgvector` doesn't work for PostgreSQL 16. Build from source:
```bash
cd /tmp && git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector
export PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config
make && make install
```

### `ValueError: password cannot be longer than 72 bytes`
passlib 1.7.4 is incompatible with bcrypt 4.x:
```bash
pip install "bcrypt==3.2.2"
```

### `module 'stripe' has no attribute 'Stripe'`
The stripe SDK renamed the class to `StripeClient`. Already fixed in the codebase.
If it appears again, ensure `stripe==9.9.0` is installed.

### `LLM API error: 401 authentication_error`
Check `.env` has `LLM_PROVIDER=groq` and a valid `GROQ_API_KEY`. The default
provider is `anthropic` — if you don't set `LLM_PROVIDER=groq`, it will try
Anthropic with no key and fail.

### `MissingGreenlet` / `InFailedSQLTransactionError` during chat
This happens when the fastembed ONNX Runtime inference disrupts SQLAlchemy's
greenlet context. Already fixed — the RAG search uses its own isolated DB session.
If it recurs after a code change, ensure the RAG block in `chat_router.py` uses
`async with AsyncSessionLocal() as rag_db`.

### Embedding model slow on first startup
The fastembed model (~45 MB) downloads on first startup and is warmed up immediately.
Subsequent requests are fast. In Docker, the model is cached in a named volume
(`fastembed_cache`) so it persists across container restarts.

---

## Architecture Overview

```
Browser (React SPA)
    │  REST over HTTP
    ▼
FastAPI (port 8000)
    │
    ├── auth_router      → JWT login / signup
    ├── chat_router      → message → LLM → KB update (RAG in consulting phase)
    ├── business_router  → business profile + knowledge base
    ├── document_router  → upload → BackgroundTask → pipeline
    ├── billing_router   → Stripe Checkout + webhooks
    ├── team_router      → invite + accept + member management
    └── integration_router → IMAP / Slack connect + sync
          │
          ├── app/llm.py          → unified Anthropic/Groq wrapper
          ├── app/knowledge.py    → system prompt builder + deep_merge
          ├── app/embeddings.py   → fastembed singleton (384-dim)
          ├── app/vector_store.py → pgvector store + cosine search (raw SQL)
          └── app/document_processor.py → extract → chunk → embed → KB summary
                │
                ▼
          PostgreSQL 16 + pgvector
                │
                ├── businesses, users, knowledge_bases
                ├── conversations, messages
                ├── documents, document_chunks (vector(384))
                ├── subscriptions, invites, integrations
                └── (pgvector IVFFlat index on document_chunks.embedding)
```

### Key design rules

- **Multi-tenancy**: every query filters by `business_id` — no data leaks between businesses
- **Knowledge base**: never overwrite, always `deep_merge()` — facts accumulate
- **System prompt**: rebuilt fresh on every chat request — Claude has no memory between calls
- **document_chunks**: raw SQL only — pgvector's `<=>` operator needs `sqlalchemy.text()`
- **Background tasks**: always create a new `AsyncSessionLocal()` — never reuse the request session
- **Stripe/SMTP**: fully optional — leave env vars blank to disable gracefully
