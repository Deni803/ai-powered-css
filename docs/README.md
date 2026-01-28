# AI-Powered Customer Support System

Monorepo scaffolding for a technical assessment: a web chat UI backed by a RAG knowledge base and a Frappe/Helpdesk CRM for ticket escalation.

## Scope (PRD-aligned)
- Customer chat interface with session context and last 10-20 messages.
- RAG knowledge base for semantic answers with confidence scoring.
- Ticket escalation to CRM when confidence is below threshold.
- Bilingual support targets: English (EN) and Hindi (HI).

## Architecture (high level)
```
Customer Browser
  -> Chat UI (Frappe page/custom app)
  -> Chat Service API
  -> RAG Service (retrieve + generate)
  -> Decision Engine (confidence gate)
     -> Resolved: response to customer
     -> Unresolved: create CRM ticket (Frappe/Helpdesk)
```

## Tech stack (initial)
- Frappe Framework + Helpdesk app (CRM/ticketing)
- LLM: OpenAI (chat + embeddings)
- Vector DB: Qdrant
- DB: PostgreSQL (PRD default)

## Repo layout
- `apps/`    - Frappe apps and custom UI
- `services/` - RAG and chat orchestration services
- `infra/`   - environment templates and deployment notes
- `docs/`    - documentation
- `scripts/` - helper scripts
- `data/kb/` - knowledge base source content

## Prerequisites
- Docker + Docker Compose
- (Later modules) Python, Node, Frappe bench

## Quick verify (preferred)
```bash
make verify
```

## Full verification (end-to-end)
```bash
make verify-full
```

## Setup (manual)
1. Copy env file: `cp infra/env.example infra/.env` and fill values.
2. Start local stack: `make up`.
3. Run checks: `make smoke`.
4. Fetch KB sources: `make fetch-kb`.
5. (Optional) Translate KB to Hindi: `make translate-hi` (set `KB_TRANSLATE_HI=true`).
6. Ingest KB (one-time or when KB changes): `make init-kb` (requires OpenAI key).

## Usage
- Helpdesk UI: http://localhost:8000/helpdesk (or http://helpdesk.localhost:8000/helpdesk with a hosts entry)
- Chat entry page: http://localhost:8000/support
- Chat page: http://localhost:8000/support-chat
- Tickets: HD Ticket (Helpdesk)
- Guest ticket status: `/api/method/ai_powered_css.api.chat.get_ticket_status?ticket_id=...`
- Qdrant: http://localhost:6333
- RAG service: http://localhost:8001/health

## Deployed URLs (BookYourShow)
- Chat: https://bookyourshow.duckdns.org/support-chat
- Helpdesk tickets: https://bookyourshow.duckdns.org/helpdesk/tickets
- Qdrant (reference): http://13.234.72.132:6333/dashboard#/collections

## Docs index
- `ARCHITECTURE.md` - system overview + data flow.
- `API.md` - RAG + chat endpoints with examples.
- `BUGS.md` - known issues and resolved bugs.
- `DECISIONS.md` - ADR-style records and rationale.
- `DEMO.md` - demo flow notes.
- `FEATURES.md` - feature checklist by module.
- `MODULE_LOG.md` - module-by-module change log.
- `TESTING.md` - test scenarios and example queries.

## Ports
| Service | Port | Notes |
| --- | --- | --- |
| Qdrant | 6333 | Vector DB API |
| RAG | 8001 | FastAPI stub |
| Helpdesk | 8000 | Frappe frontend |

## Commands
- `make verify` - fast boot + smoke
- `make verify-full` - end-to-end checks (rag/chat tests + smoke)
- `make up` - start stack
- `make smoke` - smoke test endpoints
- `make fetch-kb` - fetch & parse BookMyShow support pages
- `make translate-hi` - translate EN KB to Hindi (requires OpenAI key)
- `make init-kb` - ingest parsed KB into RAG
- `make rag-test` - RAG quality test (requires OpenAI key; expects KB ingested)
- `make chat-test` - chat endpoint test (includes EN/HI + escalation)
- `make print-creds` - print Helpdesk URL + Administrator credentials
- `make logs` - tail logs
- `make down` - stop and remove containers/volumes

## Testing
- Smoke: `make smoke`.
- Sample queries: see `docs/TESTING.md`.

## Known limitations
- Helpdesk install on Postgres includes a minimal patch for SLA boolean filtering.
- KB fetch depends on publicly available HTML; some pages are JS-rendered.

## Required env vars (for KB + RAG)
- `OPENAI_API_KEY` (embeddings + translation)
- `RAG_API_KEY` (RAG auth)

## Required env vars (Postgres)
- `DB_PASSWORD`
- `DB_ROOT_USERNAME` (default: postgres)
- `DB_NAME` (default: helpdesk)

## Optional env vars (KB fetch/translate)
- `KB_TRANSLATE_HI=true` to generate Hindi translations (requires OpenAI key)
- `KB_MAX_PAGES`, `KB_MAX_ARTICLES`, `KB_MAX_DEPTH` to limit fetch scope
- `KB_TRANSLATE_MAX`, `KB_TRANSLATE_CATEGORIES` to limit translation volume
- `ESCALATION_FALLBACK=todo` to allow ToDo tickets when HD Ticket is unavailable (default: disabled)
