#!/usr/bin/env bash
set -euo pipefail

SMOKE_RETRIES="${SMOKE_RETRIES:-20}"
SMOKE_SLEEP="${SMOKE_SLEEP:-2}"

require_bin() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: '$1' is required for smoke tests."
    exit 1
  fi
}

retry_http() {
  local name="$1"
  local url="$2"
  local allowed_codes="$3"
  local attempt=1
  local code=""

  echo "Checking ${name} at ${url} (expecting: ${allowed_codes})"
  while [ "$attempt" -le "$SMOKE_RETRIES" ]; do
    code="$(curl -sS -o /dev/null -w "%{http_code}" -L "$url" || true)"
    if echo " ${allowed_codes} " | grep -q " ${code} "; then
      echo "OK: ${name} responded with ${code}"
      return 0
    fi
    echo "Waiting for ${name} (attempt ${attempt}/${SMOKE_RETRIES}, last HTTP ${code})..."
    attempt=$((attempt + 1))
    sleep "$SMOKE_SLEEP"
  done

  if [ "$name" = "Helpdesk frontend" ] && [ "$code" = "404" ]; then
    echo "FAIL: Helpdesk returned 404. Run 'make helpdesk-init' to create the site."
    return 1
  fi

  echo "FAIL: ${name} did not respond with expected code(s) (${allowed_codes}). Last HTTP ${code}."
  return 1
}

require_bin curl

QDRANT_HEALTH_URL="${QDRANT_HEALTH_URL:-http://localhost:6333/healthz}"
QDRANT_ROOT_URL="${QDRANT_ROOT_URL:-http://localhost:6333/}"
RAG_HEALTH_URL="${RAG_HEALTH_URL:-http://localhost:8001/health}"
HELPDESK_URL="${HELPDESK_URL:-http://localhost:8080/}"
CHAT_URL="${CHAT_URL:-http://localhost:8080/support-chat}"

if ! retry_http "Qdrant (healthz)" "$QDRANT_HEALTH_URL" "200"; then
  echo "Qdrant health endpoint failed, trying root..."
  retry_http "Qdrant (root)" "$QDRANT_ROOT_URL" "200"
fi

retry_http "RAG service" "$RAG_HEALTH_URL" "200"
retry_http "Helpdesk frontend" "$HELPDESK_URL" "200 302"
retry_http "Support chat page" "$CHAT_URL" "200 302"

echo "Smoke tests passed."
