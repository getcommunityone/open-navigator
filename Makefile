.PHONY: help install install-web_app install-docs build-web_app build-docs clean test run dev dev-web_app dev-docs start-all stop-all dev-full docker-up docker-down deploy-databricks grants-refresh backup restore

help:
	@echo "🦷 Open Navigator - Makefile Commands"
	@echo "===================================================="
	@echo ""
	@echo "🚀 Quick Start:"
	@echo "  make start-all         - Start ALL services (API + Dashboard + Docs) with tmux"
	@echo "  make stop-all          - Stop all running services"
	@echo ""
	@echo "🐍 Python Backend:"
	@echo "  make install           - Install Python dependencies in venv"
	@echo "  make dev               - Start backend with auto-reload"
	@echo "  make run               - Start backend (production)"
	@echo ""
	@echo "⚛️  React Dashboard:"
	@echo "  make install-web_app  - Install dashboard npm dependencies"
	@echo "  make build-web_app    - Build React dashboard for production"
	@echo "  make dev-web_app      - Start dashboard dev server"
	@echo ""
	@echo "📚 Documentation Site:"
	@echo "  make install-docs      - Install Docusaurus dependencies"
	@echo "  make build-docs        - Build documentation for production"
	@echo "  make dev-docs          - Start documentation dev server"
	@echo ""
	@echo "☁️  Deployment:"
	@echo "  make deploy-databricks - Deploy to Databricks Apps"
	@echo ""
	@echo "🐳 Docker:"
	@echo "  make docker-up         - Start Docker containers"
	@echo "  make docker-down       - Stop Docker containers"
	@echo ""
	@echo "🧪 Testing:"
	@echo "  make test              - Run test suite"
	@echo "  make clean             - Remove build artifacts"
	@echo ""
	@echo "💰 Data Refresh:"
	@echo "  make grants-refresh    - Refresh Grants.gov opportunities (incremental upsert)"
	@echo ""
	@echo "🏷️  Releases & Backups (semver, see web_docs Quick Start):"
	@echo "  make backup VERSION=v1.5.0   - Dump open_navigator + openstates, push to Drive"
	@echo "  make restore VERSION=v1.5.0  - Pull a release's backup from Drive and restore (dev only)"
	@echo ""

install:
	@echo "📦 Creating virtual environment and installing dependencies..."
	@chmod +x install.sh
	@./install.sh

install-web_app:
	@echo "📦 Installing dashboard dependencies..."
	@cd web_app && npm install
	@echo "✅ Dashboard dependencies installed!"

install-docs:
	@echo "📦 Installing documentation dependencies..."
	@cd web_docs && npm install
	@echo "✅ Documentation dependencies installed!"

build-web_app:
	@echo "🔨 Building React dashboard..."
	@cd web_app && npm run build
	@echo "✅ Dashboard built to api/static/"

build-docs:
	@echo "🔨 Building documentation site..."
	@cd web_docs && npm run build
	@echo "✅ Documentation built to web_docs/build/"

clean:
	@echo "🧹 Cleaning up..."
	@rm -rf .venv venv
	@rm -rf web_app/node_modules web_app/dist
	@rm -rf web_docs/node_modules web_docs/build web_docs/.docusaurus
	@rm -rf api/static
	@rm -rf __pycache__
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@rm -rf .pytest_cache
	@rm -rf .coverage
	@rm -rf htmlcov
	@rm -rf dist
	@rm -rf build
	@rm -rf *.egg-info
	@rm -rf logs/*.pid logs/*.log
	@echo "✅ Cleanup complete"

test:
	@echo "🧪 Running tests..."
	@. venv/bin/activate && pytest tests/ -v

run: build-web_app
	@echo "🚀 Starting application (production mode)..."
	@. venv/bin/activate && uvicorn api.app:app --host 0.0.0.0 --port 8000

dev:
	@echo "🔧 Starting backend with auto-reload..."
	@echo "📡 Backend running at http://localhost:8000"
	@. venv/bin/activate && uvicorn api.app:app --reload

dev-web_app:
	@echo "⚛️  Starting dashboard dev server..."
	@echo "📡 Dashboard running at http://localhost:5173"
	@cd web_app && npm run dev

dev-docs:
	@echo "📚 Starting documentation dev server..."
	@echo "📡 Documentation running at http://localhost:3000"
	@cd web_docs && npm start

start-all:
	@echo "🚀 Starting all services with tmux..."
	@chmod +x start-all.sh
	@./start-all.sh

stop-all:
	@echo "🛑 Stopping all services..."
	@chmod +x stop-all.sh
	@./stop-all.sh

dev-full:
	@echo "🚀 Use 'make start-all' for better experience with tmux!"
	@echo ""
	@echo "Starting backend and web_app (manual)..."
	@echo "📡 Backend:   http://localhost:8000"
	@echo "📡 Dashboard: http://localhost:5173"
	@echo "📡 Docs:      http://localhost:3000 (run 'make dev-docs' in another terminal)"
	@echo ""
	@. venv/bin/activate && uvicorn api.app:app --reload & \
	cd web_app && npm run dev

deploy-databricks:
	@echo "☁️  Deploying to Databricks Apps..."
	@chmod +x scripts/deploy-databricks-app.sh
	@./scripts/deploy-databricks-app.sh

docker-up:
	@echo "Starting Docker containers..."
	@docker-compose up -d
	@echo "✓ Containers started"
	@echo "  API: http://localhost:8000"
	@echo "  Docs: http://localhost:8000/docs"

docker-down:
	@echo "Stopping Docker containers..."
	@docker-compose down
	@echo "✓ Containers stopped"

example:
	@echo "Running example workflow..."
	@. venv/bin/activate && python examples/example_workflow.py

heatmap:
	@echo "Generating example heatmap..."
	@. venv/bin/activate && python main.py generate-heatmap --output example_heatmap.html
	@echo "✓ Heatmap saved to example_heatmap.html"

init:
	@echo "Initializing system..."
	@. venv/bin/activate && python main.py init

status:
	@echo "Checking system status..."
	@. venv/bin/activate && python main.py status

format:
	@echo "Formatting code..."
	@. venv/bin/activate && black .
	@. venv/bin/activate && ruff check . --fix
	@echo "✓ Code formatted"

lint:
	@echo "Linting code..."
	@. venv/bin/activate && ruff check .
	@. venv/bin/activate && mypy agents/ pipeline/ visualization/ api/

# Incremental refresh of Grants.gov federal opportunities -> public.grant_opportunity.
# Bronze upserts by opportunity_id (no --truncate), then the dbt mart merges
# incrementally (delete+insert on the PK). Safe to run on a schedule/cron.
# DSN defaults to local dev; export DATABASE_URL/NEON_DATABASE_URL_DEV to override.
grants-refresh:
	@echo "💰 Refreshing Grants.gov opportunities (incremental)..."
	@: $${DATABASE_URL:=postgresql://postgres:password@localhost:5433/open_navigator}; \
		export DATABASE_URL NEON_DATABASE_URL_DEV=$${NEON_DATABASE_URL_DEV:-$$DATABASE_URL}; \
		. .venv/bin/activate && python -m ingestion.grants_gov.bronze
	@cd dbt_project && .venv_dbt/bin/dbt run --select stg_grants_gov__opportunity grant_opportunity
	@echo "✅ grant_opportunity refreshed"

# --- Releases & Data Versioning -------------------------------------------------
# Tie a semantic-version release tag to a Postgres backup of the warehouse so the
# code at a tag can be reproduced against the exact data it shipped with.
# See web_docs/docs/quickstart.md (Releases & Data Versioning) for the full flow.
#
#   make backup VERSION=v1.5.0    # dump both DBs, version-stamped, push to Drive
#   make restore VERSION=v1.5.0   # pull that version's dumps from Drive, restore (DEV ONLY)
#
# Override any of these via env: PG_HOST/PG_PORT/PG_USER/PGPASSWORD, RCLONE_REMOTE,
# BACKUP_DIR. Defaults match the local dev warehouse (localhost:5433).
PG_HOST       ?= localhost
PG_PORT       ?= 5433
PG_USER       ?= postgres
PGPASSWORD    ?= password
RCLONE_REMOTE ?= gdrive:open-navigator-backups
BACKUP_DIR    ?= backups

backup:
	@test -n "$(VERSION)" || { echo "❌ VERSION required, e.g. make backup VERSION=v1.5.0"; exit 1; }
	@mkdir -p $(BACKUP_DIR)
	@stamp=$$(date +%Y%m%d); \
		echo "📦 Dumping open_navigator + openstates at $(VERSION) ($$stamp)..."; \
		PGPASSWORD=$(PGPASSWORD) pg_dump -h $(PG_HOST) -p $(PG_PORT) -U $(PG_USER) -Fc open_navigator \
			-f $(BACKUP_DIR)/open_navigator_$(VERSION)_$$stamp.dump; \
		PGPASSWORD=$(PGPASSWORD) pg_dump -h $(PG_HOST) -p $(PG_PORT) -U $(PG_USER) -Fc openstates \
			-f $(BACKUP_DIR)/openstates_$(VERSION)_$$stamp.dump; \
		echo "✅ Dumps written to $(BACKUP_DIR)/"; \
		if command -v rclone >/dev/null 2>&1; then \
			echo "☁️  Uploading to $(RCLONE_REMOTE)/$(VERSION)/..."; \
			rclone copy $(BACKUP_DIR)/open_navigator_$(VERSION)_$$stamp.dump $(RCLONE_REMOTE)/$(VERSION)/ && \
			rclone copy $(BACKUP_DIR)/openstates_$(VERSION)_$$stamp.dump $(RCLONE_REMOTE)/$(VERSION)/ && \
			echo "✅ Uploaded to $(RCLONE_REMOTE)/$(VERSION)/"; \
		else \
			echo "⚠️  rclone not found — dumps kept locally in $(BACKUP_DIR)/ only."; \
			echo "    Install + 'rclone config' a Drive remote to push backups off-machine."; \
		fi

restore:
	@test -n "$(VERSION)" || { echo "❌ VERSION required, e.g. make restore VERSION=v1.5.0"; exit 1; }
	@echo "⚠️  Restoring $(VERSION) into LOCAL dev warehouse ($(PG_HOST):$(PG_PORT)) — never run against prod."
	@mkdir -p $(BACKUP_DIR)/restore
	@if command -v rclone >/dev/null 2>&1; then \
		echo "☁️  Pulling $(VERSION) dumps from $(RCLONE_REMOTE)/$(VERSION)/..."; \
		rclone copy $(RCLONE_REMOTE)/$(VERSION)/ $(BACKUP_DIR)/restore/ --include "*.dump"; \
	else \
		echo "ℹ️  rclone not found — expecting dumps already in $(BACKUP_DIR)/restore/."; \
	fi
	@on=$$(ls $(BACKUP_DIR)/restore/open_navigator_$(VERSION)_*.dump 2>/dev/null | head -1); \
		os=$$(ls $(BACKUP_DIR)/restore/openstates_$(VERSION)_*.dump 2>/dev/null | head -1); \
		test -n "$$on" -a -n "$$os" || { echo "❌ Could not find $(VERSION) dumps in $(BACKUP_DIR)/restore/"; exit 1; }; \
		echo "♻️  Restoring open_navigator from $$on..."; \
		PGPASSWORD=$(PGPASSWORD) pg_restore -h $(PG_HOST) -p $(PG_PORT) -U $(PG_USER) -d open_navigator --clean --if-exists "$$on"; \
		echo "♻️  Restoring openstates from $$os..."; \
		PGPASSWORD=$(PGPASSWORD) pg_restore -h $(PG_HOST) -p $(PG_PORT) -U $(PG_USER) -d openstates --clean --if-exists "$$os"; \
		echo "✅ Restored $(VERSION)"
