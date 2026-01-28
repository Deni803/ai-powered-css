#!/usr/bin/env bash
set -euo pipefail

SITE_DIR="/home/frappe/frappe-bench/sites/localhost"

if [ -d "$SITE_DIR" ]; then
  echo "Helpdesk site already exists at ${SITE_DIR}."
  exit 0
fi

echo "Creating Helpdesk site 'localhost'..."
bench new-site localhost \
  --admin-password "${HELP_DESK_ADMIN_PASSWORD:-admin}" \
  --db-root-password "${DB_PASSWORD:-123}" \
  --db-host "${DB_HOST:-helpdesk-db}" \
  --db-port "${DB_PORT:-3306}" \
  --no-mariadb-socket

echo "Helpdesk site created."
