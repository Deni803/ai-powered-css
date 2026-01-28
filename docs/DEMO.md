# Demo Guide

## Goal
Show end-to-end flow: chat -> RAG -> decision -> ticket creation.

## Prereqs
- Services running (`make up`).
- KB initialized (`make init-kb`).

## Demo steps
1. Open the chat UI in the Frappe site.
2. Ask a known KB question (e.g., "How do I change my plan?").
3. Verify AI response and sources are shown.
4. Ask an out-of-scope question (e.g., "I was charged twice for a ticket.").
5. Confirm ticket creation and display the ticket id.
6. Open CRM list view and show the new ticket details.

## Notes
- Record the screen or capture screenshots for submission.
- Use a mix of EN and HI prompts to show multilingual readiness.
