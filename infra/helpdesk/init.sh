#!/bin/bash
set -euo pipefail

BENCH_DIR="/home/frappe/frappe-bench"
SITE_NAME="helpdesk.localhost"
DB_PASSWORD="${DB_PASSWORD:-123}"
HELP_DESK_ADMIN_PASSWORD="${HELP_DESK_ADMIN_PASSWORD:-admin}"
APP_NAME="ai_powered_css"
WORKSPACE="/workspace"

if [ ! -d "${BENCH_DIR}" ]; then
  echo "Creating new bench..."
  bench init --skip-redis-config-generation frappe-bench --version version-15
else
  echo "Bench already exists, using existing directory"
fi

mkdir -p "${BENCH_DIR}/sites"
if [ ! -f "${BENCH_DIR}/sites/common_site_config.json" ]; then
  echo "{}" > "${BENCH_DIR}/sites/common_site_config.json"
fi

cd "${BENCH_DIR}"

bench set-mariadb-host mariadb
bench set-redis-cache-host redis://redis:6379
bench set-redis-queue-host redis://redis:6379
bench set-redis-socketio-host redis://redis:6379

# Remove redis, watch from Procfile (bench uses external redis)
sed -i '/redis/d' ./Procfile || true
sed -i '/watch/d' ./Procfile || true

if [ ! -d "${BENCH_DIR}/apps/telephony" ]; then
  bench get-app telephony
fi

if [ ! -d "${BENCH_DIR}/apps/helpdesk" ]; then
  bench get-app helpdesk --branch main
fi

if [ ! -d "${BENCH_DIR}/sites/${SITE_NAME}" ]; then
  bench new-site "${SITE_NAME}" \
    --force \
    --mariadb-root-password "${DB_PASSWORD}" \
    --admin-password "${HELP_DESK_ADMIN_PASSWORD}" \
    --no-mariadb-socket
fi

bench --site "${SITE_NAME}" set-admin-password "${HELP_DESK_ADMIN_PASSWORD}"

if ! bench --site "${SITE_NAME}" list-apps | grep -qi telephony; then
  bench --site "${SITE_NAME}" install-app telephony
fi

if ! bench --site "${SITE_NAME}" list-apps | grep -qi helpdesk; then
  bench --site "${SITE_NAME}" install-app helpdesk
fi

if [ -d "${WORKSPACE}/apps/${APP_NAME}" ]; then
  if [ ! -e "${BENCH_DIR}/apps/${APP_NAME}" ]; then
    ln -s "${WORKSPACE}/apps/${APP_NAME}" "${BENCH_DIR}/apps/${APP_NAME}"
  fi
  if [ ! -f "${BENCH_DIR}/sites/apps.txt" ]; then
    touch "${BENCH_DIR}/sites/apps.txt"
  fi
  if ! grep -q "^${APP_NAME}$" "${BENCH_DIR}/sites/apps.txt"; then
    if [ -s "${BENCH_DIR}/sites/apps.txt" ]; then
      last_char=$(tail -c 1 "${BENCH_DIR}/sites/apps.txt" || true)
      if [ "$last_char" != "" ]; then
        echo "" >> "${BENCH_DIR}/sites/apps.txt"
      fi
    fi
    echo "${APP_NAME}" >> "${BENCH_DIR}/sites/apps.txt"
  fi
  if [ -x "${BENCH_DIR}/env/bin/pip" ]; then
    "${BENCH_DIR}/env/bin/pip" install -e "${BENCH_DIR}/apps/${APP_NAME}"
  fi
  if ! bench --site "${SITE_NAME}" list-apps | grep -qi "${APP_NAME}"; then
    bench --site "${SITE_NAME}" install-app "${APP_NAME}"
  fi
fi

bench --site "${SITE_NAME}" migrate
bench --site "${SITE_NAME}" set-config developer_mode 1
bench --site "${SITE_NAME}" set-config mute_emails 1
bench --site "${SITE_NAME}" set-config server_script_enabled 1
bench --site "${SITE_NAME}" clear-cache
bench use "${SITE_NAME}"

bench start
