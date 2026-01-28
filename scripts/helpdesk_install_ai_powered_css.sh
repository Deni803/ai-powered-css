#!/usr/bin/env bash
set -euo pipefail

APP_NAME="ai_powered_css"
BENCH_PATH="/home/frappe/frappe-bench"
APP_PATH="${BENCH_PATH}/apps/${APP_NAME}"
SOURCE_PATH="/workspace/apps/${APP_NAME}"
SITE_NAME="localhost"
CONFIG_PATH="${BENCH_PATH}/sites/common_site_config.json"

if [ ! -d "$SOURCE_PATH" ]; then
  echo "ERROR: App source not found at $SOURCE_PATH"
  exit 1
fi

if [ ! -e "$APP_PATH" ]; then
  ln -s "$SOURCE_PATH" "$APP_PATH"
  echo "Linked $SOURCE_PATH -> $APP_PATH"
fi

python3 - <<'PY'
import json
from pathlib import Path

path = Path("/home/frappe/frappe-bench/sites/common_site_config.json")
path.parent.mkdir(parents=True, exist_ok=True)
data = {}
if path.exists():
    try:
        data = json.loads(path.read_text() or "{}")
    except Exception:
        data = {}

data.setdefault("db_host", "helpdesk-db")
data.setdefault("db_port", 3306)
data.setdefault("redis_cache", "redis://helpdesk-redis-cache:6379")
data.setdefault("redis_queue", "redis://helpdesk-redis-queue:6379")
data.setdefault("redis_socketio", "redis://helpdesk-redis-queue:6379")
data.setdefault("socketio_port", 9000)

path.write_text(json.dumps(data, indent=2))
PY

if ! bench --site "$SITE_NAME" list-apps | grep -qi "helpdesk"; then
  if [ -f /workspace/scripts/helpdesk_install_helpdesk.sh ]; then
    bash /workspace/scripts/helpdesk_install_helpdesk.sh
  else
    echo "WARNING: helpdesk install script not found; HD Ticket may be unavailable."
  fi
fi

if ! /home/frappe/frappe-bench/env/bin/python -c "import ${APP_NAME}" >/dev/null 2>&1; then
  /home/frappe/frappe-bench/env/bin/pip install -e "$APP_PATH"
fi

if ! bench --site "$SITE_NAME" list-apps | grep -q "${APP_NAME}"; then
  bench --site "$SITE_NAME" install-app "$APP_NAME"
fi

bench --site "$SITE_NAME" migrate

echo "App ${APP_NAME} installed."
