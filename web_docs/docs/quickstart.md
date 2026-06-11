---
sidebar_position: 3
displayed_sidebar: developersSidebar
---

# Quick Start Guide

## Three Services

This project runs three separate services. Launch all three at once with `./start-all.sh`:

| Service | Port (Local) | Live URL | Description |
|---------|--------------|----------|-------------|
| **⚛️ Open Navigator** (`web_app`) | 5173 | [www.communityone.com](https://www.communityone.com) | **Main application** — search, filters, heatmap, data exploration |
| **📚 Documentation** (`web_docs`) | 3000 | [www.communityone.com/docs](https://www.communityone.com/docs) | Docusaurus site with complete guides and tutorials |
| **🔥 API Backend** (`api`) | 8000 | [www.communityone.com/api/docs](https://www.communityone.com/api/docs) | FastAPI server with AI agents |

> **💡 LIVE DEMO:** Visit **[www.communityone.com](https://www.communityone.com)** to use the hosted application.
>
> **💻 LOCAL DEV:** After running `./start-all.sh`, visit **http://localhost:5173**.

## Prerequisites

- Python 3.11+
- Node.js 18+
- A local Postgres warehouse on `localhost:5433` (databases `open_navigator` and `openstates`) — see [Configuration](#configuration) below
- **PostgreSQL client tools 17** (`psql`, `pg_dump`, `pg_restore`) — **recommended version**.
  The local warehouse server runs PG 16, but a **17** client dumps it *and* the (PG 16/17)
  Neon serving DB, and reads both dump formats. Keep `pg_dump` and `pg_restore` on the
  **same major version** (≥ any server you back up) to avoid `unsupported version` errors.
- Docker (optional — only for the containerized deployment)

## Installation

### Option 1: Start Everything at Once (Recommended)

```bash
# Clone repository
git clone https://github.com/getcommunityone/open-navigator.git
cd open-navigator

# Install dependencies
./install.sh                        # Python backend (creates .venv + .env from template)
cd web_app && npm install && cd ..  # React app
cd web_docs && npm install && cd .. # Documentation

# Start all three services in tmux
./start-all.sh
```

`start-all.sh` auto-installs the `web_app`/`web_docs` `node_modules` if they're missing,
so the two `npm install` steps above are optional on first run.

### Option 2: Using Makefile

```bash
# Install
make install            # Python backend
make install-web_app    # React app
make install-docs       # Documentation

# Start all services
make start-all

# …or individually:
make dev           # API only
make dev-web_app   # React app only
make dev-docs      # Docs only
```

### Option 3: Manual Setup

```bash
# Python backend
python3 -m venv .venv
source .venv/bin/activate           # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Optional: Spark + Delta Lake (only if you'll run Databricks/Spark scripts).
# Requires a Java runtime (e.g. `sudo apt install openjdk-17-jre-headless`).
# pip install -r requirements-spark.txt

# React app + documentation
cd web_app && npm install && cd ..
cd web_docs && npm install && cd ..

# Configure environment (see Configuration below)
cp .env.example .env

# Start services in separate terminals:
source .venv/bin/activate && python main.py serve  # Terminal 1 — API   (8000)
cd web_app && npm run dev                           # Terminal 2 — App   (5173)
cd web_docs && npm start                            # Terminal 3 — Docs  (3000)
```

### Option 4: Windows (PowerShell)

The `.sh` scripts and the `make` targets are Unix-oriented (`start-all.sh` uses
`tmux`, which Windows lacks). Use the PowerShell equivalents instead — they create
the same `.venv`, install from the same `requirements.txt`, and launch the same three
services, each in its own window:

```powershell
# From the repo root, in PowerShell:
.\install.ps1        # Python backend: creates .venv, installs deps, seeds .env
cd web_app;  npm install; cd ..
cd web_docs; npm install; cd ..
.\start-all.ps1      # API (8000) + App (5173) + Docs (3000), one window each
```

If you see *"running scripts is disabled on this system"*, PowerShell's execution
policy is blocking the script. Either allow local scripts once for your user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

…or run each script without changing the policy:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
powershell -ExecutionPolicy Bypass -File .\start-all.ps1
```

> **⚠️ Don't use `uv sync` to set up the backend on any OS.** The root
> `pyproject.toml` is a **uv workspace** whose members are only `packages/*`, so
> `uv sync` installs those workspace libraries but **not** the top-level
> `requirements.txt` — leaving out the dev tooling (`pytest`, `black`, `ruff`) and
> runtime deps like `yt-dlp`. Install the backend from `requirements.txt`
> (`.\install.ps1`, `./install.sh`, or `pip install -r requirements.txt`), which is
> the complete set. `uv sync` is only for working *inside* the `packages/*`
> libraries.

> **Tesseract / OCR on Windows:** `install.ps1` installs Tesseract via `winget`
> (or Chocolatey) when available; otherwise grab the
> [UB-Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki). OCR is
> optional — the app runs without it.

## Configuration

`.env.example` is organized in tiers so you only set what you actually use.
Copy it to `.env` and fill in values as needed:

```bash
cp .env.example .env
```

### Required (minimum to run locally)

The site needs exactly **one** variable to boot. It points the API at the
already-running local Postgres warehouse on port `5433`, and the API reads it for
both the civic-data warehouse and the auth/user tables:

```bash
NEON_DATABASE_URL_DEV=postgresql://postgres:password@localhost:5433/open_navigator
```

The web app (`5173`) and docs (`3000`) need no env vars to boot. With just the line
above, `./start-all.sh` brings up all three services.

### Optional for local development

Set these only for the features that need them — the site runs without all of them:

```bash
# OAuth login (omit a provider to disable just that login button)
FRONTEND_URL=http://localhost:5173
API_BASE_URL=http://localhost:8000
# GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET, HUGGINGFACE_CLIENT_ID / _SECRET, etc.

# Stable JWT signing across restarts (auto-generated if unset)
# JWT_SECRET_KEY=$(openssl rand -hex 32)

# Bill / legislator / vote features (restore the Open States dump first)
# OPENSTATES_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/openstates
```

### Data-source API keys (ingestion only)

Keys such as `OPENAI_API_KEY`, the `GEMINI_API_KEY_*` pool, `CENSUS_API_KEY`, and the
other source keys are needed **only** to run the ingestion/enrichment pipelines that
populate the warehouse — not to view the site.

### Deployment

`HF_TOKEN` / `HF_ORGANIZATION` (HuggingFace Spaces), `NEON_DATABASE_URL` (production
Neon), and the `DATABRICKS_*` variables are for deployment only and are not needed for
local development.

> See [`.env.example`](https://github.com/getcommunityone/open-navigator/blob/main/.env.example)
> for the full, commented list of every variable across all five tiers.

## Restore the Database

The three services give you the UI, but the app shows no civic data until you load a
warehouse snapshot into the local Postgres on `localhost:5433`. Restoring a shared dump
is far faster than rebuilding every dbt model from scratch.

**If you have the [Google Drive backup folder](#google-drive-folder-one-time-setup) synced**, it's one command:

```bash
make restore VERSION=snapshot-20260609   # dev only
```

**Otherwise, restore a dump someone shared with you** directly:

```bash
# Create the DB if needed, then restore (rebuilds the `public` serving schema the API reads):
PGPASSWORD=password createdb -h localhost -p 5433 -U postgres open_navigator 2>/dev/null || true
PGPASSWORD=password pg_restore -h localhost -p 5433 -U postgres -d open_navigator \
  --clean --if-exists open_navigator.dump
```

The API serves the **`public`** schema in `open_navigator` by default (`API_DB_SCHEMA=public`).
After the restore, refresh http://localhost:5173 — search, maps, and the heatmap will be populated.

> **Restore only into a local/dev warehouse — never into a production database.**

## Access Points

**💻 Local development:**
- **🚀 Main App:** http://localhost:5173
- **📚 Documentation:** http://localhost:3000
- **🔥 API Docs:** http://localhost:8000/docs

**🌐 Live application:**
- **🚀 Open Navigator:** https://www.communityone.com
- **📚 Documentation:** https://www.communityone.com/docs
- **🔥 API Docs:** https://www.communityone.com/api/docs

## Stop Services

```bash
./stop-all.sh
# or
make stop-all
```

## Running the System

### Start the API Server

```bash
# Using the virtual environment
source .venv/bin/activate
python main.py serve

# Or using make
make run
```

Visit http://localhost:8000 for the API and http://localhost:8000/docs for interactive documentation.

## Common Commands

```bash
# Activate virtual environment (required for all commands)
source .venv/bin/activate

# Start API server
python main.py serve

# Run with auto-reload (development)
python main.py serve --reload

# Check system status
python main.py status

# Run tests
pytest

# Or using make
make test
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'click'"

You need to activate the virtual environment first:

```bash
source .venv/bin/activate
```

### "Tesseract binary not found" or OCR errors

The `install.sh` script automatically installs tesseract-ocr on Linux (via apt) and macOS (via brew). If it failed or you're on a different system, install manually:

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get update && sudo apt-get install -y tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

**Verify installation:**
```bash
tesseract --version
```

OCR is optional but enables text extraction from scanned PDFs and images.

### "error: externally-managed-environment"

Don't use `pip install` directly. Use the virtual environment:

```bash
# Create venv if not exists
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Now install
pip install -r requirements.txt
```

### Permission denied when running install.sh

```bash
chmod +x install.sh
./install.sh
```

## Releases & Data Versioning

Open Navigator follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).
**Every release is tied to a Postgres backup** so that a given version of the code can
always be paired with the warehouse state it was built and tested against.

Given a version `MAJOR.MINOR.PATCH` (e.g. `1.4.2`):

| Bump      | When                                                                            | Example         |
| --------- | ------------------------------------------------------------------------------- | --------------- |
| **MAJOR** | Breaking API/schema change, dropped table or endpoint, incompatible dbt model   | `1.4.2 → 2.0.0` |
| **MINOR** | New data source, new endpoint, new dbt mart, backward-compatible feature        | `1.4.2 → 1.5.0` |
| **PATCH** | Bug fix, data backfill, doc change, no schema or contract change                | `1.4.2 → 1.4.3` |

A release bundles three things at the same version number:

1. **Code** — a git tag (`vMAJOR.MINOR.PATCH`).
2. **Schema/marts** — the dbt models as built at that tag.
3. **Data** — a Postgres backup snapshot stored off-machine (see [Database Backups](#database-backups) below).

## Database Backups

Backup and restore are Makefile targets — no manual `pg_dump`/`pg_restore` needed. Each
stamps the dump files with version/date/git SHA and syncs them off-machine through Google
Drive. Pick the scope that fits — and note that **two of the three are free of personal
user data**:

| Command | Scope | Personal user data? |
| --- | --- | --- |
| `make backup VERSION=v1.5.0` | **Full** — entire `open_navigator` warehouse (bronze/gold/staging/intermediate/public) **+** `openstates`. Self-contained; ~170 GB. | ⚠️ **Yes** — includes the `user`/auth/social tables. Keep private. |
| `make backup-neon VERSION=v1.5.0` | **Neon serving** (recommended) — dumps the production Neon serving DB; civic data as standalone materialized tables. Small (~0.5 GB). | ✅ **No** |
| `make backup-public VERSION=v1.5.0` | **Local public** — dumps only the local `public` serving schema; civic views + `event_documents`. | ✅ **No** (personal tables excluded) |
| `make restore VERSION=v1.5.0` | Restore the full backup into the local warehouse. **Dev only.** | — |
| `make restore-neon VERSION=v1.5.0` | Restore a Neon snapshot into a separate local db (`open_navigator_serving`). **Dev only.** | — |
| `make restore-public VERSION=v1.5.0` | Restore the local `public` schema (needs `gold` present). **Dev only.** | — |

The `VERSION` label decides **where the dump is filed** inside the backup folder:

- A **semver tag** (`v1.5.0`) → `open-navigator-backups/releases/v1.5.0/` — for tagged releases.
- **Any other label** (e.g. `2026-06-09`, `snapshot-20260609`) → `open-navigator-backups/snapshots/<label>/` — for ad-hoc point-in-time backups.

`restore*` searches **both** folders, so you restore with the same label you backed up with
regardless of which one it landed in. Exact commands live in the
[`backup` targets in the Makefile](https://github.com/getcommunityone/open-navigator/blob/main/Makefile).

### Backing up the serving data without user PII

To share or version the public civic data **without** shipping personal user information
(accounts, OAuth state, social graph, feed prefs, saved locations), use one of the
PII-free targets. Both exclude the same app/runtime tables that the Neon serving DB never
mirrors (`user`, `contact_oauth_state`, `social_follows`, `user_lens_prefs`,
`user_locations`, `user_signal_prefs`, `meeting_document_gap_cache`).

**`make backup-neon` (recommended).** Dumps the production Neon serving DB
(`NEON_DATABASE_URL` from `.env`). That DB is **civic-only by construction** — the
`sync_public_to_neon.py` loader never copies the user/auth tables — and its serving objects
are real **materialized tables**, so the dump is standalone (no dependency on `gold`):

```bash
make backup-neon VERSION=snapshot-20260609   # writes one small neon_serving_*.dump, no PII
```

`pg_dump` is read-only, so this is safe to run against prod. Restore into a **separate
local** database (never prod) and optionally point the API at it for a PII-free local
serving instance:

```bash
make restore-neon VERSION=snapshot-20260609  # → local db open_navigator_serving (dev only)
```

The Neon dump is taken with `--no-owner --no-privileges`, and `restore-neon` restores with
`--role=$(PG_USER)`, so all objects end up owned by your **local** `postgres` user — not the
Neon role. (Same for `make backup-public`.)

**`make backup-public`.** Dumps the local `public` schema with the personal tables
excluded — civic views + `event_documents` only. It does **not** include the Postgres
extensions (`pg_trgm`, `btree_gin`, …) that live in `public`, so restoring it never drops
them and `gold`'s indexes stay safe. Because the views reference `gold`, restore it onto a
warehouse that already has `gold`:

```bash
make backup-public VERSION=snapshot-20260609   # local public, personal tables excluded
```

> **Restore only into a local/dev warehouse — never into a production database.** The full
> `make backup` is the only one that contains user accounts; treat its dumps as private and
> do not share them via a public Drive link.

> **Client version.** The backup targets auto-select the newest PostgreSQL client under
> `/usr/lib/postgresql/*/bin` (so a PG 17 `pg_dump` is used for the PG 17 Neon server even
> when your `PATH` still points at PG 16). Install PG 17 client tools (see
> [Prerequisites](#prerequisites)). Override the choice if needed with
> `make backup-neon VERSION=… PG_BIN=/usr/lib/postgresql/17/bin/` (or `PG_BIN=` to force `PATH`).

### Google Drive folder (one-time setup)

`make backup` writes into a folder synced by **Google Drive for Desktop**, reached in WSL
through a symlink named `open-navigator-backups` in the repo root. Set it up once per machine:

```bash
# 1. Google Drive for Desktop must be running on Windows (so H:\My Drive is accessible).

# 2. Mount H: into WSL and make it persist across restarts:
sudo mkdir -p /mnt/h && sudo mount -t drvfs 'H:' /mnt/h
echo 'H: /mnt/h drvfs defaults 0 0' | sudo tee -a /etc/fstab

# 3. Create the Drive folder and link it into the repo (the symlink is gitignored):
mkdir -p "/mnt/h/My Drive/open-navigator-backups"
ln -sfn "/mnt/h/My Drive/open-navigator-backups" open-navigator-backups

# 4. Verify:
test -d open-navigator-backups/ && echo "✅ Drive backup folder ready"
```

> Different Drive letter? Swap `H:` / `/mnt/h`. No Drive for Desktop? Point `BACKUP_DIR`
> at any folder and sync it with [`rclone`](https://rclone.org/drive/) instead.

### Create a backup

With the [Google Drive folder](#google-drive-folder-one-time-setup) in place, dump both
databases with one command. Pick any label — a semver tag for a release, or a date for an
ad-hoc snapshot:

```bash
make backup VERSION=snapshot-20260609
```

This stages the dumps on local disk, copies them into
`open-navigator-backups/snapshots/snapshot-20260609/` (a non-`v` label files under
`snapshots/`; each filename stamped with the version, date, and git SHA), and Google Drive
for Desktop syncs them off-machine automatically. Confirm they landed:

```bash
ls open-navigator-backups/snapshots/snapshot-20260609/
# open_navigator_snapshot-20260609_20260609_a1b2c3d.dump
# openstates_snapshot-20260609_20260609_a1b2c3d.dump
```

### Share a snapshot with a collaborator

1. Run `make backup VERSION=<label>`.
2. At [drive.google.com](https://drive.google.com), open the `open-navigator-backups`
   folder → right-click the `<label>` folder → **Share** → set "Anyone with the link →
   Viewer" and copy the link.
3. The recipient either shares the **same** Drive folder and runs
   `make restore VERSION=<label>`, or downloads the `.dump` and restores it manually
   (see [Restore the Database](#restore-the-database)).

For a tagged release, also push the matching git tag and record the backup link + SHA in
the [Release History](development/release-history.md):

```bash
git tag -a v1.5.0 -m "feat: add grants.gov opportunities to search" && git push origin v1.5.0
```

## Next Steps

1. Configure your `.env` file (see [Configuration](#configuration) — only `NEON_DATABASE_URL_DEV` is required)
2. Start all three services: `./start-all.sh`
3. Open the app at http://localhost:5173
4. Check out the interactive API docs: http://localhost:8000/docs

For more details, see the main [README.md](https://github.com/getcommunityone/open-navigator/blob/main/README.md).
