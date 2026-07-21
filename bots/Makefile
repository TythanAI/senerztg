# Convenience targets. Run `make help` for the list.
.DEFAULT_GOAL := help
.PHONY: help install regen env selfcheck catalog archive up down restart logs ps

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	 awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

install: ## Install Python dependencies
	pip install -r requirements.txt

regen: ## Regenerate all configs + docker-compose.yml from the templates
	python tools/gen_tg_configs.py
	python tools/gen_domain_configs.py
	python tools/gen_niche_configs.py
	python tools/gen_compose.py

catalog: ## Regenerate the buyer-facing CATALOG.md from all configs
	python tools/export_catalog.py

archive: ## Build a .zip of the whole project into dist/ (for backup/flash drive)
	python tools/make_archive.py

env: ## Scaffold env/<slug>.env for every bot (fill in tokens after)
	bash tools/init_env.sh

selfcheck: ## Offline health check (no token/network needed)
	python tools/selfcheck.py

up: ## Build and start every bot in the background
	docker compose up -d --build

down: ## Stop and remove all bot containers
	docker compose down

restart: ## Restart all bots
	docker compose restart

logs: ## Follow logs from all bots
	docker compose logs -f --tail=100

ps: ## Show running bots
	docker compose ps
