#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-infra/.env}"
BASE_URL="${CHAT_BASE_URL:-http://localhost:8000}"
API_URL="${BASE_URL}/api/method/ai_powered_css.api.chat.send_message"
API_TICKET_URL="${BASE_URL}/api/method/ai_powered_css.api.chat.create_ticket"
API_STATUS_URL="${BASE_URL}/api/method/ai_powered_css.api.chat.get_ticket_status"
API_MESSAGES_URL="${BASE_URL}/api/method/ai_powered_css.api.chat.get_messages"
RAG_HEALTH_URL="${RAG_HEALTH_URL:-http://localhost:8001/health}"
QDRANT_HEALTH_URL="${QDRANT_HEALTH_URL:-http://localhost:6333/healthz}"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: Missing env file at $ENV_FILE"
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "ERROR: OPENAI_API_KEY is required for chat-test. Update infra/.env."
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required."
  exit 1
fi

SESSION_BASE="chat-$(date +%s)-$(python3 - <<'PY'
import uuid
print(uuid.uuid4().hex[:8])
PY
)"

WAIT_ATTEMPTS="${CHAT_WAIT_ATTEMPTS:-60}"
WAIT_SLEEP="${CHAT_WAIT_SLEEP:-2}"

wait_for_url() {
  local url="$1"
  local count=1
  while [ "$count" -le "$WAIT_ATTEMPTS" ]; do
    if curl -sS -o /dev/null -w "%{http_code}" "$url" | grep -Eq "200|302"; then
      return 0
    fi
    sleep "$WAIT_SLEEP"
    count=$((count + 1))
  done
  return 1
}

if ! wait_for_url "$BASE_URL/"; then
  echo "ERROR: Helpdesk frontend not reachable at $BASE_URL"
  exit 1
fi

if ! wait_for_url "$RAG_HEALTH_URL"; then
  echo "ERROR: RAG service not reachable at $RAG_HEALTH_URL"
  exit 1
fi

if ! wait_for_url "$QDRANT_HEALTH_URL"; then
  echo "ERROR: Qdrant not reachable at $QDRANT_HEALTH_URL"
  exit 1
fi

request_json() {
  local url="$1"
  local data="$2"
  local response
  response=$(curl -sS -w "\n%{http_code}" -H "Content-Type: application/json" -X POST "$url" -d "$data")
  local body
  local code
  body=$(echo "$response" | sed '$d')
  code=$(echo "$response" | tail -n 1)
  echo "$code" > /tmp/chat_last_code.txt
  echo "$body" > /tmp/chat_last_body.json
}

request_ticket_json() {
  local data="$1"
  local response
  response=$(curl -sS -w "\n%{http_code}" -H "Content-Type: application/json" -X POST "$API_TICKET_URL" -d "$data")
  local body
  local code
  body=$(echo "$response" | sed '$d')
  code=$(echo "$response" | tail -n 1)
  echo "$code" > /tmp/chat_last_code.txt
  echo "$body" > /tmp/chat_last_body.json
}

print_response() {
  local label="$1"
  python3 - <<'PY' "$label"
import json
import sys

label = sys.argv[1]
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)

payload = body.get("message", body)
summary = {
  "label": label,
  "session_id": payload.get("session_id"),
  "answer_preview": (payload.get("answer") or "")[:200],
  "confidence": payload.get("confidence"),
  "language": payload.get("language"),
  "resolution_state": payload.get("resolution_state"),
  "sources_count": len(payload.get("sources") or []),
  "ticket_id": payload.get("ticket_id"),
  "ticket_type": payload.get("ticket_type"),
  "escalated": payload.get("escalated"),
  "escalation_offered": payload.get("escalation_offered"),
  "contact_required": payload.get("contact_required"),
  "quick_replies_count": len(payload.get("quick_replies") or []),
}
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY
}

# Greeting test
SESSION_ID="${SESSION_BASE}-greet"
export SESSION_ID
QUERY_GREETING=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("SESSION_ID", ""),
  "message": "hello",
  "lang_hint": ""
}))
PY
)
request_json "$API_URL" "$QUERY_GREETING"
if [ "$(cat /tmp/chat_last_code.txt)" != "200" ]; then
  echo "ERROR: chat greeting query failed"
  cat /tmp/chat_last_body.json
  exit 1
fi
print_response "CHAT_GREETING"
python3 - <<'PY'
import json
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
resp = body.get("message", body)
if resp.get("ticket_id"):
    raise SystemExit("ERROR: greeting should not create ticket")
PY

# Auto English: refund status
SESSION_ID="${SESSION_BASE}-en-auto"
export SESSION_ID
QUERY_EN_AUTO=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("SESSION_ID", ""),
  "message": "refund status",
  "lang_hint": ""
}))
PY
)
request_json "$API_URL" "$QUERY_EN_AUTO"
if [ "$(cat /tmp/chat_last_code.txt)" != "200" ]; then
  echo "ERROR: auto English query failed"
  cat /tmp/chat_last_body.json
  exit 1
fi
print_response "AUTO_EN"
python3 - <<'PY'
import json
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
resp = body.get("message", body)
if resp.get("language") != "en":
    raise SystemExit("ERROR: auto English should respond in English")
if (resp.get("quick_replies") or []) == []:
    raise SystemExit("ERROR: expected quick replies for vague refund query")
PY

# Resolvable query (KB-backed)
SESSION_ID="${SESSION_BASE}-resolvable"
export SESSION_ID
QUERY_RESOLVABLE=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("SESSION_ID", ""),
  "message": "Transaction didn\u2019t go thru and seats appeared to be blocked",
  "lang_hint": "en"
}))
PY
)
request_json "$API_URL" "$QUERY_RESOLVABLE"
if [ "$(cat /tmp/chat_last_code.txt)" != "200" ]; then
  echo "ERROR: resolvable query failed"
  cat /tmp/chat_last_body.json
  exit 1
fi
print_response "RESOLVABLE_QUERY"
python3 - <<'PY'
import json
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
resp = body.get("message", body)
if resp.get("resolution_state") != "ANSWERED":
    raise SystemExit("ERROR: expected ANSWERED for resolvable query")
if not resp.get("sources") or len(resp.get("sources") or []) < 1:
    raise SystemExit("ERROR: expected KB sources for resolvable query")
PY

# Roman Hindi refund -> needs clarification, Hindi response
SESSION_ID="${SESSION_BASE}-roman"
export SESSION_ID
QUERY_ROMAN=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("SESSION_ID", ""),
  "message": "mujhe refund ke liye help chahiye",
  "lang_hint": ""
}))
PY
)
request_json "$API_URL" "$QUERY_ROMAN"
if [ "$(cat /tmp/chat_last_code.txt)" != "200" ]; then
  echo "ERROR: roman hindi query failed"
  cat /tmp/chat_last_body.json
  exit 1
fi
print_response "ROMAN_HI_REFUND"
python3 - <<'PY'
import json, re
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
resp = body.get("message", body)
if resp.get("language") != "hi":
    raise SystemExit("ERROR: roman hindi should return language=hi")
if resp.get("ticket_id"):
    raise SystemExit("ERROR: roman hindi should not create ticket")
if resp.get("resolution_state") != "NEEDS_CLARIFICATION":
    raise SystemExit("ERROR: expected NEEDS_CLARIFICATION for roman hindi")
if not re.search(r"[\u0900-\u097F]", resp.get("answer") or ""):
    raise SystemExit("ERROR: expected Hindi answer for roman hindi")
PY

# Roman Hindi explicit ticket request
SESSION_ID="${SESSION_BASE}-roman-ticket"
export SESSION_ID
QUERY_ROMAN_TICKET=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("SESSION_ID", ""),
  "message": "tum ticket bana ke do",
  "lang_hint": ""
}))
PY
)
request_json "$API_URL" "$QUERY_ROMAN_TICKET"
if [ "$(cat /tmp/chat_last_code.txt)" != "200" ]; then
  echo "ERROR: roman hindi ticket query failed"
  cat /tmp/chat_last_body.json
  exit 1
fi
print_response "ROMAN_HI_TICKET"
python3 - <<'PY'
import json
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
resp = body.get("message", body)
if resp.get("ticket_id"):
    raise SystemExit("ERROR: ticket should not be created before contact")
if not resp.get("contact_required"):
    raise SystemExit("ERROR: expected contact_required for explicit request")
PY

# Provide contact in chat to create ticket
CONTACT_MESSAGE=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("SESSION_ID", ""),
  "message": "my email is test@example.com",
  "lang_hint": ""
}))
PY
)
request_json "$API_URL" "$CONTACT_MESSAGE"
if [ "$(cat /tmp/chat_last_code.txt)" != "200" ]; then
  echo "ERROR: contact submission failed"
  cat /tmp/chat_last_body.json
  exit 1
fi
print_response "ROMAN_HI_TICKET_CREATED"

# Manual override: Hindi mode forces Hindi
SESSION_ID="${SESSION_BASE}-force-hi"
export SESSION_ID
QUERY_FORCE_HI=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("SESSION_ID", ""),
  "message": "refund status",
  "lang_hint": "hi"
}))
PY
)
request_json "$API_URL" "$QUERY_FORCE_HI"
if [ "$(cat /tmp/chat_last_code.txt)" != "200" ]; then
  echo "ERROR: forced Hindi query failed"
  cat /tmp/chat_last_body.json
  exit 1
fi
print_response "FORCE_HI"
python3 - <<'PY'
import json
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
resp = body.get("message", body)
if resp.get("language") != "hi":
    raise SystemExit("ERROR: Hindi mode should force Hindi responses")
PY

# Manual override: English mode forces English
SESSION_ID="${SESSION_BASE}-force-en"
export SESSION_ID
QUERY_FORCE_EN=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("SESSION_ID", ""),
  "message": "रिफंड स्टेटस",
  "lang_hint": "en"
}))
PY
)
request_json "$API_URL" "$QUERY_FORCE_EN"
if [ "$(cat /tmp/chat_last_code.txt)" != "200" ]; then
  echo "ERROR: forced English query failed"
  cat /tmp/chat_last_body.json
  exit 1
fi
print_response "FORCE_EN"
python3 - <<'PY'
import json
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
resp = body.get("message", body)
if resp.get("language") != "en":
    raise SystemExit("ERROR: English mode should force English responses")
PY

# Quick reply should trigger KB retrieval and avoid loops
SESSION_ID="${SESSION_BASE}-kb"
export SESSION_ID
QUERY_VAGUE=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("SESSION_ID", ""),
  "message": "payments",
  "lang_hint": ""
}))
PY
)
request_json "$API_URL" "$QUERY_VAGUE"
if [ "$(cat /tmp/chat_last_code.txt)" != "200" ]; then
  echo "ERROR: vague payment query failed"
  cat /tmp/chat_last_body.json
  exit 1
fi
print_response "VAGUE_PAYMENTS"
python3 - <<'PY'
import json
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
resp = body.get("message", body)
if len(resp.get("quick_replies") or []) < 1:
    raise SystemExit("ERROR: expected quick replies for vague payment query")
PY

QUERY_REFINED=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("SESSION_ID", ""),
  "message": "Amount deducted but no confirmation",
  "lang_hint": "en"
}))
PY
)
request_json "$API_URL" "$QUERY_REFINED"
if [ "$(cat /tmp/chat_last_code.txt)" != "200" ]; then
  echo "ERROR: refined query failed"
  cat /tmp/chat_last_body.json
  exit 1
fi
print_response "QUICK_REPLY_SELECTED"
python3 - <<'PY'
import json
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
resp = body.get("message", body)
answer = (resp.get("answer") or "").lower()
banned = ["live chat", "email", "whatsapp", "call us", "helpline"]
if resp.get("ticket_id"):
    raise SystemExit("ERROR: should not create ticket for quick reply selection")
if (resp.get("sources") is None) or len(resp.get("sources") or []) < 1:
    raise SystemExit("ERROR: expected KB sources for quick reply selection")
if any(term in answer for term in banned):
    raise SystemExit("ERROR: answer contains external channel suggestion")
PY

QUERY_FOLLOWUP=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("SESSION_ID", ""),
  "message": "timeline?",
  "lang_hint": "en"
}))
PY
)
request_json "$API_URL" "$QUERY_FOLLOWUP"
if [ "$(cat /tmp/chat_last_code.txt)" != "200" ]; then
  echo "ERROR: follow-up query failed"
  cat /tmp/chat_last_body.json
  exit 1
fi
print_response "FOLLOWUP_TIMELINE"
python3 - <<'PY'
import json
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
resp = body.get("message", body)
if (resp.get("sources") is None) or len(resp.get("sources") or []) < 1:
    raise SystemExit("ERROR: expected KB sources for follow-up")
if len(resp.get("quick_replies") or []) > 0:
    raise SystemExit("ERROR: should not loop quick replies after subtype selection")
PY

# Edge case: off-topic / ambiguous query
SESSION_ID="${SESSION_BASE}-edge"
export SESSION_ID
QUERY_EDGE=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("SESSION_ID", ""),
  "message": "how to reset my gmail password",
  "lang_hint": ""
}))
PY
)
request_json "$API_URL" "$QUERY_EDGE"
if [ "$(cat /tmp/chat_last_code.txt)" != "200" ]; then
  echo "ERROR: edge-case query failed"
  cat /tmp/chat_last_body.json
  exit 1
fi
print_response "EDGE_OFF_TOPIC"
python3 - <<'PY'
import json
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
resp = body.get("message", body)
if resp.get("resolution_state") == "ANSWERED":
    raise SystemExit("ERROR: off-topic should not be ANSWERED")
PY

# Auto escalation after repeated clarification failure
SESSION_ID="${SESSION_BASE}-repeat"
export SESSION_ID
QUERY_R1=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("SESSION_ID", ""),
  "message": "refund",
  "lang_hint": ""
}))
PY
)
request_json "$API_URL" "$QUERY_R1"

QUERY_R2=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("SESSION_ID", ""),
  "message": "payment issue",
  "lang_hint": ""
}))
PY
)
request_json "$API_URL" "$QUERY_R2"

QUERY_R3=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("SESSION_ID", ""),
  "message": "refund help",
  "lang_hint": ""
}))
PY
)
request_json "$API_URL" "$QUERY_R3"
if [ "$(cat /tmp/chat_last_code.txt)" != "200" ]; then
  echo "ERROR: repeated clarification query failed"
  cat /tmp/chat_last_body.json
  exit 1
fi
print_response "AUTO_ESCALATE_AFTER_FAILURE"
python3 - <<'PY'
import json, os
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
resp = body.get("message", body)
if resp.get("ticket_id"):
    raise SystemExit("ERROR: ticket should not be created before contact")
if not resp.get("contact_required"):
    raise SystemExit("ERROR: expected contact_required after repeated failures")
PY

# Create ticket with contact info via chat
CONTACT_MESSAGE=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("SESSION_ID", ""),
  "message": "my email is test@example.com and phone 9999999999",
  "lang_hint": ""
}))
PY
)
request_json "$API_URL" "$CONTACT_MESSAGE"
if [ "$(cat /tmp/chat_last_code.txt)" != "200" ]; then
  echo "ERROR: contact submission failed after escalation"
  cat /tmp/chat_last_body.json
  exit 1
fi
TICKET_ID=$(python3 - <<'PY'
import json
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
resp = body.get("message", body)
print(resp.get("ticket_id") or "")
PY
)
if [ -z "$TICKET_ID" ]; then
  echo "ERROR: expected ticket id after contact submission"
  exit 1
fi
python3 - <<'PY'
import json, os
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
resp = body.get("message", body)
if os.getenv("CHAT_REQUIRE_HD_TICKET", "").lower() in ("1", "true", "yes") and resp.get("ticket_type") != "HD Ticket":
    raise SystemExit(f"ERROR: expected HD Ticket, got {resp.get('ticket_type')}")
PY
STATUS_RESPONSE=$(curl -sS -w "\n%{http_code}" -G --data-urlencode "ticket_id=${TICKET_ID}" --data-urlencode "include_description=1" "$API_STATUS_URL")
STATUS_BODY=$(echo "$STATUS_RESPONSE" | sed '$d')
STATUS_CODE=$(echo "$STATUS_RESPONSE" | tail -n 1)
if [ "$STATUS_CODE" != "200" ]; then
  echo "ERROR: get_ticket_status failed"
  echo "$STATUS_BODY"
  exit 1
fi
echo "$STATUS_BODY" > /tmp/chat_last_body.json
python3 - <<'PY'
import json
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
resp = body.get("message", body)
desc = resp.get("description") or ""
required = [
    "Customer Details",
    "Issue Summary",
    "Conversation Transcript",
    "Knowledge Base Sources Used",
    "System Metadata",
]
for item in required:
    if item not in desc:
        raise SystemExit(f"ERROR: ticket description missing {item}")
if "Customer:" not in desc or "Assistant:" not in desc:
    raise SystemExit("ERROR: ticket transcript missing speaker prefixes")
print(json.dumps({"label": "TICKET_FORMAT", "ticket_id": resp.get("ticket_id")}, indent=2))
PY

# New chat test: new session id
QUERY_NEW_CHAT=$(python3 - <<'PY'
import json
print(json.dumps({
  "message": "refund status?",
  "lang_hint": ""
}))
PY
)
request_json "$API_URL" "$QUERY_NEW_CHAT"

# get_messages endpoint sanity check (real-time fallback)
SESSION_ID="${SESSION_BASE}-realtime"
export SESSION_ID
QUERY_RT=$(python3 - <<'PY'
import json, os
print(json.dumps({
  "session_id": os.environ.get("SESSION_ID", ""),
  "message": "payment deducted but no confirmation",
  "lang_hint": "en"
}))
PY
)
request_json "$API_URL" "$QUERY_RT"
if [ "$(cat /tmp/chat_last_code.txt)" != "200" ]; then
  echo "ERROR: real-time seed query failed"
  cat /tmp/chat_last_body.json
  exit 1
fi
RT_RESPONSE=$(curl -sS -w "\n%{http_code}" -G --data-urlencode "session_id=${SESSION_ID}" --data-urlencode "limit=20" "$API_MESSAGES_URL")
RT_BODY=$(echo "$RT_RESPONSE" | sed '$d')
RT_CODE=$(echo "$RT_RESPONSE" | tail -n 1)
if [ "$RT_CODE" != "200" ]; then
  echo "ERROR: get_messages failed"
  echo "$RT_BODY"
  exit 1
fi
echo "$RT_BODY" > /tmp/chat_last_body.json
python3 - <<'PY'
import json
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
resp = body.get("message", body)
msgs = resp.get("messages") or []
if len(msgs) < 2:
    raise SystemExit("ERROR: expected at least 2 messages from get_messages")
print(json.dumps({"label": "GET_MESSAGES", "count": len(msgs)}, indent=2))
PY
if [ "$(cat /tmp/chat_last_code.txt)" != "200" ]; then
  echo "ERROR: new chat query failed"
  cat /tmp/chat_last_body.json
  exit 1
fi
print_response "NEW_CHAT"
python3 - <<'PY'
import json
with open("/tmp/chat_last_body.json", "r", encoding="utf-8") as f:
    body = json.load(f)
resp = body.get("message", body)
if not resp.get("session_id"):
    raise SystemExit("ERROR: expected session_id for new chat")
PY

echo "Chat tests passed."
