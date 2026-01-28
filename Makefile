.PHONY: up down logs lint format smoke init-kb fetch-kb translate-hi verify verify-full ensure-env rag-test chat-test print-creds

ENV_FILE := infra/.env
ENV_EXAMPLE := infra/env.example
COMPOSE := docker compose --env-file $(ENV_FILE) -f infra/docker-compose.yml

ensure-env:
	@if [ ! -f $(ENV_FILE) ]; then \
		cp $(ENV_EXAMPLE) $(ENV_FILE); \
		echo "Created $(ENV_FILE) from $(ENV_EXAMPLE)."; \
	fi

up: ensure-env
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=200

lint:
	@echo "Running lint checks (TODO: add linters)"

format:
	@echo "Running formatters (TODO: add formatters)"

smoke:
	@bash scripts/smoke_test.sh

init-kb: fetch-kb
	@python3 scripts/init_kb.py

fetch-kb:
	@python3 scripts/fetch_bms_kb.py --seeds data/kb/sources/bookmyshow_seeds.json --max-pages $${KB_MAX_PAGES:-250} --max-articles $${KB_MAX_ARTICLES:-120} --max-depth $${KB_MAX_DEPTH:-3}

translate-hi:
	@python3 scripts/translate_kb_hi.py

verify:
	$(MAKE) up
	$(MAKE) smoke

verify-full:
	$(MAKE) up
	$(MAKE) rag-test
	CHAT_REQUIRE_HD_TICKET=1 CHAT_BASE_URL=http://localhost:8000 CHAT_WAIT_ATTEMPTS=60 $(MAKE) chat-test
	HELPDESK_URL=http://localhost:8000/ CHAT_URL=http://localhost:8000/support-chat SMOKE_RETRIES=60 $(MAKE) smoke

rag-test: ensure-env
	@bash scripts/rag_integration_test.sh

chat-test: ensure-env
	@bash scripts/chat_test.sh

print-creds: ensure-env
	@set -a; . $(ENV_FILE); set +a; \
	echo "Helpdesk URL: $${HELPDESK_URL:-http://localhost:8000}"; \
	echo "User: Administrator"; \
	echo "Password: $${HELP_DESK_ADMIN_PASSWORD:-admin}"
