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

### One-Time Setup: Google Drive Backup Folder (WSL)

Backups are written into a folder synced by **Google Drive for Desktop** on Windows,
so they replicate off-machine automatically — no separate upload step. The dev
environment is WSL, where Google Drive's virtual `H:` drive is reached through a
symlink named `open-navigator-backups` in the repo root.

Do this once per machine:

```bash
# 1. Make sure Google Drive for Desktop is running on Windows and H:\My Drive is accessible.

# 2. Mount H: into WSL (Google Drive's virtual drive is not auto-mounted). Needs sudo:
sudo mkdir -p "/mnt/h"
sudo mount -t drvfs 'H:' /mnt/h

# 3. Make the mount persist across WSL restarts — add this line to /etc/fstab:
#    H: /mnt/h drvfs defaults 0 0
echo 'H: /mnt/h drvfs defaults 0 0' | sudo tee -a /etc/fstab

# 4. Create the Drive folder and the repo symlink (the symlink is gitignored, per-machine):
mkdir -p "/mnt/h/My Drive/open-navigator-backups"
ln -sfn "/mnt/h/My Drive/open-navigator-backups" open-navigator-backups

# 5. Verify the symlink resolves to a real directory:
test -d "open-navigator-backups/" && echo "✅ Drive backup folder ready"
```

> If you use a different Drive letter, change `H:` and `/mnt/h` accordingly. To push
> off-machine **without** Drive for Desktop, point `BACKUP_DIR` at any folder and sync
> it with [`rclone`](https://rclone.org/drive/) instead — the Makefile targets only
> care that `BACKUP_DIR` resolves to a directory.

### Backing Up the Warehouse for a Release

The warehouse runs on `localhost:5433` with two databases: `open_navigator` (primary)
and `openstates` (source). One command dumps both, version-stamped, into the
Drive-synced folder:

```bash
make backup VERSION=v1.5.0
```

This writes compressed (`-Fc`) dumps to
`open-navigator-backups/releases/v1.5.0/`, with the version, date, and git SHA in each
filename so the data snapshot ties back to the exact code tag:

```
open-navigator-backups/releases/v1.5.0/
├── open_navigator_v1.5.0_20260609_a1b2c3d.dump
└── openstates_v1.5.0_20260609_a1b2c3d.dump
```

Google Drive for Desktop then syncs the folder off-machine automatically. The
equivalent manual `pg_dump` is:

```bash
pg_dump -h localhost -p 5433 -U postgres -Fc open_navigator \
  -f "open-navigator-backups/releases/v1.5.0/open_navigator_v1.5.0_$(date +%Y%m%d)_$(git rev-parse --short HEAD).dump"
```

### Restoring a Versioned Backup

To reproduce the exact state of a release locally — check out the matching git tag,
then restore its data snapshot from the Drive folder:

```bash
git checkout v1.5.0
make restore VERSION=v1.5.0
```

Equivalent manual steps (Drive for Desktop streams the file on access):

```bash
git checkout v1.5.0

# Restore into clean databases (drops & recreates objects)
pg_restore -h localhost -p 5433 -U postgres -d open_navigator --clean --if-exists \
  "open-navigator-backups/releases/v1.5.0/open_navigator_v1.5.0_"*.dump

pg_restore -h localhost -p 5433 -U postgres -d openstates --clean --if-exists \
  "open-navigator-backups/releases/v1.5.0/openstates_v1.5.0_"*.dump
```

> **Restore only into a local/dev warehouse (`localhost:5433` or a dev Neon
> instance) — never into a production database.**

Every release is recorded in the [Release History](development/release-history.md),
which pairs each version with its backup location.

### Sharing a Snapshot So Others Can Boot Their Environment

The `make backup` / `make restore` flow above is the same one used to hand a working
warehouse to a **new collaborator** — they download your dump from Google Drive and
restore it locally instead of rebuilding every dbt model and re-running ingestion from
scratch.

#### 1. Back up the current database

You don't need a formal release to share a snapshot. Tag the snapshot with any label
(a date works well) and dump both databases:

```bash
# Versioned via the Makefile (writes into the Drive-synced backup folder):
make backup VERSION=snapshot-20260609

# …or a one-off manual dump of just the primary database:
PGPASSWORD=password pg_dump -h localhost -p 5433 -U postgres -Fc open_navigator \
  -f open_navigator_$(date +%Y%m%d).dump
```

> `-Fc` is Postgres' compressed custom format — it restores with `pg_restore` and is
> far smaller than plain SQL. Dump **both** `open_navigator` and `openstates` if the
> recipient needs the source data too.

#### 2. Publish to Google Drive

**If you use Google Drive for Desktop** (the WSL setup above), `make backup` already
wrote the dumps into `open-navigator-backups/`, which Drive syncs off-machine
automatically. To let *others* download them:

1. Open [drive.google.com](https://drive.google.com) → the `open-navigator-backups`
   folder.
2. Right-click the release/snapshot folder → **Share** → set "Anyone with the link →
   Viewer", and copy the link.

**Without Drive for Desktop**, upload the dump from any machine with
[`rclone`](https://rclone.org/drive/) (one-time `rclone config` to authorize Drive):

```bash
# Upload a single dump to a Drive folder named "open-navigator-backups"
rclone copy open_navigator_20260609.dump gdrive:open-navigator-backups/snapshot-20260609/
```

Then share that folder from the Drive web UI as above. Record the link (and the
matching git SHA/tag) in the [Release History](development/release-history.md) so the
data snapshot stays tied to the code that produced it.

#### 3. Bootstrap from a shared snapshot (the new collaborator's steps)

On a fresh machine, the recipient gets the warehouse running on `localhost:5433`,
checks out the matching code, **downloads** the dump, and restores it.

```bash
# a) Make sure local Postgres is up on :5433 and the databases exist.
#    (createdb is a no-op / harmless error if they already exist.)
PGPASSWORD=password createdb -h localhost -p 5433 -U postgres open_navigator 2>/dev/null || true
PGPASSWORD=password createdb -h localhost -p 5433 -U postgres openstates     2>/dev/null || true

# b) Check out the code that matches the snapshot (use the tag/SHA from the share notes).
git checkout v1.5.0   # or the SHA recorded with the snapshot

# c) Download the dump(s) from the shared Google Drive link:
#    • Browser: open the share link and click Download, OR
#    • CLI (no Drive login) with gdown using the file id from the share URL:
pip install gdown
gdown "https://drive.google.com/uc?id=<FILE_ID>" -O open_navigator.dump
#    • or, if they share via rclone, pull the whole folder:
#      rclone copy gdrive:open-navigator-backups/snapshot-20260609/ ./

# d) Restore into the LOCAL dev warehouse:
PGPASSWORD=password pg_restore -h localhost -p 5433 -U postgres -d open_navigator \
  --clean --if-exists open_navigator.dump
# (repeat for openstates.dump if provided)
```

If both collaborators share the **same** Drive folder through Drive for Desktop, the
recipient can skip the manual download entirely and just run
`make restore VERSION=snapshot-20260609` — the symlinked folder resolves to the
synced files.

> **Restore only into a local/dev warehouse (`localhost:5433` or a dev Neon
> instance) — never into a production database.**

## Next Steps

1. Configure your `.env` file with API keys
2. Run the example workflow: `make example`
3. Start the API server: `make run`
4. Check out the interactive docs: http://localhost:8000/docs
5. Generate a heatmap: `make heatmap`

For more details, see the main [README.md](README.md).
