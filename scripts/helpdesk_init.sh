#!/usr/bin/env bash
set -euo pipefail

SITE_DIR="/home/frappe/frappe-bench/sites/localhost"
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_ROOT_USERNAME="${DB_ROOT_USERNAME:-postgres}"
DB_NAME="${DB_NAME:-helpdesk}"

if [ -d "$SITE_DIR" ]; then
  echo "Helpdesk site already exists at ${SITE_DIR}."
  exit 0
fi

echo "Creating Helpdesk site 'localhost'..."
bench new-site localhost \
  --admin-password "${HELP_DESK_ADMIN_PASSWORD:-admin}" \
  --db-type postgres \
  --db-root-username "${DB_ROOT_USERNAME}" \
  --db-root-password "${DB_PASSWORD:-123}" \
  --db-host "${DB_HOST}" \
  --db-port "${DB_PORT}" \
  --db-name "${DB_NAME}"

echo "Helpdesk site created."
