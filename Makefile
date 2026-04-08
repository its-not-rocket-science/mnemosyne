# ─────────────────────────────────────────────────────────────────────────────
# Mnemosyne — developer Makefile
#
# Local-Python targets use the Poetry environment directly.
# Docker targets require Docker with Compose v2  (docker compose …).
#
# First-time setup:
#   make install          install Python deps
#   cp .env.example .env  configure environment
#   make up               start the full Docker stack
# ─────────────────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help
COMPOSE       := docker compose

.PHONY: help \
        install dev test lint lock \
        build up down restart logs shell \
        psql redis-cli ready

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@printf '\nLocal Python\n'
	@grep -E '^(install|dev|test|lint|lock):.*?## ' $(MAKEFILE_LIST) \
	 | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n",$$1,$$2}'
	@printf '\nDocker\n'
	@grep -E '^(build|up|down|restart|logs|shell|psql|redis-cli|ready):.*?## ' \
	 $(MAKEFILE_LIST) \
	 | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n",$$1,$$2}'
	@printf '\n'

# ── Local Python ──────────────────────────────────────────────────────────────

install: ## Install all Python dependencies via Poetry
	poetry install

dev: ## Run API server locally with hot-reload (no Docker needed)
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

test: ## Run the full test suite
	pytest backend/tests -q

lint: ## Lint (ruff) and type-check (mypy)
	ruff check backend
	mypy backend --ignore-missing-imports

lock: ## Regenerate poetry.lock from pyproject.toml (required before docker build)
	poetry lock --no-update

# ── Docker ────────────────────────────────────────────────────────────────────

build: ## Build (or rebuild) the app image — generates poetry.lock if absent
	@test -f poetry.lock || { echo "No poetry.lock found — running 'poetry lock' first"; poetry lock --no-update; }
	$(COMPOSE) build

up: ## Start all services in the background
	$(COMPOSE) up -d

down: ## Stop and remove containers (data volumes are preserved)
	$(COMPOSE) down

restart: ## Restart the app container only (picks up bind-mounted code changes)
	$(COMPOSE) restart app

logs: ## Tail logs for all services (Ctrl-C to stop)
	$(COMPOSE) logs -f

shell: ## Open a bash shell inside the running app container
	$(COMPOSE) exec app bash

psql: ## Connect to PostgreSQL via psql
	$(COMPOSE) exec postgres psql \
	  -U $${POSTGRES_USER:-mnemosyne} \
	  $${POSTGRES_DB:-mnemosyne}

redis-cli: ## Connect to the Redis CLI
	$(COMPOSE) exec redis redis-cli

ready: ## Call /ready and print the connectivity report
	@curl -sf http://localhost:8000/ready | python -m json.tool \
	 || echo "Not reachable — is the stack up? (make up)"
