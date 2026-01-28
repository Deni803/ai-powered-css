#!/usr/bin/env bash
set -euo pipefail

if bench --site localhost list-apps 2>/dev/null | grep -qi "helpdesk"; then
  echo "Helpdesk app already installed."
  exit 0
fi

LOG_FILE="/tmp/helpdesk_install.log"
: > "$LOG_FILE"

set +e
bench get-app helpdesk --branch main >> "$LOG_FILE" 2>&1
GET_RC=$?
bench --site localhost install-app helpdesk >> "$LOG_FILE" 2>&1
INSTALL_RC=$?
bench build --app helpdesk >> "$LOG_FILE" 2>&1
BUILD_RC=$?
set -e

if [ $GET_RC -ne 0 ] || [ $INSTALL_RC -ne 0 ] || [ $BUILD_RC -ne 0 ]; then
  echo "Helpdesk install failed; logging to docs/BUGS.md"
  if [ -d /workspace/docs ]; then
    if ! grep -q "Helpdesk install failed" /workspace/docs/BUGS.md; then
      {
        echo
        echo "- Helpdesk install failed during Module 3."
        echo "  Output:"
        echo "  ```"
        sed 's/^/  /' "$LOG_FILE"
        echo "  ```"
      } >> /workspace/docs/BUGS.md
    fi
  fi
  cat "$LOG_FILE"
  exit 0
fi

echo "Helpdesk app installed successfully."
