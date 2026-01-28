# Architecture Decision Records (ADR)

## Initial decisions (2026-01-27)

| Decision | Choice | Rationale |
| --- | --- | --- |
| LLM provider | OpenAI | Reliable chat + embedding models; broad ecosystem support. |
| Vector database | Qdrant | Lightweight, open-source, easy local deployment. |
| CRM / ticketing | Frappe Helpdesk | Required by assessment; native Frappe integration. |
| Supported languages | EN + HI | Covers English and Hindi user base requirements. |

## Module 1 decisions (2026-01-27)

| Decision | Choice | Rationale |
| --- | --- | --- |
| Compose baseline | frappe_docker-style dev stack | Matches known-good multi-container Frappe patterns. |
| Database (dev) | MariaDB | Stable for Frappe dev; PRD mismatch noted, Postgres profile planned. |
| Env file | `infra/.env` | Single source for compose env vars; template in `infra/env.example`. |
| Verify workflow | `make verify` | One-command validation for reviewers (boot + init + smoke). |

## Module 2 decisions (2026-01-27)

| Decision | Choice | Rationale |
| --- | --- | --- |
| Chunking method | Word-based (target 800 words, overlap 80) | Simple token approximation to keep ~500-1000 token chunks. |
| Language handling | Detect Devanagari; embed query as-is | OpenAI embeddings are multilingual; avoids translation complexity. |
| Confidence formula | `0.6 * top_score + 0.4 * self_confidence` | Blend retrieval similarity with model self-assessment. |
| Collection schema | Qdrant payload includes doc_id/title/chunk_id/tags/lang/chunk_text | Keeps sources traceable and debuggable. |

## Module 2.1 decisions (2026-01-27)

| Decision | Choice | Rationale |
| --- | --- | --- |
| Embedding failure handling | Fail-safe (no fake embeddings) | Safer to escalate than retrieve with incorrect vectors and hallucinate. |

## Module 3 decisions (2026-01-28)

| Decision | Choice | Rationale |
| --- | --- | --- |
| KB source policy | Only official BookMyShow support/help pages | Prevents hallucinated policies; ensures traceable sources. |
| Hindi support | Translate fetched English articles only | Avoids inventing content; preserves fidelity to source. |
| RAG quality gate | `make rag-test` fails on missing OpenAI key or ingest errors | Ensures retrieval quality is tested against real embeddings. |

## Module 3.1 decisions (2026-01-28)

| Decision | Choice | Rationale |
| --- | --- | --- |
| Crawl strategy | BFS from seed URLs with depth/page caps + discovered/blocked URL logs | Expands coverage while remaining traceable and rate-limit friendly. |
| Extraction cleanup | Prefer article-body selectors; strip boilerplate/feedback UI; skip <200-char bodies | Improves signal-to-noise for RAG context. |
| Translation workflow | Separate `make translate-hi` step with env limits | Keeps costs controlled and avoids translating low-quality content. |

## Module 4 decisions (2026-01-28)

| Decision | Choice | Rationale |
| --- | --- | --- |
| Chat access | Website page `/support-chat` in guest mode | Enables local demo without Desk login. |
| Session persistence | Store sessions + messages in custom DocTypes | Keeps 10–20 message history for RAG and auditing. |
| RAG history handling | Pass history for generation only (not retrieval) | Prevents irrelevant retrieval drift while keeping context for answers. |
| Escalation | Auto-create ticket when confidence < CONF_THRESHOLD (default 0.7) | Aligns PRD; safe fallback to human support. |
| Ticket doctype fallback | HD Ticket only (Module 4.2 allows ToDo via `ESCALATION_FALLBACK=todo`) | Avoids silent escalation to non-Helpdesk doctypes. |

## Module 4.2 decisions (2026-01-28)

| Decision | Choice | Rationale |
| --- | --- | --- |
| Helpdesk stack | Add official `frappe/helpdesk` docker init profile | Aligns with upstream dev setup and enables HD Ticket creation. |
| Escalation default | Create `HD Ticket` only; no fallback unless `ESCALATION_FALLBACK=todo` | Prevents silent fallback to non‑Helpdesk doctypes. |
| Bench Python version | `PYENV_VERSION=3.10.13` for `frappe/bench:latest` | Avoids pypika build errors seen on Python 3.14. |

## Module 4.3 decisions (2026-01-28)

| Decision | Choice | Rationale |
| --- | --- | --- |
| Escalation policy | Two-step low-confidence (offer, then auto) + very-low immediate escalation | Avoids tickets for greetings while still escalating unresolved queries. |
| Greeting/short routing | Skip RAG + no tickets for greetings/very short messages | Prevents junk sources and unnecessary escalation. |
| Source gating | Drop sources when top score < MIN_TOP_SCORE (default 0.35) | Reduces irrelevant context in responses. |
| Guest ticket status | Public `get_ticket_status` endpoint | Enables POC verification without Desk login. |

## Module 4.4 decisions (2026-01-28)

| Decision | Choice | Rationale |
| --- | --- | --- |
| Roman Hindi handling | Normalize via OpenAI to Hindi+English, run multi-embedding retrieval | Improves retrieval accuracy for Hinglish queries. |
| Resolution states | 3-state engine: ANSWERED / NEEDS_CLARIFICATION / UNRESOLVED | Prevents premature escalation for broad questions. |
| Hindi-only responses | Force Hindi output when input is Hindi or Roman Hindi | Avoids mixed-language replies for Hindi users. |
| Ticket format | Structured ticket description with summary, transcript, sources, next steps | Improves agent readability and triage quality. |

## Module 4.5 decisions (2026-01-28)

| Decision | Choice | Rationale |
| --- | --- | --- |
| Auto language policy | Default English; Hindi only when Devanagari or high-confidence Roman Hindi | Reduces noisy Hindi replies for English queries. |
| Language ambiguity | Ask for preference with buttons instead of guessing | Keeps auto mode conservative and user-controlled. |
| KB-first flow | Clarify only for vague queries or low-evidence retrieval | Ensures KB answers are attempted before escalation. |
| Answer threshold | ANSWERED requires sources_count ≥ 1 and top_score ≥ ANSWER_TOP_SCORE | Prevents confident replies without KB evidence. |
| Confidence calibration | 0.6 retrieval + 0.4 self-confidence weights | Keeps confidence aligned with retrieval strength. |
| Escalation offer timing | Offer after 2nd user turn / failed clarification / very-low confidence | Prevents premature ticket prompts. |
| External channel suppression | Prompt + sanitizer block live chat/email/WhatsApp unless in KB | Avoids hallucinated support channels. |
| Ticket readability | Add Key Details section + bounded transcript | Faster scanning for Helpdesk agents. |

## Next decisions to capture
- Postgres override/profile for PRD alignment.
- Observability and logging stack.
- Auth/session strategy for chat.
