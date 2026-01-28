# Bugs / Known Issues

## Open issues
- Module 1 uses MariaDB for Frappe dev stability; PRD calls for Postgres. Postgres profile is planned.
- Legacy Helpdesk site must be initialized once via `make helpdesk-init` before the frontend returns HTTP 200/302.
- Legacy Helpdesk install can fail in the current container due to missing `yarn`/`node` and `telephony` dependency; use `make up-helpdesk-official` for HD Ticket support.
- RAG responses can still hallucinate if the LLM ignores context; mitigated via prompt and confidence gate.
- Hindi/English detection is heuristic and may misclassify mixed-language queries.
- OpenAI quota/rate limits cause /ingest to return 503 and /query to return low-confidence safe responses.
- Some BookMyShow help pages are JS-rendered; fetcher may capture limited content in static HTML.
- Aggressive rate limiting or bot protection may block certain pages; retry or reduce fetch speed.
- Observed HTTP 403 from in.bookmyshow.com/help-centre during fetch; support.bookmyshow.com works.
- Blocked during latest crawl (see `data/kb/sources/blocked_urls.json`): https://in.bookmyshow.com/help-centre, https://in.bookmyshow.com/help-centre/topic/4000034343, https://in.bookmyshow.com/help-centre/topic/4000038106, https://in.bookmyshow.com/help-centre/topic/4000038113.

## Resolved in Module 4.3
- Greeting or small-talk messages created tickets; now handled by EscalationPolicy (no RAG, no tickets).
- Irrelevant sources for greetings/short messages; now routed away from RAG and filtered via MIN_TOP_SCORE.
- Ticket visibility for POC demos; use `make print-creds` and `/api/method/ai_powered_css.api.chat.get_ticket_status`.

## Resolved in Module 4.5
- Auto mode replied in Hindi for English queries; Roman-Hindi detection tightened with ambiguity prompt.
- Quick replies looped instead of running KB retrieval; selection now persists subtype and drives RAG follow-ups.
- Answers suggested live chat/email without KB evidence; prompts + sanitizer now suppress external channels.
- Ticket description was hard to scan; added structured sections + system metadata.

## Resolved (All tracked to date)
- Ticket escalation triggered on greetings; fixed with greeting router and no-RAG path.
- Ticket CTA appeared too early after first clarification; now suppressed when quick replies are present and only shown after prior clarification or very-low confidence.
- Chat UI showed confidence as `n/a` for older localStorage entries or empty responses; UI now normalizes stored messages and defaults confidence to 0.
- Ticket summaries were a single-line blob in Helpdesk Activity; switched to HTML description with headings and bullet transcript.
- Live chat / email / WhatsApp suggestions appeared even when not in KB; prompt + sanitizer now strip these unless explicitly in source content.
- Roman Hindi detection was too aggressive; now high-precision with ambiguity prompt.
- Clarification loop after selecting quick replies; subtype persists and follow-up queries go to RAG.

## Resolved in Module 4.4
- Broad refund/payment questions triggered tickets; now routed to NEEDS_CLARIFICATION with targeted questions.
- Roman Hindi queries were misclassified; now normalized and answered in Hindi only.
- Ticket descriptions lacked structure; now include summary, transcript, sources, and next steps.

## Resolved in Module 4.5
- Auto language sometimes replied in Hindi for English input; tightened Roman Hindi detection with conservative defaults.
- Ticket offers appeared too early; escalation now follows multi-turn offer/auto rules.
- Quick replies felt random; now gated to vague queries and refined queries trigger KB retrieval first.

## Known limitations
- Roman Hindi normalization depends on OpenAI availability and may be imperfect for rare slang.
- Clarification heuristics are keyword-based and can miss edge cases.

## Operational notes
- `infra/.env` is the single env source; template is `infra/env.example`.
- `make verify` is the preferred fast check (legacy stack). Use `make verify-full` for official Helpdesk + chat tests.

## Reporting template
- **ID**: BUG-000
- **Summary**:
- **Steps to reproduce**:
- **Expected**:
- **Actual**:
- **Severity**: Low | Medium | High
- **Owner**:
- **Status**: Open | In Progress | Resolved
