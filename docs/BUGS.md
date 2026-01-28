# Bugs / Known Issues

## Open issues
- RAG responses can still hallucinate if the LLM ignores context; mitigated via prompt and confidence gate.
- Hindi/English detection is heuristic and may misclassify mixed-language queries.
- OpenAI quota/rate limits cause /ingest to return 503 and /query to return low-confidence safe responses.
- Some BookMyShow help pages are JS-rendered; fetcher may capture limited content in static HTML.
- Aggressive rate limiting or bot protection may block certain pages; retry or reduce fetch speed.
- Observed HTTP 403 from in.bookmyshow.com/help-centre during fetch; support.bookmyshow.com works.
- Blocked during latest crawl (see `data/kb/sources/blocked_urls.json`): https://in.bookmyshow.com/help-centre, https://in.bookmyshow.com/help-centre/topic/4000034343, https://in.bookmyshow.com/help-centre/topic/4000038106, https://in.bookmyshow.com/help-centre/topic/4000038113.
- If `/helpdesk` shows `User None is disabled`, it is usually a stale session cookie; clear site cookies or use an incognito window.

## Resolved issues (chronological)
### Module 4.3
- Greeting or small-talk messages created tickets; now handled by EscalationPolicy (no RAG, no tickets).
- Irrelevant sources for greetings/short messages; now routed away from RAG and filtered via MIN_TOP_SCORE.
- Ticket visibility for POC demos; use `make print-creds` and `/api/method/ai_powered_css.api.chat.get_ticket_status`.

### Module 4.4
- Broad refund/payment questions triggered tickets; now routed to NEEDS_CLARIFICATION with targeted questions.
- Roman Hindi queries were misclassified; now normalized and answered in Hindi only.
- Ticket descriptions lacked structure; now include summary, transcript, sources, and next steps.

### Module 4.5
- Auto mode replied in Hindi for English queries; Roman-Hindi detection tightened with ambiguity prompt.
- Ticket offers appeared too early; escalation now follows multi-turn offer/auto rules.
- Quick replies looped instead of running KB retrieval; selection now persists subtype and drives RAG follow-ups.
- Answers suggested live chat/email without KB evidence; prompts + sanitizer now suppress external channels.
- Ticket description was hard to scan; added structured sections + system metadata.
- Chat UI showed confidence as `n/a` for older localStorage entries or empty responses; UI now normalizes stored messages and defaults confidence to 0.

### Module 4.6
- Helpdesk install failed on Postgres with `smallint = boolean` SLA query error; patched Helpdesk SLA filters to compare integer flags on Postgres.

### Module 4.7+
- Contact form input was clearing/resetting; moved contact capture into chat flow.
- Auto-scroll forced the view to bottom while reading older messages; now only auto-scrolls if near bottom.
- Follow-up queries (e.g., “15 days”) lost context; follow-up detection now uses issue subtype + KB retrieval.
- Contact prompt repeated “Create Ticket” and re-sent the same prompt; CTA hidden while contact is required.
- Ticket confirmation copy was too short; replaced with clear “ticket ID + 24-hour contact” message.
- Ticket customer name not captured from onboarding; now inferred from prior chat history when creating tickets.
- HD Ticket creation failed (404/DoesNotExistError) due to missing Helpdesk defaults (ticket statuses, template, settings). Fixed by seeding minimal defaults (Default template with `template_name`, Open/Replied/Resolved/Closed statuses, priority/type, and required HD Settings fields).
- HD Ticket creation failed during SLA application on Postgres because `ignore_permissions` was passed to `get_last_doc` (unsupported in this version). Patched `apply_sla` to safely no-op when SLA is absent and avoid the unsupported argument.

### Module 4.7
- `/helpdesk` could show “User None is disabled” after guest polling requests; restored user context to `Guest` when missing to avoid invalid session state.

## Known limitations
- Roman Hindi normalization depends on OpenAI availability and may be imperfect for rare slang.
- Clarification heuristics are keyword-based and can miss edge cases.

## Operational notes
- `infra/.env` is the single env source; template is `infra/env.example`.
- `make verify` is the preferred fast check; `make verify-full` runs end-to-end tests.

## Reporting template
- **ID**: BUG-000
- **Summary**:
- **Steps to reproduce**:
- **Expected**:
- **Actual**:
- **Severity**: Low | Medium | High
- **Owner**:
- **Status**: Open | In Progress | Resolved
