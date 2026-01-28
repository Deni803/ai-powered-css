# API (Draft)

## Chat Service
### POST /api/chat
Send a user message and receive an AI response or ticket escalation.

Request
```json
{
  "session_id": "abc123",
  "message": "How do I reset my password?",
  "locale": "en"
}
```

Response (resolved)
```json
{
  "status": "resolved",
  "answer": "You can reset your password by...",
  "confidence": 0.82,
  "sources": ["kb/article-001", "kb/article-007"]
}
```

Response (escalated)
```json
{
  "status": "escalated",
  "ticket_id": "TCK-000123",
  "message": "I've created a support ticket for your query."
}
```

## RAG Service
Base URL: `http://localhost:8001`

### POST /ingest
Adds a document to the knowledge base (chunked + embedded).

Headers
- `x-api-key: <RAG_API_KEY>`

Request
```json
{
  "doc_id": "kb-001",
  "title": "Refund timelines",
  "text": "Refunds are processed within 5-7 business days...",
  "tags": ["refunds", "payments"],
  "lang": "en"
}
```

Response
```json
{
  "ingested_chunks": 2,
  "doc_id": "kb-001"
}
```

Curl
```bash
curl -sS -X POST http://localhost:8001/ingest \
  -H "Content-Type: application/json" \
  -H "x-api-key: $RAG_API_KEY" \
  -d '{"doc_id":"kb-001","title":"Refund timelines","text":"Refunds are processed within 5-7 business days...","tags":["refunds"],"lang":"en"}'
```

### POST /query
Retrieves relevant chunks and generates an answer.

Headers
- `x-api-key: <RAG_API_KEY>`

Request
```json
{
  "session_id": "sess-123",
  "user_query": "When will my refund arrive?",
  "lang_hint": "en"
}
```

Response
```json
{
  "answer": "Refunds are processed within 5-7 business days...",
  "confidence": 0.78,
  "language": "en",
  "sources": [
    {"chunk_id": "kb-001#0", "doc_id": "kb-001", "title": "Refund timelines", "score": 0.82}
  ],
  "retrieved_k": 1
}
```

Curl
```bash
curl -sS -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -H "x-api-key: $RAG_API_KEY" \
  -d '{"session_id":"sess-123","user_query":"When will my refund arrive?","lang_hint":"en"}'
```

## CRM (Frappe/Helpdesk)
### POST /api/crm/tickets
Creates a helpdesk ticket when confidence is low.

Request
```json
{
  "subject": "Billing update failed",
  "description": "User: ...\nConversation: ...",
  "priority": "Medium",
  "tags": ["billing", "escalated"]
}
```

Response
```json
{
  "ticket_id": "TCK-000123",
  "status": "Open"
}
```
