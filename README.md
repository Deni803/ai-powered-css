# BookYourShow AI Support (Frappe + RAG)

AI-powered customer support system with a Frappe Helpdesk CRM and a RAG service backed by Qdrant + OpenAI. Built to satisfy the PRD for a chat UI, knowledge base, and ticket escalation flow.

## Project overview
- **Customer chat UI**: web chat page (`/support-chat`) with session history and bilingual support (EN/HI).
- **RAG knowledge base**: Qdrant vector search + OpenAI LLM responses grounded in KB.
- **CRM escalation**: unresolved queries create **HD Ticket** in Frappe Helpdesk (with contact capture).
- **Source‑driven KB**: KB is built from real BookMyShow FAQ pages via `scripts/fetch_bms_kb.py`, stored as clean JSON in `data/kb/articles/`, and ingested into Qdrant. We can scale this by crawling more official help pages and running `scripts/translate_kb_hi.py` to add Hindi content before re‑ingesting to the vector DB.

## Architecture diagram (high level)
```
Customer Browser
  |
  v
Chat UI (/support-chat)
  |  (Auto/EN/HI + Roman-Hindi detection)
  v
Chat API (Frappe app) -----> Postgres (sessions/messages)
  |
  v
RAG Service (FastAPI) -----> Qdrant (KB vectors)
  |
  v
Decision Engine
  |--> ANSWERED (KB-grounded reply in selected language)
  |--> NEEDS_CLARIFICATION (targeted question + quick replies)
  |        ^                                  |
  |        |----------------------------------|
  `--> UNRESOLVED (contact capture -> HD Ticket)
```

## Architecture
- Detailed diagrams and implementation-accurate flow: `docs/architecture/ai-chatbot-architecture.md`
- System overview: `docs/architecture/system-overview.md`

## Tech stack
- **Framework**: Frappe + Helpdesk app
- **DB**: PostgreSQL (PRD default)
- **LLM**: OpenAI (chat + embeddings)
- **Vector DB**: Qdrant
- **RAG API**: FastAPI

## Setup instructions
### Prerequisites
- Docker + Docker Compose
- OpenAI API key (for embeddings + translation + chat)

### Installation
```bash
cp infra/env.example infra/.env
# edit infra/.env to set OPENAI_API_KEY, RAG_API_KEY, etc.
make up
```

### Environment configuration
- Single source of truth: `infra/.env`
- Template: `infra/env.example`
- Required for RAG: `OPENAI_API_KEY`, `RAG_API_KEY`

### Database setup (Postgres)
The stack boots with Postgres and auto-creates the Helpdesk site during init (no manual DB steps).

### Knowledge base initialization
```bash
make fetch-kb
make translate-hi   # optional, requires OPENAI_API_KEY
make init-kb         # ingest into Qdrant
```

## Usage guide
### Access chat interface
- Local: http://localhost:8000/support-chat
- Deployed: https://bookyourshow.duckdns.org/support-chat
- Support Chat (public): https://bookyourshow.duckdns.org/support-chat

### View tickets in CRM
- Local: http://localhost:8000/helpdesk/tickets
- Deployed: https://bookyourshow.duckdns.org/helpdesk/tickets
- Helpdesk / CRM UI: https://bookyourshow.duckdns.org/login

### Add knowledge base articles
- Edit or add JSON files in `data/kb/articles/`
- Re-run `make init-kb`

## Configuration
### LLM API key setup
Set in `infra/.env`:
- `OPENAI_API_KEY`
- `OPENAI_CHAT_MODEL`
- `OPENAI_EMBED_MODEL`

### Vector DB configuration
- `QDRANT_URL` (default points to container)
- `QDRANT_COLLECTION`

### Environment variables (core)
- `RAG_API_KEY` (required for `/ingest` + `/query`)
- `CONF_THRESHOLD` (default 0.7)
- `TOP_K` (default 5)
- `DB_PASSWORD`, `DB_ROOT_USERNAME`, `DB_NAME` (Postgres)

## Deployment (EC2 + Nginx + Let's Encrypt)
We run the public demo behind **Nginx** with **Let's Encrypt** certificates. The canonical Nginx config is stored at `infra/nginx.conf` and is currently deployed at:
```
/etc/nginx/sites-available/ai-css.conf
```
See `infra/README.md` for the exact config, proxy routing, and Certbot commands used to issue/renew TLS certificates.

## Caching
Not implemented yet for RAG responses. Each chat query calls the RAG service and OpenAI. The UI stores chat messages in browser `localStorage` for session continuity, and Frappe uses Redis for internal queues/sessions, but there is no semantic response or retrieval cache in the application code.
## Testing
```bash
make verify-full
```
Sample test scenarios (PRD-aligned):
- **Resolvable**: “Refund timeline for UPI payments” → answer with KB sources.
- **Partially resolvable**: “Refund help” → asks for clarification + quick replies.
- **Unresolvable**: “Create ticket for fraud dispute” → offers/creates ticket after contact capture.
- **Edge**: “hello”, “??”, off-topic → friendly prompt, no ticket.

## Known limitations
- **Current scope boundaries**: no production auth or SLA automation; guest chat intended for demo/POC.
- **Production considerations**: add rate limiting, monitoring, and hardened auth before real users.
- Some BookMyShow help pages are JS-rendered; fetcher may capture limited text.
- OpenAI rate limits can cause low-confidence safe responses.
- If `/helpdesk` shows “User None is disabled”, clear cookies or use incognito.

## Future scope
1. **Semantic caching (L1 response + L2 retrieval)**: cache keys based on normalized query + language + KB version; TTL-based expiry; invalidate on KB re-ingest; expose cache hit metrics.
2. **Verifier/critic pass**: run a lightweight QA step after generation to detect unsupported claims before returning ANSWERED.

## Repository structure
```
apps/       Frappe apps (ai_powered_css)
services/   RAG service (FastAPI)
infra/      docker-compose + env templates
scripts/    helper scripts (fetch/translate/init KB, tests)
data/kb/    KB sources and parsed articles
test_output/ Screenshot containg test output
```

## Technical documentation
- **API endpoints**: `docs/API.md`
- **DB schema overview**: `docs/ARCHITECTURE.md` (chat session/message + HD Ticket)
- **RAG architecture notes**: `docs/ARCHITECTURE.md` + `docs/DECISIONS.md`
- **Test cases**: `docs/TESTING.md`
- **Module history**: `docs/MODULE_LOG.md`

## Repository & deliverables
- Git repository with clear structure (see layout above).
- `.gitignore` configured to exclude secrets (`infra/.env`) and raw crawl data (`data/kb/raw/`).
- This README includes all PRD-required sections.
