# AI Chatbot Architecture (Implementation-Accurate)

This document is derived from the current codebase. All component names and flows map to real files and endpoints.

**Primary implementation references**
- Chat API + decision engine: `apps/ai_powered_css/ai_powered_css/api/chat.py`
- Chat UI (polling client): `apps/ai_powered_css/ai_powered_css/www/support-chat.html`
- Chat session/message storage: `apps/ai_powered_css/ai_powered_css/chat/doctype/*/*.json`
- RAG service: `services/rag/app/main.py`, `services/rag/app/rag.py`, `services/rag/app/openai_client.py`
- KB ingestion scripts: `scripts/fetch_bms_kb.py`, `scripts/translate_kb_hi.py`, `scripts/init_kb.py`
- Infra / services: `infra/docker-compose.yml`, `infra/helpdesk/init.sh`

---

## 1) End-to-end runtime flow (chat to ticket)

```mermaid
flowchart LR
  subgraph Client[Client / Browser]
    UI[Support Chat Page
/support-chat
support-chat.html]
  end

  subgraph Frappe[Frappe App: ai_powered_css]
    ChatAPI[/POST ai_powered_css.api.chat.send_message/]
    PollAPI[/GET ai_powered_css.api.chat.get_messages/]
    ChatState[(AI CSS Chat Session + Message
Postgres)]
    Ticket[HD Ticket (Helpdesk)]
  end

  subgraph RAG[FastAPI RAG Service]
    Query[/POST /query/]
  end

  subgraph Storage[Storage]
    Qdrant[(Qdrant Vector DB)]
    Postgres[(Postgres)]
  end

  OpenAI[(OpenAI API
Embeddings + Chat)]

  UI -->|polling JSON| PollAPI
  UI -->|message JSON| ChatAPI
  ChatAPI --> ChatState
  ChatState --> Postgres

  ChatAPI -->|RAG query| Query
  Query --> Qdrant
  Query --> OpenAI
  Query --> ChatAPI

  ChatAPI -->|create ticket| Ticket
  Ticket --> Postgres
```

**Inputs/Outputs**
- UI sends `{session_id, message, lang_hint}` to `send_message` and polls `get_messages` for incremental updates.
- Chat API sends `{session_id, user_query, lang_hint, top_k, history}` to `POST /query`.
- RAG returns `{answer, confidence, language, sources, retrieved_k}`.
- Ticket creation includes structured description + transcript.

**State / Storage**
- Conversation state is stored in **Postgres** via DocTypes:
  - `AI CSS Chat Session` (language, state counters) and `AI CSS Chat Message` (content, confidence, sources JSON).
- Tickets stored as **HD Ticket** in Postgres (Helpdesk app).
- Embeddings stored in **Qdrant** (`QDRANT_COLLECTION`).

**Guardrails / Resolution Logic**
- Decision engine and language rules live in `apps/ai_powered_css/ai_powered_css/api/chat.py`.
- RAG prompts are grounded to KB context only (`services/rag/app/rag.py`).
- Ticket escalation requires explicit intent or repeated low confidence.

**Operational notes**
- RAG call has retry + safe fallback on errors (`send_message`, `services/rag/app/main.py`).
- Polling provides near real-time updates; UI shows Connected/Disconnected.
- If RAG is unavailable, chat returns safe low-confidence response.

---

## 2) Language analyzer + decision engine flow (3-state)

```mermaid
flowchart TD
  A[Incoming message
send_message] --> B{Language mode?}
  B -->|lang_hint=en/hi| C[Force language]
  B -->|Auto| D[Detect Devanagari]
  D -->|yes| C
  D -->|no| E[Roman Hindi decision
(_roman_hindi_decision)]
  E -->|hi| C
  E -->|ambiguous| L[Ask language preference
quick replies]
  E -->|en| C

  C --> F{Closing message?}
  F -->|yes| Z[Send closing reply
ANSWERED]
  F -->|no| G{Greeting?}
  G -->|yes| H[Greeting reply
ANSWERED]
  G -->|no| I{Too short?}
  I -->|yes| J[Short clarify
NEEDS_CLARIFICATION]
  I -->|no| K{Explicit ticket request?}
  K -->|yes| U[UNRESOLVED
collect contact]
  K -->|no| M[Intent + quick reply mapping]
  M --> N{Vague intent?}
  N -->|yes| O[Clarify + quick replies
NEEDS_CLARIFICATION]
  N -->|no| P[RAG /query]
  P --> Q{Sources usable &
score >= ANSWER_TOP_SCORE?}
  Q -->|yes| R[ANSWERED]
  Q -->|no| S{Very low + high risk
or attempts >= max?}
  S -->|yes| U
  S -->|no| O
```

**Inputs/Outputs**
- Inputs: user message, `lang_hint`, session history, session counters.
- Outputs: `resolution_state` in `{ANSWERED, NEEDS_CLARIFICATION, UNRESOLVED}` + `quick_replies` + `contact_required`.

**State / Storage**
- Session counters stored in `AI CSS Chat Session`:
  - `low_conf_count`, `clarification_count`, `last_resolution_state`, `issue_category`, `issue_subtype`.

**Guardrails / Logic**
- Closing detection (`_is_closing_message`) responds with a final thank-you and does not call RAG.
- Greetings and short inputs are handled without retrieval.
- RAG answers require **usable sources** and score >= `ANSWER_TOP_SCORE`.
- Escalation occurs after repeated low confidence or high-risk conditions.

**Operational notes**
- Language preference prompt occurs when Roman Hindi detection is ambiguous.
- Roman Hindi is converted via OpenAI before retrieval (RAG service).

---

## 3) RAG retrieval + response generation

```mermaid
flowchart LR
  A[POST /query
user_query + history] --> B[Detect language + roman hindi]
  B -->|roman hi| C[OpenAI roman-hindi convert]
  B -->|en/hi| D[Embed texts (OpenAI)]
  C --> D
  D --> E[Qdrant search
(top_k)]
  E --> F[Pick best results
(top_score)]
  F --> G[Prompt build
(system + context + history)]
  G --> H[OpenAI chat JSON]
  H --> I[Compute confidence
(top_score + self_confidence)]
  I --> J[Return answer + sources]
```

**Inputs/Outputs**
- Input: `{session_id, user_query, lang_hint, top_k, history}`.
- Output: `{answer, confidence, language, sources, retrieved_k}`.

**State / Storage**
- Vector embeddings stored in Qdrant (collection from `QDRANT_COLLECTION`).
- No server-side response cache; each `/query` hits OpenAI + Qdrant.

**Guardrails / Logic**
- Embeddings failure → safe low-confidence response (`safe_query_response`).
- Prompt strictly requires KB grounding and blocks external channel suggestions.
- Confidence combines retrieval score + model self-confidence (`services/rag/app/confidence.py`).

**Operational notes**
- Roman Hindi conversion uses OpenAI chat JSON in `OpenAIClient.roman_hindi_to_hi_en`.
- History is used only for generation context, not embeddings.

---

## 4) Knowledge ingestion pipeline

```mermaid
flowchart LR
  A[Seed URLs
bookmyshow_seeds.json] --> B[fetch_bms_kb.py]
  B --> C[Raw HTML
 data/kb/raw/*.html]
  B --> D[Cleaned JSON
 data/kb/articles/*.json]
  D --> E[translate_kb_hi.py (optional)]
  E --> F[Hindi JSON
 data/kb/articles/*.hi.json]
  D --> G[init_kb.py]
  F --> G
  G --> H[POST /ingest
RAG service]
  H --> I[Chunk + embed
(OpenAI)]
  I --> J[Upsert vectors
Qdrant]
```

**Inputs/Outputs**
- Input: Seed URLs + crawl config.
- Output: JSON articles (`data/kb/articles`) and Qdrant vectors.

**State / Storage**
- Raw HTML cached in `data/kb/raw/`.
- Cleaned article JSON in `data/kb/articles/`.
- Vectors stored in Qdrant.

**Guardrails / Logic**
- Fetcher filters allowed domains and cleans boilerplate.
- Translation is optional and controlled by `KB_TRANSLATE_HI`.
- Ingestion fails if OpenAI or RAG API key is missing.

**Operational notes**
- Chunking uses word-based approximation (500–1000 words) in `services/rag/app/chunking.py`.
- Ingest endpoint enforces API key and returns 503 when embeddings are unavailable.

---

## Future improvements (documented but not implemented)
- **Semantic caching**: L1 response cache + L2 retrieval cache (keys by normalized query + language; TTLs; invalidation on KB updates).
- **Verifier/critic pass**: post-generation QA to detect hallucinations before returning an ANSWERED state.
