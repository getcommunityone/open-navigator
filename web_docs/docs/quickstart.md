---
sidebar_position: 3
displayed_sidebar: developersSidebar
---

# Quick Start Guide

## Installation

### Option 1: Automated Installation (Recommended)

Run the installation script:

```bash
chmod +x install.sh
./install.sh
```

This will:
- Create a virtual environment
- Install all dependencies
- Create .env file from template
- Set up the project structure

### Option 2: Manual Installation

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
```

### Option 3: Using Makefile

```bash
make install
```

## Configuration

Edit the `.env` file and add your API keys:

```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here

# For production (Databricks)
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=your_databricks_token_here
DATABRICKS_WAREHOUSE_ID=your_warehouse_id_here

# Optional: HuggingFace (for publishing datasets)
HF_TOKEN=hf_your_write_token_here  # Needs Write permissions
HF_ORGANIZATION=YourOrgName  # Optional
```

## Running the System

### Start the API Server

```bash
# Using the virtual environment
source venv/bin/activate
python main.py serve

# Or using make
make run
```

Visit http://localhost:8000 for the API and http://localhost:8000/docs for interactive documentation.

### Run Example Workflow

```bash
# Activate venv first
source venv/bin/activate

# Run example
python examples/example_workflow.py

# Or using make
make example
```

### Generate Heatmap

```bash
# Activate venv first
source venv/bin/activate

# Generate heatmap
python main.py generate-heatmap --output heatmap.html

# Or using make
make heatmap
```

## Docker Deployment

```bash
# Start all services
make docker-up

# Stop all services
make docker-down
```

This starts:
- API server on http://localhost:8000
- Qdrant vector DB on http://localhost:6333
- Jupyter notebook on http://localhost:8888

## Common Commands

```bash
# Activate virtual environment (required for all commands)
source venv/bin/activate

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
source venv/bin/activate
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
python3 -m venv venv

# Activate it
source venv/bin/activate

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

### Semantic Versioning Scheme

Given a version `MAJOR.MINOR.PATCH` (e.g. `1.4.2`):

| Bump      | When                                                                            | Example         |
| --------- | ------------------------------------------------------------------------------- | --------------- |
| **MAJOR** | Breaking API/schema change, dropped table or endpoint, incompatible dbt model   | `1.4.2 → 2.0.0` |
| **MINOR** | New data source, new endpoint, new dbt mart, backward-compatible feature        | `1.4.2 → 1.5.0` |
| **PATCH** | Bug fix, data backfill, doc change, no schema or contract change                | `1.4.2 → 1.4.3` |

A release bundles three things at the same version number:

1. **Code** — a git tag (`vMAJOR.MINOR.PATCH`).
2. **Schema/marts** — the dbt models as built at that tag.
3. **Data** — a Postgres backup snapshot stored off-machine (see below).

### Cutting a Release

```bash
# 1. Make sure you're on an up-to-date main with green CI
git checkout main && git pull

# 2. Tag the release (annotated tag, semver, v-prefixed)
git tag -a v1.5.0 -m "feat: add grants.gov opportunities to search"
git push origin v1.5.0
```

### Backing Up the Warehouse for a Release

The warehouse runs on `localhost:5433` with two databases: `open_navigator` (primary)
and `openstates` (source). The quickest path is the Makefile target, which dumps both
databases (version-stamped) **and** uploads them to Drive in one step:

```bash
make backup VERSION=v1.5.0
```

Under the hood it creates a compressed, version-stamped dump of each database so the
filename ties the data snapshot back to the git tag:

```bash
VERSION=v1.5.0
STAMP=$(date +%Y%m%d)

# Custom-format (-Fc) dumps — compressed and restorable with pg_restore
pg_dump -h localhost -p 5433 -U postgres -Fc open_navigator \
  -f "open_navigator_${VERSION}_${STAMP}.dump"

pg_dump -h localhost -p 5433 -U postgres -Fc openstates \
  -f "openstates_${VERSION}_${STAMP}.dump"
```

### Pushing Backups to Google Drive

> The remote backup target (Google Drive folder / `rclone` remote) is **not yet
> provisioned** — fill in the real remote name and folder once it exists. Do not
> commit dumps to git (they are large and may contain PII-adjacent data).

Recommended tool is [`rclone`](https://rclone.org/drive/) (handles Drive auth,
chunked uploads, and resumes). One-time setup: `rclone config` → create a `drive`
remote (name it e.g. `gdrive`).

```bash
# Upload the version-stamped dumps to a "releases" folder on Drive
rclone copy open_navigator_${VERSION}_${STAMP}.dump gdrive:open-navigator-backups/${VERSION}/
rclone copy openstates_${VERSION}_${STAMP}.dump     gdrive:open-navigator-backups/${VERSION}/

# Verify the upload landed
rclone ls gdrive:open-navigator-backups/${VERSION}/
```

Keep one folder per release tag (`open-navigator-backups/v1.5.0/`) so the data
snapshot is unambiguously paired with the code tag.

### Restoring a Versioned Backup

To reproduce the exact state of a release locally — check out the matching git tag,
then restore its data snapshot. The Makefile target pulls the dumps from Drive and
restores both databases:

```bash
git checkout v1.5.0
make restore VERSION=v1.5.0
```

Equivalent manual steps:

```bash
git checkout v1.5.0

# Pull the dumps for that version from Drive
rclone copy gdrive:open-navigator-backups/v1.5.0/ ./restore/ --include "*.dump"

# Restore into clean databases (drops & recreates objects)
pg_restore -h localhost -p 5433 -U postgres -d open_navigator --clean --if-exists \
  ./restore/open_navigator_v1.5.0_*.dump

pg_restore -h localhost -p 5433 -U postgres -d openstates --clean --if-exists \
  ./restore/openstates_v1.5.0_*.dump
```

> **Restore only into a local/dev warehouse (`localhost:5433` or a dev Neon
> instance) — never into a production database.**

Every release is recorded in the [Release History](development/release-history.md),
which pairs each version with its backup location.

## Next Steps

1. Configure your `.env` file with API keys
2. Run the example workflow: `make example`
3. Start the API server: `make run`
4. Check out the interactive docs: http://localhost:8000/docs
5. Generate a heatmap: `make heatmap`

For more details, see the main [README.md](README.md).
