# Documentation Guide

This folder contains the project’s living documentation. Each file has a specific purpose and is meant to be read on its own.

## What each doc contains

- `ARCHITECTURE.md`
  - **What it is:** System design overview and component interactions.
  - **What you get:** Data flow, key services, storage choices, and how chat → RAG → Helpdesk fits together.

- `API.md`
  - **What it is:** API reference for RAG + chat endpoints.
  - **What you get:** Endpoint specs, request/response examples, auth headers, and error behavior.

- `BUGS.md`
  - **What it is:** Known issues and resolved bugs, tracked chronologically.
  - **What you get:** Repro notes, status, and operational caveats.

- `DECISIONS.md`
  - **What it is:** ADR-style decisions log.
  - **What you get:** Why we chose specific models, DB, escalation rules, polling, etc.

- `DEMO.md`
  - **What it is:** Demo checklist and scenario walkthroughs.
  - **What you get:** Suggested flows to show the product working end-to-end.

- `FEATURES.md`
  - **What it is:** Feature checklist by module.
  - **What you get:** Quick view of implemented vs planned capabilities.

- `MODULE_LOG.md`
  - **What it is:** Chronological record of module changes.
  - **What you get:** What changed, commands run, and known issues per module.

- `TESTING.md`
  - **What it is:** Test scenarios and expected behavior (PRD-aligned).
  - **What you get:** Query examples, edge cases, and verification notes.

## How to use this folder
- Start with `ARCHITECTURE.md` to understand the system.
- Use `API.md` for integration or debugging.
- Check `BUGS.md` and `MODULE_LOG.md` when troubleshooting.
