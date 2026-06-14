.PHONY: help install install-web_app install-docs build-web_app build-docs clean test run dev dev-web_app dev-docs start-all stop-all dev-full docker-up docker-down deploy-databricks grants-refresh backup-preflight backup backup-public backup-neon restore restore-public restore-neon azure-init azure-plan azure-apply azure-fmt

# Azure subscriptions Terraform (infra/azure). Creds load from infra/azure/.env (ARM_*),
# never committed. Override dir with AZURE_TF_DIR if needed.
AZURE_TF_DIR ?= infra/azure

help:
	@echo "🦷 Open Navigator - Makefile Commands"
	@echo "===================================================="
	@echo ""
	@echo "🚀 Quick Start:"
	@echo "  make start-all         - Start ALL services (API + Dashboard + Docs) with tmux"
	@echo "  make stop-all          - Stop all running services"
	@echo ""
	@echo "🐍 Python Backend:"
	@echo "  make install           - Install Python dependencies in .venv"
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
	@echo "  make backup VERSION=v1.5.0         - Dump full open_navigator + openstates, push to Drive"
	@echo "  make backup-neon VERSION=v1.5.0    - Dump the Neon serving DB (civic only, NO user PII) [recommended]"
	@echo "  make backup-public VERSION=v1.5.0  - Dump the local public schema, personal user tables excluded"
	@echo "  make restore VERSION=v1.5.0        - Restore a full backup (dev only)"
	@echo "  make restore-neon VERSION=v1.5.0   - Restore Neon snapshot into local '$(NEON_RESTORE_DB)' (dev only)"
	@echo "  make restore-public VERSION=v1.5.0 - Restore the public schema (dev only; needs gold present)"
	@echo ""
	@echo "☁️  Azure subscriptions (Terraform, infra/azure — creds from infra/azure/.env):"
	@echo "  make azure-init        - terraform init"
	@echo "  make azure-fmt         - terraform fmt + validate"
	@echo "  make azure-plan        - terraform plan"
	@echo "  make azure-apply       - terraform apply"
	@echo ""

# --- Azure subscriptions Terraform ------------------------------------------------
# Each target sources infra/azure/.env so ARM_* creds reach terraform without ever
# living in a .tf/.tfvars file. Fails loudly if .env is missing.
define _azure_tf
	@command -v terraform >/dev/null 2>&1 || { echo "❌ terraform not installed (https://developer.hashicorp.com/terraform/install)"; exit 1; }
	@test -f "$(AZURE_TF_DIR)/.env" || { echo "❌ $(AZURE_TF_DIR)/.env missing — copy $(AZURE_TF_DIR)/.env.example and fill in ARM_* creds"; exit 1; }
	@set -a && . "$(AZURE_TF_DIR)/.env" && set +a && cd "$(AZURE_TF_DIR)" && terraform $(1)
endef

azure-init:
	$(call _azure_tf,init)

azure-fmt:
	$(call _azure_tf,fmt -recursive)
	$(call _azure_tf,validate)

azure-plan:
	$(call _azure_tf,plan)

azure-apply:
	$(call _azure_tf,apply)

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
	@. .venv/bin/activate && pytest tests/ -v

run: build-web_app
	@echo "🚀 Starting application (production mode)..."
	@. .venv/bin/activate && uvicorn api.app:app --host 0.0.0.0 --port 8000

dev:
	@echo "🔧 Starting backend with auto-reload..."
	@echo "📡 Backend running at http://localhost:8000"
	@. .venv/bin/activate && uvicorn api.app:app --reload

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
	@. .venv/bin/activate && uvicorn api.app:app --reload & \
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
	@. .venv/bin/activate && python examples/example_workflow.py

heatmap:
	@echo "Generating example heatmap..."
	@. .venv/bin/activate && python main.py generate-heatmap --output example_heatmap.html
	@echo "✓ Heatmap saved to example_heatmap.html"

init:
	@echo "Initializing system..."
	@. .venv/bin/activate && python main.py init

status:
	@echo "Checking system status..."
	@. .venv/bin/activate && python main.py status

format:
	@echo "Formatting code..."
	@. .venv/bin/activate && black .
	@. .venv/bin/activate && ruff check . --fix
	@echo "✓ Code formatted"

lint:
	@echo "Linting code..."
	@. .venv/bin/activate && ruff check .
	@. .venv/bin/activate && mypy agents/ pipeline/ visualization/ api/

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
#   make backup VERSION=v1.5.0    # dump both DBs (version-stamped) into the Drive folder
#   make restore VERSION=v1.5.0   # restore that version's dumps from the Drive folder (DEV ONLY)
#
# BACKUP_DIR is a WSL symlink that points at the Google Drive for Desktop folder on
# Windows (open-navigator-backups -> /mnt/h/My Drive/open-navigator-backups). Writing
# there means Google Drive auto-syncs the dumps off-machine — no rclone needed.
#
# pg_dump streams to a LOCAL staging dir first (BACKUP_STAGING, on fast ext4), then the
# finished file is copied into the Drive folder. This sidesteps a known DriveFS-over-WSL
# failure mode where large sequential writes straight into the virtual H: drive stall.
# One-time setup is documented in web_docs/docs/quickstart.md.
# Override any of these via env. Defaults match the local dev warehouse (localhost:5433).
PG_HOST        ?= localhost
PG_PORT        ?= 5433
PG_USER        ?= postgres
PGPASSWORD     ?= password
BACKUP_DIR     ?= open-navigator-backups
BACKUP_STAGING ?= .backup-staging
# Local DB to restore a Neon serving snapshot into (NEVER prod; localhost only).
NEON_RESTORE_DB ?= open_navigator_serving
# Personal / app-owned tables in public.* that must NEVER land in a shared snapshot.
# Mirrors RUNTIME_OWNED in packages/hosting/src/hosting/neon/sync_public_to_neon.py — the
# same set the Neon serving DB already excludes (user accounts, OAuth state, social graph,
# feed prefs). backup-public strips these so no personal user data leaves the machine.
PII_EXCLUDE_TABLES ?= user contact_oauth_state social_follows user_lens_prefs user_locations user_signal_prefs meeting_document_gap_cache
# Postgres client tools. `pg_dump` must be >= the server it dumps (Neon is PG 17), and
# `pg_restore` >= the dump's archive format — a mismatched major aborts the dump. We
# AUTO-SELECT the newest client installed under /usr/lib/postgresql/*/bin, so PG 17 is used
# even when PATH still points at PG 16; this is empty (→ PATH) on other platforms. Override
# explicitly with PG_BIN=/usr/lib/postgresql/17/bin/  (or PG_BIN= to force PATH).
PG_BIN      ?= $(shell ls -d /usr/lib/postgresql/*/bin/ 2>/dev/null | sort -V | tail -1)
PG_DUMP     ?= $(PG_BIN)pg_dump
PG_RESTORE  ?= $(PG_BIN)pg_restore
PG_CREATEDB ?= $(PG_BIN)createdb

# Verify the Drive folder is reachable, and if not, diagnose *why* and print the exact
# fix. Most common cause: the WSL symlink exists but the Drive letter never got mounted
# (e.g. after a WSL restart with no /etc/fstab entry) — see web_docs/docs/quickstart.md.
backup-preflight:
	@test -d "$(BACKUP_DIR)/" && exit 0; \
	echo "❌ $(BACKUP_DIR) does not resolve to a directory."; \
	if [ -L "$(BACKUP_DIR)" ]; then \
		tgt=$$(readlink "$(BACKUP_DIR)"); \
		root=$$(printf '%s' "$$tgt" | grep -oE '^/mnt/[a-z]+'); \
		letter=$$(printf '%s' "$$root" | sed -E 's:^/mnt/::' | tr a-z A-Z); \
		echo "   Symlink → $$tgt"; \
		if [ -n "$$root" ] && ! mountpoint -q "$$root" 2>/dev/null; then \
			echo "   Drive letter $$letter: is not mounted in WSL. Mount it once (needs sudo password):"; \
			echo "     sudo mkdir -p $$root && sudo mount -t drvfs '$$letter:' $$root"; \
			echo "     echo '$$letter: $$root drvfs defaults 0 0' | sudo tee -a /etc/fstab   # persist across WSL restarts"; \
			echo "   (Google Drive for Desktop must be running on Windows so $$letter: exists.)"; \
		else \
			echo "   Mount is present but the folder is missing. Create it: mkdir -p \"$$tgt\""; \
		fi; \
	else \
		echo "   Symlink '$(BACKUP_DIR)' is missing. See web_docs/docs/quickstart.md (Google Drive folder one-time setup)."; \
	fi; \
	exit 1

backup:
	@test -n "$(VERSION)" || { echo "❌ VERSION required, e.g. make backup VERSION=v1.5.0"; exit 1; }
	@$(MAKE) --no-print-directory backup-preflight
	@set -e; stamp=$$(date +%Y%m%d); sha=$$(git rev-parse --short HEAD 2>/dev/null || echo nogit); \
		stage="$(BACKUP_STAGING)/$(VERSION)"; case "$(VERSION)" in v[0-9]*) sub=releases;; *) sub=snapshots;; esac; dir="$(BACKUP_DIR)/$$sub/$(VERSION)"; \
		mkdir -p "$$stage" "$$dir"; \
		on="open_navigator_$(VERSION)_$${stamp}_$${sha}.dump"; \
		os="openstates_$(VERSION)_$${stamp}_$${sha}.dump"; \
		echo "📦 Dumping open_navigator + openstates at $(VERSION) ($$stamp, $$sha) to local staging..."; \
		PGPASSWORD=$(PGPASSWORD) $(PG_DUMP) -h $(PG_HOST) -p $(PG_PORT) -U $(PG_USER) -Fc open_navigator -f "$$stage/$$on"; \
		PGPASSWORD=$(PGPASSWORD) $(PG_DUMP) -h $(PG_HOST) -p $(PG_PORT) -U $(PG_USER) -Fc openstates     -f "$$stage/$$os"; \
		echo "📤 Copying dumps into the Drive folder ($$dir/)..."; \
		cp "$$stage/$$on" "$$dir/$$on" && cp "$$stage/$$os" "$$dir/$$os"; \
		rm -rf "$$stage"; \
		echo "✅ Dumps in $$dir/ — Google Drive for Desktop will sync them off-machine automatically."

restore:
	@test -n "$(VERSION)" || { echo "❌ VERSION required, e.g. make restore VERSION=v1.5.0"; exit 1; }
	@$(MAKE) --no-print-directory backup-preflight
	@echo "⚠️  Restoring $(VERSION) into LOCAL dev warehouse ($(PG_HOST):$(PG_PORT)) — never run against prod."
	@dir=$$(ls -d "$(BACKUP_DIR)"/releases/$(VERSION) "$(BACKUP_DIR)"/snapshots/$(VERSION) 2>/dev/null | head -1); test -n "$$dir" || dir="$(BACKUP_DIR)/snapshots/$(VERSION)"; \
		on=$$(ls "$$dir"/open_navigator_$(VERSION)_*.dump 2>/dev/null | head -1); \
		os=$$(ls "$$dir"/openstates_$(VERSION)_*.dump 2>/dev/null | head -1); \
		test -n "$$on" -a -n "$$os" || { echo "❌ Could not find $(VERSION) dumps in $$dir/"; exit 1; }; \
		echo "♻️  Restoring open_navigator from $$on..."; \
		PGPASSWORD=$(PGPASSWORD) $(PG_RESTORE) -h $(PG_HOST) -p $(PG_PORT) -U $(PG_USER) -d open_navigator --clean --if-exists "$$on"; \
		echo "♻️  Restoring openstates from $$os..."; \
		PGPASSWORD=$(PGPASSWORD) $(PG_RESTORE) -h $(PG_HOST) -p $(PG_PORT) -U $(PG_USER) -d openstates --clean --if-exists "$$os"; \
		echo "✅ Restored $(VERSION)"

# Public-only backup: dumps ONLY the `public` serving schema of open_navigator, stored as
# its own dump file separate from the bronze/gold/private warehouse. Tiny vs the ~170GB DB.
# The personal/app-owned tables (PII_EXCLUDE_TABLES — user accounts, OAuth state, social
# graph, feed prefs) are EXCLUDED, so no personal user data leaves the machine; the dump
# is the civic serving layer only (views + event_documents).
# A `--schema=public` dump does NOT include the extensions (pg_trgm, btree_gin, …) that
# live in `public`, so it never DROPs them on restore — gold's indexes are safe.
# Caveat: the public views are defined over `gold`, so restoring them needs `gold`
# present (restore the full/private warehouse first, or restore onto your existing one).
backup-public:
	@test -n "$(VERSION)" || { echo "❌ VERSION required, e.g. make backup-public VERSION=v1.5.0"; exit 1; }
	@$(MAKE) --no-print-directory backup-preflight
	@set -e; stamp=$$(date +%Y%m%d); sha=$$(git rev-parse --short HEAD 2>/dev/null || echo nogit); \
		stage="$(BACKUP_STAGING)/$(VERSION)"; case "$(VERSION)" in v[0-9]*) sub=releases;; *) sub=snapshots;; esac; dir="$(BACKUP_DIR)/$$sub/$(VERSION)"; \
		mkdir -p "$$stage" "$$dir"; \
		f="open_navigator_public_$(VERSION)_$${stamp}_$${sha}.dump"; \
		excl=""; for t in $(PII_EXCLUDE_TABLES); do excl="$$excl --exclude-table=public.$$t"; done; \
		echo "📦 Dumping open_navigator schema 'public' (civic only — personal user tables excluded) at $(VERSION)..."; \
		PGPASSWORD=$(PGPASSWORD) $(PG_DUMP) -h $(PG_HOST) -p $(PG_PORT) -U $(PG_USER) -Fc --no-owner --no-privileges --schema=public $$excl open_navigator -f "$$stage/$$f"; \
		echo "📤 Copying dump into the Drive folder ($$dir/)..."; \
		cp "$$stage/$$f" "$$dir/$$f"; \
		rm -rf "$$stage"; \
		echo "✅ Public-only dump (no personal user data) in $$dir/$$f — Google Drive will sync it off-machine."

# Neon serving backup (recommended for a PII-free public snapshot): dumps the PRODUCTION
# Neon serving DB from NEON_DATABASE_URL in .env. That DB is civic-only by construction —
# sync_public_to_neon.py NEVER mirrors the user/auth/social/feed tables — and its serving
# objects are real materialized tables (not views over gold), so the dump is standalone
# AND contains no personal user data. pg_dump is READ-ONLY, so it is safe against prod.
# We strip Neon's `-pooler` host suffix because pg_dump needs the direct (session) endpoint.
# `--no-owner --no-privileges` drops Neon's role/grants so the dump restores cleanly under
# the LOCAL `$(PG_USER)` user (restore-neon also passes --role=$(PG_USER)).
backup-neon:
	@test -n "$(VERSION)" || { echo "❌ VERSION required, e.g. make backup-neon VERSION=v1.5.0"; exit 1; }
	@$(MAKE) --no-print-directory backup-preflight
	@set -e; url=$$(grep -E '^NEON_DATABASE_URL=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'"); \
		test -n "$$url" || { echo "❌ NEON_DATABASE_URL not found in .env (the prod serving DB)."; exit 1; }; \
		url=$$(printf '%s' "$$url" | sed 's/-pooler//'); \
		stamp=$$(date +%Y%m%d); sha=$$(git rev-parse --short HEAD 2>/dev/null || echo nogit); \
		stage="$(BACKUP_STAGING)/$(VERSION)"; case "$(VERSION)" in v[0-9]*) sub=releases;; *) sub=snapshots;; esac; dir="$(BACKUP_DIR)/$$sub/$(VERSION)"; \
		mkdir -p "$$stage" "$$dir"; \
		f="neon_serving_$(VERSION)_$${stamp}_$${sha}.dump"; \
		echo "📦 Dumping Neon serving DB (civic only — no personal user data) at $(VERSION) to local staging..."; \
		$(PG_DUMP) --no-owner --no-privileges -Fc "$$url" -f "$$stage/$$f"; \
		echo "📤 Copying dump into the Drive folder ($$dir/)..."; \
		cp "$$stage/$$f" "$$dir/$$f"; \
		rm -rf "$$stage"; \
		echo "✅ Neon serving dump (no PII) in $$dir/$$f — Google Drive will sync it off-machine."

# Restore a Neon serving snapshot into a SEPARATE LOCAL database (default
# open_navigator_serving on localhost:5433). Never touches prod and never the main
# open_navigator warehouse. Point the API at it (NEON_DATABASE_URL_DEV) for a PII-free
# local serving instance.
restore-neon:
	@test -n "$(VERSION)" || { echo "❌ VERSION required, e.g. make restore-neon VERSION=v1.5.0"; exit 1; }
	@$(MAKE) --no-print-directory backup-preflight
	@echo "⚠️  Restoring Neon serving $(VERSION) into LOCAL db '$(NEON_RESTORE_DB)' ($(PG_HOST):$(PG_PORT)) — never prod."
	@dir=$$(ls -d "$(BACKUP_DIR)"/releases/$(VERSION) "$(BACKUP_DIR)"/snapshots/$(VERSION) 2>/dev/null | head -1); test -n "$$dir" || dir="$(BACKUP_DIR)/snapshots/$(VERSION)"; \
		f=$$(ls "$$dir"/neon_serving_$(VERSION)_*.dump 2>/dev/null | head -1); \
		test -n "$$f" || { echo "❌ Could not find $(VERSION) Neon dump in $$dir/ (run: make backup-neon VERSION=$(VERSION))"; exit 1; }; \
		PGPASSWORD=$(PGPASSWORD) $(PG_CREATEDB) -h $(PG_HOST) -p $(PG_PORT) -U $(PG_USER) $(NEON_RESTORE_DB) 2>/dev/null || true; \
		echo "♻️  Restoring $$f into $(NEON_RESTORE_DB)..."; \
		PGPASSWORD=$(PGPASSWORD) $(PG_RESTORE) -h $(PG_HOST) -p $(PG_PORT) -U $(PG_USER) -d $(NEON_RESTORE_DB) --no-owner --no-privileges --role=$(PG_USER) --clean --if-exists "$$f"; \
		echo "✅ Restored Neon serving $(VERSION) into local '$(NEON_RESTORE_DB)' (owned by $(PG_USER))"

restore-public:
	@test -n "$(VERSION)" || { echo "❌ VERSION required, e.g. make restore-public VERSION=v1.5.0"; exit 1; }
	@$(MAKE) --no-print-directory backup-preflight
	@echo "⚠️  Restoring $(VERSION) PUBLIC schema into LOCAL dev warehouse ($(PG_HOST):$(PG_PORT)) — never run against prod."
	@echo "   Note: public serving views reference 'gold'; restore the full backup first if gold is absent."
	@dir=$$(ls -d "$(BACKUP_DIR)"/releases/$(VERSION) "$(BACKUP_DIR)"/snapshots/$(VERSION) 2>/dev/null | head -1); test -n "$$dir" || dir="$(BACKUP_DIR)/snapshots/$(VERSION)"; \
		f=$$(ls "$$dir"/open_navigator_public_$(VERSION)_*.dump 2>/dev/null | head -1); \
		test -n "$$f" || { echo "❌ Could not find $(VERSION) public dump in $$dir/ (run: make backup-public VERSION=$(VERSION))"; exit 1; }; \
		echo "♻️  Restoring open_navigator (public schema only) from $$f..."; \
		PGPASSWORD=$(PGPASSWORD) $(PG_RESTORE) -h $(PG_HOST) -p $(PG_PORT) -U $(PG_USER) -d open_navigator --schema=public --clean --if-exists "$$f"; \
		echo "✅ Restored $(VERSION) public schema"
