#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-infra/.env}"
RAG_URL="${RAG_URL:-http://localhost:8001}"
COMPOSE="docker compose --env-file ${ENV_FILE} -f infra/docker-compose.yml"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: Missing env file at $ENV_FILE"
  exit 1
fi

# Load env vars from file
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ "$RAG_URL" == http://rag:* ]]; then
  RAG_URL="http://localhost:8001"
fi

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "ERROR: OPENAI_API_KEY is required for rag-test. Update infra/.env."
  exit 1
fi

if [ -z "${RAG_API_KEY:-}" ]; then
  echo "ERROR: RAG_API_KEY is required for rag-test. Update infra/.env."
  exit 1
fi

CONF_THRESHOLD="${CONF_THRESHOLD:-0.7}"

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required."
  exit 1
fi

request_json() {
  local url="$1"
  local data="$2"
  local api_key="${3-}"
  local response
  local headers=("-H" "Content-Type: application/json")
  local attempts=5
  local body=""
  local code=""

  if [ -n "$api_key" ]; then
    headers+=("-H" "x-api-key: ${api_key}")
  fi

  for attempt in $(seq 1 "$attempts"); do
    response=$(curl --retry 2 --retry-delay 1 --retry-connrefused -sS -w "\n%{http_code}" \
      "${headers[@]}" \
      -X POST "$url" \
      -d "$data" || true)
    if [ -z "$response" ]; then
      sleep 1
      continue
    fi
    body=$(echo "$response" | sed '$d')
    code=$(echo "$response" | tail -n 1)
    if [ "$code" != "000" ]; then
      break
    fi
    sleep 1
  done
  if [ -z "${code}" ] || [ "$code" = "000" ]; then
    echo "ERROR: RAG endpoint not reachable at $url"
    exit 1
  fi
  echo "$code" > /tmp/rag_last_code.txt
  echo "$body" > /tmp/rag_last_body.json
}

print_query_summary() {
  local label="$1"
  python3 - <<'PY' "$label"
import json
import sys

label = sys.argv[1]
with open("/tmp/rag_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
answer = body.get("answer", "")
confidence = body.get("confidence")
language = body.get("language")
sources = body.get("sources") or []
summary = {
    "label": label,
    "answer_preview": answer[:200],
    "confidence": confidence,
    "language": language,
    "sources_count": len(sources),
    "top_source": None,
}
if sources:
    top = sources[0]
    summary["top_source"] = {
        "title": top.get("title"),
        "doc_id": top.get("doc_id"),
        "chunk_id": top.get("chunk_id"),
        "score": top.get("score"),
    }
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY
}

assert_unanswerable() {
  python3 - <<'PY'
import json
import os
import sys

with open("/tmp/rag_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
conf = float(body.get("confidence", 0))
threshold = float(os.getenv("CONF_THRESHOLD", "0.7"))
sources = body.get("sources") or []
answer = (body.get("answer") or "").lower()

if conf < threshold or not sources:
    sys.exit(0)

if "not sure" in answer or "insufficient" in answer or "नहीं" in answer:
    sys.exit(0)

print("ERROR: unanswerable query did not fail safe")
sys.exit(1)
PY
}

assert_safe_response() {
  python3 - <<'PY'
import json
import sys

with open("/tmp/rag_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
conf = float(body.get("confidence", 0))
sources = body.get("sources") or []
if conf != 0.0:
    print(f"ERROR: expected confidence 0.0, got {conf}")
    sys.exit(1)
if sources:
    print("ERROR: expected no sources when vector store unavailable")
    sys.exit(1)
PY
}

wait_for_url() {
  local url="$1"
  local attempts=20
  local count=1
  while [ "$count" -le "$attempts" ]; do
    if curl -sS -o /dev/null -w "%{http_code}" "$url" | grep -q 200; then
      return 0
    fi
    sleep 1
    count=$((count + 1))
  done
  return 1
}

if ! wait_for_url "${RAG_URL}/health"; then
  echo "ERROR: RAG service not ready at ${RAG_URL}"
  exit 1
fi

# Edge cases: missing/invalid API key
EDGE_PAYLOAD='{"session_id":"edge","user_query":"Test","lang_hint":"en"}'
request_json "${RAG_URL}/query" "$EDGE_PAYLOAD" ""
if [ "$(cat /tmp/rag_last_code.txt)" != "401" ]; then
  echo "ERROR: missing API key did not return 401"
  cat /tmp/rag_last_body.json
  exit 1
fi

request_json "${RAG_URL}/query" "$EDGE_PAYLOAD" "bad-key"
if [ "$(cat /tmp/rag_last_code.txt)" != "401" ]; then
  echo "ERROR: invalid API key did not return 401"
  cat /tmp/rag_last_body.json
  exit 1
fi

# Empty query
EMPTY_PAYLOAD='{"session_id":"edge","user_query":" ","lang_hint":"en"}'
request_json "${RAG_URL}/query" "$EMPTY_PAYLOAD" "${RAG_API_KEY}"
if [ "$(cat /tmp/rag_last_code.txt)" != "400" ]; then
  echo "ERROR: empty query did not return 400"
  cat /tmp/rag_last_body.json
  exit 1
fi

# Very long query (6000 chars)
python3 - <<'PY' > /tmp/rag_long_query.json
import json
query = "a" * 6000
print(json.dumps({"session_id": "edge", "user_query": query, "lang_hint": "en"}))
PY
request_json "${RAG_URL}/query" "$(cat /tmp/rag_long_query.json)" "${RAG_API_KEY}"
if [ "$(cat /tmp/rag_last_code.txt)" != "200" ]; then
  echo "ERROR: long query did not return 200"
  cat /tmp/rag_last_body.json
  exit 1
fi

# Load one EN doc (fetched) to craft a query (assumes KB already ingested)
python3 - <<'PY' > /tmp/rag_doc_en.json
import glob
import json
import sys

files = [f for f in glob.glob("data/kb/articles/*.json") if not f.endswith(".hi.json")]
if not files:
    print("ERROR: No KB articles found. Run: make fetch-kb")
    sys.exit(1)

def load_doc(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

docs = [load_doc(p) for p in files]
doc = max(docs, key=lambda d: len((d.get("body") or "").strip()))
body = (doc.get("body") or "").strip()
lines = [line.strip() for line in body.splitlines() if line.strip()]
query_text = lines[0] if lines else (doc.get("title") or doc["doc_id"])
if len(query_text) < 10:
    query_text = f"What is {doc.get('title') or doc['doc_id']}?"
query_text = query_text[:200]

payload = {
    "doc_id": doc["doc_id"],
    "title": doc.get("title") or doc["doc_id"],
    "lang": doc.get("lang", "en"),
    "query_text": query_text,
}
print(json.dumps(payload))
PY

if [ ! -s /tmp/rag_doc_en.json ]; then
  exit 1
fi

# EN query
python3 - <<'PY' > /tmp/rag_query_en.json
import json
with open("/tmp/rag_doc_en.json", "r", encoding="utf-8") as f:
    doc = json.load(f)
query = doc.get("query_text") or doc.get("title") or ""
payload = {
    "session_id": "sess-en",
    "user_query": query,
    "lang_hint": "en",
    "history": [{"role": "user", "content": "Earlier context message."}],
}
print(json.dumps(payload))
PY

request_json "${RAG_URL}/query" "$(cat /tmp/rag_query_en.json)" "${RAG_API_KEY}"
if [ "$(cat /tmp/rag_last_code.txt)" != "200" ]; then
  echo "ERROR: EN /query failed"
  cat /tmp/rag_last_body.json
  exit 1
fi
print_query_summary "EN_QUERY"

python3 - <<'PY'
import json
import sys
with open("/tmp/rag_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
conf = float(body.get("confidence", 0))
top_score = 0.0
if body.get("sources"):
    try:
        top_score = float(body.get("sources")[0].get("score") or 0.0)
    except Exception:
        top_score = 0.0
if conf <= 0.5 and top_score <= 0.5:
    print(f"ERROR: confidence too low: {conf} (top_score={top_score})")
    print("Hint: KB may not be ingested. Run: make init-kb")
    sys.exit(1)
if not body.get("sources"):
    print("ERROR: expected sources for EN query")
    print("Hint: KB may not be ingested. Run: make init-kb")
    sys.exit(1)
PY

# Hindi query if Hindi KB exists (assumes already ingested)
python3 - <<'PY' > /tmp/rag_doc_hi.json
import glob
import json
import sys

files = [f for f in glob.glob("data/kb/articles/*.hi.json")]
if not files:
    sys.exit(0)

path = sorted(files)[0]
with open(path, "r", encoding="utf-8") as f:
    doc = json.load(f)

payload = {
    "doc_id": doc["doc_id"],
    "title": doc.get("title") or doc["doc_id"],
    "lang": doc.get("lang", "hi"),
}
print(json.dumps(payload))
PY

if [ -s /tmp/rag_doc_hi.json ]; then
  python3 - <<'PY' > /tmp/rag_query_hi.json
import json
with open("/tmp/rag_doc_hi.json", "r", encoding="utf-8") as f:
    doc = json.load(f)
query = f"कृपया बताएं: {doc.get('title','')}"
print(json.dumps({"session_id": "sess-hi", "user_query": query, "lang_hint": "hi"}))
PY

  request_json "${RAG_URL}/query" "$(cat /tmp/rag_query_hi.json)" "${RAG_API_KEY}"
  if [ "$(cat /tmp/rag_last_code.txt)" != "200" ]; then
    echo "ERROR: HI /query failed"
    cat /tmp/rag_last_body.json
    exit 1
  fi
  print_query_summary "HI_QUERY"
fi

# Unanswerable query
QUERY_NO='{"session_id":"sess-none","user_query":"What is the weather on Mars tomorrow?","lang_hint":"en"}'
request_json "${RAG_URL}/query" "$QUERY_NO" "${RAG_API_KEY}"
if [ "$(cat /tmp/rag_last_code.txt)" != "200" ]; then
  echo "ERROR: unanswerable /query failed"
  cat /tmp/rag_last_body.json
  exit 1
fi
print_query_summary "UNANSWERABLE_QUERY"
assert_unanswerable

# Qdrant unavailable simulation
${COMPOSE} stop qdrant || true
request_json "${RAG_URL}/query" "$(cat /tmp/rag_query_en.json)" "${RAG_API_KEY}"
if [ "$(cat /tmp/rag_last_code.txt)" != "200" ]; then
  echo "ERROR: query failed while qdrant stopped"
  cat /tmp/rag_last_body.json
  ${COMPOSE} start qdrant || true
  exit 1
fi
print_query_summary "QDRANT_DOWN_QUERY"
assert_safe_response
${COMPOSE} start qdrant || true
wait_for_url "http://localhost:6333/healthz" || true
wait_for_url "${RAG_URL}/health" || true

echo "RAG integration tests passed."
