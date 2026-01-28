# Architecture

## Components
1. **Chat UI (Frappe)**
   - Web page or custom app inside Frappe.
   - Maintains session context and shows last 10-20 messages.
2. **Chat Service**
   - Orchestrates requests between UI, RAG, and CRM.
   - Handles retries, timeouts, and error mapping to UI.
3. **RAG Service**
   - Embeds documents and queries.
   - Retrieves top-K chunks from Qdrant.
   - Generates responses using LLM with retrieved context.
4. **Decision Engine**
   - Compares confidence score with threshold.
   - Routes resolved responses or triggers ticket creation.
5. **CRM (Frappe/Helpdesk)**
   - Receives auto-created tickets for unresolved queries.

## Data flow
```
User Message
  -> Chat API
  -> RAG retrieve + generate
  -> Confidence score
     -> High: Answer returned
     -> Low: Ticket created in CRM
```

## Key artifacts
- `data/kb/` holds raw knowledge base documents.
- `services/` will contain RAG pipeline and chat orchestration.
- `apps/` will contain Frappe UI and DocTypes.

## Non-functional notes
- Observability: log every request with correlation IDs.
- Security: avoid logging secrets, redact PII.
- Reliability: fail open to ticket creation when RAG is uncertain.
