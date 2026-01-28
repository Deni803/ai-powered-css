# Features

## Module 0
- Monorepo scaffolding with apps/services/infra/docs/scripts/data layout.
- Baseline Makefile and environment template.

## Module 1
- Docker Compose baseline: Qdrant + RAG stub + Frappe dev stack.
- Smoke tests + `make verify`.

## Module 2
- RAG service with /ingest + /query using OpenAI + Qdrant.
- Confidence scoring and language handling (EN/HI).
- Unit tests + integration rag-test.

## Module 2.1
- Safe failure behavior on embedding outages.
- Expanded rag-test with edge cases.

## Module 3
- Source-driven KB fetcher from official BookMyShow support/help pages.
- KB ingest pipeline and strict rag-test gate.

## Module 3.1
- BFS crawl expansion + pagination + blocked URL tracking.
- Cleaner HTML extraction and optional Hindi translation pipeline.

## Module 4
- Frappe guest chat page (/support-chat) with session + message persistence.
- Chat API calls RAG and escalates to Helpdesk ticketing.
- Chat tests + helpdesk app install scripts.

## Module 4.2
- Official Helpdesk docker profile with init.sh.
- HD Ticket escalation as default.
- Public support entry page (/support) and verify-full flow.

## Module 4.3
- Escalation policy: greeting/short routing, low-confidence clarifications, explicit ticket flow.
- Guest ticket status endpoint and improved chat tests.

## Module 4.4
- Roman-Hindi normalization + Hindi-only responses for Hindi inputs.
- 3-state resolution engine (ANSWERED / NEEDS_CLARIFICATION / UNRESOLVED).
- Domain-aware clarification prompts and quick replies for refunds/payments.
- Agent-friendly ticket formatting.
- Chat UI polish (new chat, details toggle, quick replies, clearer banner).

## Module 4.5
- Conservative language selection (auto EN default, high-precision Roman Hindi).
- KB-first answering with targeted clarifications, quick-reply persistence, and follow-up retrieval.
- Escalation offer/auto rules aligned to multi-turn support flow.
- Suppressed external channel suggestions unless grounded in KB context.
- Improved ticket readability with structured sections, metadata, and bounded transcript.
