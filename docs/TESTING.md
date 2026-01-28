# Testing

## Test levels
- **Smoke**: basic startup and critical endpoints (see `scripts/smoke_test.sh`).
- **Unit**: RAG retrieval, prompt assembly, confidence scoring.
- **Integration**: end-to-end chat -> RAG -> decision -> ticket creation.

## Sample test queries
**Resolvable**
- "How do I reset my password?"
- "What are your refund policies?"

**Partially resolvable**
- "My payment failed yesterday, what can I do?"

**Unresolvable**
- "My account was hacked and locked, please restore it."

**Edge cases**
- "asdfasdf" (nonsense)
- "I need help" (ambiguous)

## Expected behavior
- High-confidence responses return an answer with sources.
- Low-confidence responses create a CRM ticket and return a ticket id.
