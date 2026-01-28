.PHONY: up down logs lint format smoke init-kb fetch-kb translate-hi helpdesk-init helpdesk-install-app verify verify-full ensure-env rag-test chat-test up-helpdesk-official print-creds

ENV_FILE := infra/.env
ENV_EXAMPLE := infra/env.example
COMPOSE_LEGACY := docker compose --env-file $(ENV_FILE) -f infra/docker-compose.yml --profile helpdesk-legacy
COMPOSE_OFFICIAL := docker compose --env-file $(ENV_FILE) -f infra/docker-compose.yml -f infra/docker-compose.helpdesk.yml --profile helpdesk-official

ensure-env:
	@if [ ! -f $(ENV_FILE) ]; then \
		cp $(ENV_EXAMPLE) $(ENV_FILE); \
		echo "Created $(ENV_FILE) from $(ENV_EXAMPLE)."; \
	fi

up: ensure-env
	$(COMPOSE_LEGACY) up -d --build

up-helpdesk-official: ensure-env
	$(COMPOSE_OFFICIAL) up -d --build

down:
	docker compose --env-file $(ENV_FILE) -f infra/docker-compose.yml -f infra/docker-compose.helpdesk.yml down -v

logs:
	$(COMPOSE_LEGACY) logs -f --tail=200

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

helpdesk-init: ensure-env
	@if [ "$$HELPDESK_PROFILE" = "official" ]; then \
		echo "Skipping legacy helpdesk-init (official profile)."; \
	else \
		$(COMPOSE_LEGACY) run --rm helpdesk-backend bash -lc "bash /workspace/scripts/helpdesk_init.sh"; \
	fi

helpdesk-install-app: ensure-env
	$(COMPOSE_LEGACY) run --rm helpdesk-backend bash -lc "bash /workspace/scripts/helpdesk_install_ai_powered_css.sh"

verify:
	$(MAKE) up
	$(MAKE) smoke

verify-full:
	$(MAKE) up-helpdesk-official
	HELPDESK_PROFILE=official $(MAKE) helpdesk-init
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
