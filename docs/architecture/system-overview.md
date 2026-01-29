# System Overview

## What is this project?
BookYourShow AI Support is a Frappe Helpdesk + RAG system that provides a guest web chat UI, retrieves answers from a BookMyShow knowledge base, and escalates unresolved queries into Helpdesk tickets. It is a PRD-aligned POC with bilingual support (English/Hindi) and a 3-state resolution engine.

## Modules / Services (as implemented)
- **Frappe App (`ai_powered_css`)**: Chat API, session/message persistence, escalation, ticket creation. (`apps/ai_powered_css/ai_powered_css/api/chat.py`)
- **Support Chat UI**: Guest web page with polling for new messages. (`apps/ai_powered_css/ai_powered_css/www/support-chat.html`)
- **FastAPI RAG Service**: `/query` and `/ingest` endpoints. (`services/rag/app/main.py`)
- **Qdrant**: Vector DB for KB embeddings. (`infra/docker-compose.yml`)
- **Postgres**: Frappe + Helpdesk data store. (`infra/docker-compose.yml`)
- **KB Tooling**: Fetch → optional translation → ingest scripts. (`scripts/*.py`, `data/kb/`)

## Local development flow
- Start stack: `make up`
- Full verification: `make verify-full`
- KB pipeline: `make fetch-kb`, `make translate-hi` (optional), `make init-kb`

## Architecture docs
- **Detailed architecture + diagrams**: `docs/architecture/ai-chatbot-architecture.md`

## Future improvements (not implemented yet)
- **Semantic caching** (L1 response + L2 retrieval) to reduce repeated RAG calls.
- **Verifier/critic pass** to validate answers before returning an ANSWERED state.
