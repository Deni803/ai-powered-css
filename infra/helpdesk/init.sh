#!/bin/bash
set -euo pipefail

BENCH_DIR="/home/frappe/frappe-bench"
SITE_NAME="helpdesk.localhost"
DB_PASSWORD="${DB_PASSWORD:-123}"
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_ROOT_USERNAME="${DB_ROOT_USERNAME:-postgres}"
DB_NAME="${DB_NAME:-helpdesk}"
HELP_DESK_ADMIN_PASSWORD="${HELP_DESK_ADMIN_PASSWORD:-admin}"
APP_NAME="ai_powered_css"
WORKSPACE="/workspace"

if [ "$(id -u)" = "0" ]; then
  RUN_AS="su -s /bin/bash frappe -c"
else
  RUN_AS=""
fi

bench_exec() {
  if [ -n "$RUN_AS" ]; then
    $RUN_AS "export PATH=/home/frappe/.local/bin:/home/frappe/frappe-bench/env/bin:\$PATH; cd ${BENCH_DIR} && $*"
  else
    (cd "${BENCH_DIR}" && $*)
  fi
}

bench_init() {
  if [ -n "$RUN_AS" ]; then
    $RUN_AS "export PATH=/home/frappe/.local/bin:/home/frappe/frappe-bench/env/bin:\$PATH; cd /home/frappe && $*"
  else
    (cd /home/frappe && $*)
  fi
}

if [ ! -d "${BENCH_DIR}" ]; then
  echo "Creating new bench..."
  bench_init "bench init --skip-redis-config-generation --skip-assets --no-backups frappe-bench --version version-15"
else
  echo "Bench already exists, using existing directory"
fi

mkdir -p "${BENCH_DIR}/sites" "${BENCH_DIR}/logs"
if [ "$(id -u)" = "0" ]; then
  chown -R frappe:frappe "${BENCH_DIR}/sites" "${BENCH_DIR}/logs" || true
  chmod -R u+rwX,g+rwX "${BENCH_DIR}/sites" "${BENCH_DIR}/logs" || true
fi
if [ ! -f "${BENCH_DIR}/sites/common_site_config.json" ]; then
  echo "{}" > "${BENCH_DIR}/sites/common_site_config.json"
fi

bench_exec "bench set-config -g db_type postgres"
bench_exec "bench set-config -g db_host ${DB_HOST}"
bench_exec "bench set-config -g db_port ${DB_PORT}"
bench_exec "bench set-redis-cache-host redis://redis:6379"
bench_exec "bench set-redis-queue-host redis://redis:6379"
bench_exec "bench set-redis-socketio-host redis://redis:6379"

# Wait for Postgres to be reachable before creating the site
python - <<PY
import socket
import time
import os

host = os.environ.get("DB_HOST", "postgres")
port = int(os.environ.get("DB_PORT", "5432"))
deadline = time.time() + 60
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"DB reachable at {host}:{port}")
            raise SystemExit(0)
    except Exception:
        time.sleep(2)
print(f"DB not reachable at {host}:{port} after 60s")
raise SystemExit(1)
PY

# Remove redis, watch from Procfile (bench uses external redis)
sed -i '/redis/d' "${BENCH_DIR}/Procfile" || true
sed -i '/watch/d' "${BENCH_DIR}/Procfile" || true

if [ ! -d "${BENCH_DIR}/apps/telephony" ]; then
  bench_exec "bench get-app telephony"
fi

if [ ! -d "${BENCH_DIR}/apps/helpdesk" ]; then
  bench_exec "bench get-app helpdesk --branch main --skip-assets"
fi

# Patch Helpdesk SLA query for Postgres (smallint vs boolean)
python - <<'PY'
from pathlib import Path

bench_dir = Path("/home/frappe/frappe-bench")
path = bench_dir / "apps/helpdesk/helpdesk/helpdesk/doctype/hd_service_level_agreement/utils.py"
if path.exists():
    text = path.read_text()
    updated = text.replace("QBSla.enabled == True", "QBSla.enabled == 1")
    updated = updated.replace("QBSla.default_sla == False", "QBSla.default_sla == 0")
    # Replace get_default() body with a Postgres-safe, permission-agnostic version.
    marker_start = "def get_default()"
    marker_end = "def convert_to_seconds"
    if marker_start in updated and marker_end in updated:
        before, rest = updated.split(marker_start, 1)
        _, after = rest.split(marker_end, 1)
        new_block = (
            "def get_default() -> Document | None:\n"
            "    \"\"\"\n"
            "    Get default Service Level Agreement\n\n"
            "    :return: Default SLA\n"
            "    \"\"\"\n"
            "    try:\n"
            "        return frappe.get_last_doc(\n"
            "            DOCTYPE,\n"
            "            filters={\n"
            "                \"enabled\": 1,\n"
            "                \"default_sla\": 1,\n"
            "            },\n"
            "            ignore_permissions=True,\n"
            "        )\n"
            "    except Exception:\n"
            "        return None\n\n"
        )
        updated = before + new_block + marker_end + after
    if updated != text:
        path.write_text(updated)
        print("Patched Helpdesk SLA defaults for Postgres.")

sla_path = bench_dir / "apps/helpdesk/helpdesk/helpdesk/doctype/hd_service_level_agreement/hd_service_level_agreement.py"
if sla_path.exists():
    text = sla_path.read_text()
    start_expr = "(current_workday_doc.start_time.hour * 3600) + (current_workday_doc.start_time.minute * 60) + current_workday_doc.start_time.second"
    end_expr = "(current_workday_doc.end_time.hour * 3600) + (current_workday_doc.end_time.minute * 60) + current_workday_doc.end_time.second"
    updated = text.replace("current_workday_doc.start_time.total_seconds()", start_expr)
    updated = updated.replace("current_workday_doc.end_time.total_seconds()", end_expr)
    if updated != text:
        sla_path.write_text(updated)
        print("Patched Helpdesk SLA time conversion for Postgres.")

ticket_path = bench_dir / "apps/helpdesk/helpdesk/helpdesk/doctype/hd_ticket/hd_ticket.py"
if ticket_path.exists():
    text = ticket_path.read_text()
    updated = text.replace("self.key = uuid.uuid4()", "self.key = str(uuid.uuid4())")
    if "def apply_sla(self):" in updated and "def set_default_status" in updated:
        before, rest = updated.split("def apply_sla(self):", 1)
        _, after = rest.split("def set_default_status", 1)
        apply_block = (
            "def apply_sla(self):\n"
            "        \"\"\"\n"
            "        Apply SLA if set.\n"
            "        \"\"\"\n"
            "        try:\n"
            "            if not self.sla:\n"
            "                return\n"
            "            sla = frappe.get_last_doc(\"HD Service Level Agreement\", {\"name\": self.sla}, ignore_permissions=True)\n"
            "        except Exception:\n"
            "            return\n"
            "        if sla:\n"
            "            sla.apply(self)\n\n"
            "    def set_default_status"
        )
        updated = before + apply_block + after
    if updated != text:
        ticket_path.write_text(updated)
        print("Patched HD Ticket key to string UUID for Postgres.")

# Patch Helpdesk install: skip FULLTEXT index creation on Postgres.
install_path = bench_dir / "apps/helpdesk/helpdesk/setup/install.py"
if install_path.exists():
    text = install_path.read_text()
    marker = "def add_fts_index():"
    if marker in text and "POSTGRES_SKIP_FTS" not in text:
        injected = (
            "def add_fts_index():\n"
            "    # POSTGRES_SKIP_FTS: FULLTEXT indexes are MySQL-specific.\n"
            "    import frappe\n"
            "    if frappe.db.db_type == \"postgres\":\n"
            "        return\n"
        )
        text = text.replace(marker, injected)
        install_path.write_text(text)
        print("Patched Helpdesk FTS install for Postgres.")
PY

if [ ! -d "${BENCH_DIR}/sites/${SITE_NAME}" ]; then
  bench_exec "bench new-site ${SITE_NAME} \
    --force \
    --db-type postgres \
    --db-host ${DB_HOST} \
    --db-port ${DB_PORT} \
    --db-root-username ${DB_ROOT_USERNAME} \
    --db-root-password ${DB_PASSWORD} \
    --db-name ${DB_NAME} \
    --admin-password ${HELP_DESK_ADMIN_PASSWORD}"
fi

bench_exec "bench --site ${SITE_NAME} set-admin-password ${HELP_DESK_ADMIN_PASSWORD}"

if ! bench_exec "bench --site ${SITE_NAME} list-apps" | grep -qi telephony; then
  bench_exec "bench --site ${SITE_NAME} install-app telephony"
fi

if ! bench_exec "bench --site ${SITE_NAME} list-apps" | grep -qi helpdesk; then
  bench_exec "bench --site ${SITE_NAME} install-app helpdesk"
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
  if ! bench_exec "bench --site ${SITE_NAME} list-apps" | grep -qi "${APP_NAME}"; then
    bench_exec "bench --site ${SITE_NAME} install-app ${APP_NAME}"
  fi
fi

if [ ! -f "${BENCH_DIR}/sites/assets/website.bundle.css" ]; then
  echo "Building assets (website.bundle.css missing)..."
  bench_exec "bench build"
fi

bench_exec "bench --site ${SITE_NAME} migrate"
bench_exec "bench --site ${SITE_NAME} set-config developer_mode 0"
bench_exec "bench --site ${SITE_NAME} set-config mute_emails 1"
bench_exec "bench --site ${SITE_NAME} set-config server_script_enabled 1"
bench_exec "bench --site ${SITE_NAME} clear-cache"
bench_exec "bench use ${SITE_NAME}"

mkdir -p "/home/frappe/logs" "/home/frappe/frappe-bench/${SITE_NAME}/logs"

bench_exec "/home/frappe/frappe-bench/env/bin/python - <<'PY'\nimport os\nimport frappe\n\nos.chdir(\"/home/frappe/frappe-bench\")\nfrappe.init(site=\"helpdesk.localhost\", sites_path=\"/home/frappe/frappe-bench/sites\")\nfrappe.connect()\nfrappe.flags.ignore_permissions = True\n\n\ndef ensure_doc(doctype, name=None, **fields):\n    if name and frappe.db.exists(doctype, name):\n        return name\n    if name and not fields.get(\"name\"):\n        fields[\"name\"] = name\n    if not name:\n        exists = frappe.db.exists(doctype, fields)\n        if exists:\n            return exists\n    doc = frappe.get_doc({\"doctype\": doctype, **fields})\n    doc.insert(ignore_permissions=True)\n    return doc.name\n\n# Ticket Statuses\nif frappe.db.count(\"HD Ticket Status\") == 0:\n    ensure_doc(\"HD Ticket Status\", \"Open\", label_agent=\"Open\", category=\"Open\")\n    ensure_doc(\"HD Ticket Status\", \"Replied\", label_agent=\"Replied\", category=\"Open\")\n    ensure_doc(\"HD Ticket Status\", \"Resolved\", label_agent=\"Resolved\", category=\"Resolved\")\n    ensure_doc(\"HD Ticket Status\", \"Closed\", label_agent=\"Closed\", category=\"Resolved\")\n\n# Ticket Priorities\nif frappe.db.count(\"HD Ticket Priority\") == 0:\n    ensure_doc(\"HD Ticket Priority\", \"Low\", integer_value=1)\n    ensure_doc(\"HD Ticket Priority\", \"Medium\", integer_value=2)\n    ensure_doc(\"HD Ticket Priority\", \"High\", integer_value=3)\n\n# Ticket Types\nif frappe.db.count(\"HD Ticket Type\") == 0:\n    ensure_doc(\"HD Ticket Type\", \"Unspecified\")\n\n# Default Ticket Template
if frappe.db.count("HD Ticket Template") == 0:
    ensure_doc("HD Ticket Template", "Default", template_name="Default")

# HD Settings defaults
settings = frappe.get_single("HD Settings")
settings.default_ticket_status = settings.default_ticket_status or "Open"
settings.ticket_reopen_status = settings.ticket_reopen_status or "Open"
settings.default_priority = settings.default_priority or "Medium"
settings.save(ignore_permissions=True)

frappe.db.commit()\nfrappe.destroy()\nPY"

bench_exec "bench start"
