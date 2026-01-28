# Module Progress Log

## Repo purpose
AI-powered customer support system: chat UI + RAG knowledge base + CRM ticket escalation (Frappe Helpdesk).

## Architecture overview (high level)
Customer -> Chat UI -> RAG service (retrieve + generate) -> Confidence gate -> Frappe/Helpdesk ticketing.

## Completed modules

### Module 0 (2026-01-27)
- Key changes: monorepo scaffolding, base docs, Makefile, env template.
- Commands: n/a (scaffold only).
- Known issues: none recorded.

### Module 1 (2026-01-27)
- Key changes: docker-compose baseline (Qdrant + RAG stub + Frappe dev stack), smoke tests, `make verify`.
- Commands: `make up`, `make helpdesk-init`, `make smoke`, `make verify`.
- Known issues: MariaDB used for dev stability (PRD wants Postgres); Helpdesk app install deferred.

### Module 2 (2026-01-27)
- Key changes: RAG service with /ingest + /query, OpenAI embeddings/chat, Qdrant retrieval, unit tests.
- Commands: `make rag-test`, `make init-kb`.
- Known issues: Requires valid OpenAI key; Qdrant dependency for retrieval.

### Module 2.1 (2026-01-27)
- Key changes: safety hardening (no fake embeddings), safer fallback responses on failures, expanded rag-test.
- Commands: `make rag-test`.
- Known issues: Embedding outages cause ingest to fail (expected).

### Module 3 (2026-01-28)
- Key changes: source-driven KB fetcher from official BookMyShow pages, ingest pipeline, rag-test gate requires embeddings.
- Commands: `make fetch-kb`, `make init-kb`, `make rag-test`.
- Known issues: Some help-centre pages return 403 or require JS rendering.

## Module 3.1 status (2026-01-28)
- Changes: improved crawl breadth (more seeds, BFS, pagination); stronger extraction cleanup; Hindi translation pipeline; traceability logs for discovered/blocked URLs.
- Commands: `make fetch-kb`, `make translate-hi`, `make init-kb`, `make rag-test`.
- KB counts (EN/HI): 139 EN, 0 HI (translation not run).
- Top categories: Solutions, Ratings & Reviews, BookMyShow Stream, BMS Cash, Ticket Booking Queries.
- Blocked pages (403/JS): https://in.bookmyshow.com/help-centre and topic pages (see `data/kb/sources/blocked_urls.json`).
- Next steps: validate OpenAI key, run translate-hi + ingest + rag-test, and review low-quality skips.

## Module 4 (2026-01-28)
- Changes: added `ai_powered_css` Frappe app with guest chat page `/support-chat`, chat API, session/message DocTypes, RAG history pass-through, ticket escalation with doctype fallbacks, and `make chat-test`. `make verify` no longer runs `init-kb`; `rag-test` assumes KB already ingested (no /ingest).
- Commands: `make helpdesk-install-app`, `docker compose restart helpdesk-backend`, `make chat-test`, `make verify`.
- Known issues: Helpdesk install failed due to missing `yarn`/`node` and `telephony` dependency; escalation falls back to `ToDo` (see `docs/BUGS.md`).

## Module 4.2 (2026-01-28)
- Changes: added official Helpdesk compose profile + init.sh, added legacy/official Makefile targets, set bench Python to 3.10, updated escalation to require `HD Ticket` unless fallback is enabled, and added a public `/support` entry page.
- Commands: `make down`, `make up`, `make verify`, `python3 scripts/init_kb.py`, `make up-helpdesk-official`, `make verify-full`.
- Known issues: `make down -v` clears Qdrant volume; KB must be re‑ingested once after a full teardown.

## Module 4.3 (2026-01-28)
- Changes: added escalation policy (greetings/short messages skip RAG, 2-step low-confidence escalation with very-low immediate), added explicit create-ticket + guest ticket status endpoints, filtered low-score sources via MIN_TOP_SCORE, added Helpdesk admin password env + print-creds, and expanded chat-test coverage.
- Commands: `make up-helpdesk-official`, `make verify`, `make verify-full`.
- Outputs: `make verify-full` passed; chat-test printed greeting/no-ticket, low-confidence escalation (HD Ticket), create-ticket + status check, auto-escalation behavior, and Hindi greeting.
- Known issues: curl connection resets during rag-test Qdrant-down simulation (expected, handled by retries).

## Module 4.4 (2026-01-28)
- Changes: added Roman Hindi normalization in RAG, 3-state resolution engine (ANSWERED / NEEDS_CLARIFICATION / UNRESOLVED), domain-aware refund/payment clarification prompts + quick replies, Hindi-only responses for Hindi inputs, structured HD Ticket formatting, and chat UI polish (new chat, details toggle, quick replies, improved banner).
- Commands: `make verify-full`.
- Outputs: `make verify-full` passed; chat-test covered Roman Hindi, clarification flow, auto-escalation after repeated clarification, ticket format validation, and new-chat session check.
- Known issues: occasional curl connection resets during Qdrant-down simulation; retries handle this.

## Module 4.5 (2026-01-28)
- Changes: enforced KB-first retrieval for specific + quick-reply follow-ups, persisted issue subtype in sessions, suppressed external-channel suggestions (prompt + sanitizer), tightened Roman Hindi detection (default EN + ambiguity prompt), and expanded ticket formatting with System Metadata. Confidence weights adjusted (0.5/0.5) to reduce false-low scores.
- Commands: `make up-helpdesk-official`, `make verify-full` (reran after Helpdesk finished initializing).
- Outputs: `make verify-full` passed; chat-test validated auto English, Roman Hindi, quick-reply retrieval + follow-up, explicit ticket request, repeated clarification escalation, and ticket format sections (ticket #6). 
- Known issues: occasional curl connection resets during Qdrant-down simulation; retries handle this.

## Module 4.6 (2026-01-28)
- Changes: switched to a single Postgres-only compose stack, removed MariaDB profiles, added Helpdesk SLA Postgres patch, and enabled polling-based real-time chat updates via `get_messages`.
- Commands: `make down -v`, `make up`, `make verify-full`.
- Outputs: `make verify-full` passed on Postgres (rag-test + chat-test + smoke).
- Known issues: none new; Postgres SLA issue resolved.

## Module 4.7 (2026-01-29)
- Changes: added UI-only onboarding flow (name → mood → help intent) stored in localStorage, required contact capture before ticket creation, clarified ticket description sections with customer details, standardized polling-only realtime flow, and restored guest context to avoid “User None is disabled” errors.
- Commands: `make verify-full`.
- Outputs: `make verify-full` passed (rag-test + chat-test + smoke).
- Known issues: none new.

## Module 4.7.1 (2026-01-29)
- Changes: updated branding to BookYourShow in chat UI, adjusted onboarding prompt copy, added assistant avatar for friendlier UI, and refreshed documentation (root README + docs index + deployment URLs).
- Commands: n/a (UI + docs only).
- Known issues: none new.
