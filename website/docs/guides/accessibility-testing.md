---
sidebar_position: 12
displayed_sidebar: developersSidebar
---

# Accessibility testing (jurisdiction websites)

Bulk accessibility checks for canonical government homepages in **`intermediate.int_jurisdiction_websites`**. Results are stored in Postgres bronze tables for analysis, dashboards, and compliance reporting.

This guide covers **how to read these docs**, **what each engine does**, and **exact commands to run** from the repo root.

## How to read this documentation

### On the web (local)

1. From the repo root, start the documentation site:

   ```bash
   cd website && npm install && npm run start
   ```

2. Open the guide in your browser:

   - **Local dev:** [http://localhost:3000/docs/guides/accessibility-testing](http://localhost:3000/docs/guides/accessibility-testing)
   - If that 404s, try the site home at [http://localhost:3000](http://localhost:3000) and use the left nav: **Developers & Technical Users → How-To Guides → Accessibility testing**.

3. Production (when deployed): [https://www.communityone.com/docs/guides/accessibility-testing](https://www.communityone.com/docs/guides/accessibility-testing)

### In the repository

| Location | Contents |
|----------|----------|
| This page (`website/docs/guides/accessibility-testing.md`) | User-facing runbook |
| `scripts/accessibility/README.md` | Maintainer notes (env vars, file layout) |
| `scripts/accessibility/*.py`, `*.mjs`, `*.sh` | Implementations |

---

## What gets tested

| Layer | Source | Engines | Bronze table |
|-------|--------|---------|--------------|
| **HTML homepages** | One URL per `jurisdiction_id` from `int_jurisdiction_websites` | [axe-core](https://github.com/dequelabs/axe-core) + Puppeteer, [Pa11y-CI](https://github.com/pa11y/pa11y-ci) | `bronze.bronze_jurisdiction_website_accessibility` |
| **PDF documents** | `.pdf` links discovered on those homepages | [veraPDF](https://verapdf.org/) (PDF/UA, PDF/A) | `bronze.bronze_jurisdiction_pdf_verapdf` |

HTML tools check **WCAG-oriented** issues in the DOM. veraPDF checks **machine-verifiable** PDF/UA and PDF/A rules (industry standard for accessible PDFs).

---

## Prerequisites

1. **Postgres** with dbt intermediate built:

   ```bash
   ./scripts/dbt.sh run --select int_jurisdiction_websites
   ```

2. **Python** (repo `.venv`):

   ```bash
   pip install -r requirements.txt
   ```

3. **Database URL** in `.env` (first non-empty wins): `OPEN_NAVIGATOR_DATABASE_URL`, `NEON_DATABASE_URL_DEV`, or `NEON_DATABASE_URL`.

4. **HTML scans only — Node 18+:**

   ```bash
   cd scripts/accessibility && npm install
   npx puppeteer browsers install chrome
   ```

5. **PDF scans — Docker** (recommended; pulls `verapdf/cli` on first use):

   ```bash
   docker --version
   docker run --rm verapdf/cli:v1.30.1 -l   # list PDF/UA and PDF/A profiles
   ```

---

## Quick start (recommended)

Run everything from the **repository root** (`open-navigator/`).

### HTML: axe on one state

```bash
./scripts/accessibility/run_accessibility_scan.sh --engine axe --state AL
```

Exports URLs → scans with axe (default concurrency 5) → upserts `bronze.bronze_jurisdiction_website_accessibility`.

### HTML: Pa11y-CI with higher parallelism

```bash
PA11YCI_CONCURRENCY=8 WORKER_POOL_SIZE=6 \
  ./scripts/accessibility/run_accessibility_scan.sh --engine pa11y --state AL
```

### PDF: veraPDF on one state

```bash
./scripts/accessibility/run_verapdf_scan.sh --state AL --max-pdfs-per-site 3
```

Discovers PDFs on homepages → validates with PDF/UA profile `ua1` by default → upserts `bronze.bronze_jurisdiction_pdf_verapdf`.

---

## Step-by-step: HTML (axe or Pa11y)

### 1. Export homepage manifest

One canonical URL per `jurisdiction_id` (same source priority as jurisdiction discovery):

```bash
.venv/bin/python -m scripts.accessibility.export_urls --state AL \
  --out data/cache/accessibility/urls-al.json
```

**Sharding** for large batches (~20k sites):

```bash
.venv/bin/python -m scripts.accessibility.export_urls --limit 50 --offset 0 --batch-id shard-0
.venv/bin/python -m scripts.accessibility.export_urls --limit 50 --offset 50 --batch-id shard-1
```

### 2. Run a scanner

**axe-core + Puppeteer:**

```bash
cd scripts/accessibility
AXE_CONCURRENCY=10 node run_axe_scan.mjs \
  --urls ../../data/cache/accessibility/urls-al.json
```

**Pa11y-CI (worker pool):**

```bash
cd scripts/accessibility
PA11YCI_CONCURRENCY=8 WORKER_POOL_SIZE=6 WORKER_CHUNK_SIZE=25 \
  node run_pa11y_workers.mjs --urls ../../data/cache/accessibility/urls-al.json
```

### 3. Persist to Postgres

```bash
.venv/bin/python -m scripts.accessibility.persist_results --ensure-ddl \
  --scanner axe --input data/cache/accessibility/axe-<batch-id>.ndjson

.venv/bin/python -m scripts.accessibility.persist_results --ensure-ddl \
  --scanner pa11y --input data/cache/accessibility/pa11y-<batch-id>/pa11y-results-merged.json
```

### 4. Query HTML results

```sql
SELECT jurisdiction_id, website_url, scanner, violation_count, status, scanned_at
FROM bronze.bronze_jurisdiction_website_accessibility
WHERE batch_id = '20260515T120000Z'
ORDER BY violation_count DESC NULLS LAST
LIMIT 50;
```

**DDL (Neon):**

```bash
psql "$OPEN_NAVIGATOR_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f scripts/deployment/neon/migrations/032_create_bronze_jurisdiction_website_accessibility.sql
```

---

## Step-by-step: PDF (veraPDF)

### 1. Discover PDF links on homepages

```bash
.venv/bin/python -m scripts.accessibility.export_pdf_urls --state AL \
  --out data/cache/accessibility/pdf-urls-al.json \
  --max-pdfs-per-site 3
```

Use `--from-manifest path.json` to skip crawling if you already have a PDF URL list.

### 2. Download and validate

**Default (Docker wraps veraPDF):**

```bash
.venv/bin/python -m scripts.accessibility.run_verapdf_scan \
  --manifest data/cache/accessibility/pdf-urls-al.json
```

**Multiple profiles** (e.g. PDF/UA-1 and PDF/UA-2):

```bash
VERAPDF_FLAVOURS=ua1,ua2 .venv/bin/python -m scripts.accessibility.run_verapdf_scan \
  --manifest data/cache/accessibility/pdf-urls-al.json
```

**Local veraPDF binary** (no Docker):

```bash
VERAPDF_USE_DOCKER=false VERAPDF_BIN=verapdf \
  .venv/bin/python -m scripts.accessibility.run_verapdf_scan \
  --manifest data/cache/accessibility/pdf-urls-al.json
```

### 3. Persist PDF results

```bash
.venv/bin/python -m scripts.accessibility.persist_verapdf_results --ensure-ddl \
  --input data/cache/accessibility/verapdf-<batch-id>.ndjson
```

### 4. Query PDF results

```sql
SELECT jurisdiction_id, pdf_url, profile_flavour, is_compliant,
       failed_rules, failed_checks, status
FROM bronze.bronze_jurisdiction_pdf_verapdf
WHERE batch_id = '20260515T120000Z'
ORDER BY failed_checks DESC NULLS LAST
LIMIT 50;
```

**DDL (Neon):**

```bash
psql "$OPEN_NAVIGATOR_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f scripts/deployment/neon/migrations/033_create_bronze_jurisdiction_pdf_verapdf.sql
```

### Docker worker (batch / Lambda-style)

```bash
docker build -f scripts/accessibility/docker/Dockerfile.verapdf-worker \
  -t open-navigator/verapdf-worker .

docker compose -f docker-compose.verapdf.example.yml run --rm verapdf-worker \
  --state AL --limit 50
```

Inside the image, `VERAPDF_USE_DOCKER=false` — the `verapdf` CLI is already on `PATH`.

---

## Scale (~20,000 jurisdictions)

| Approach | When to use |
|----------|-------------|
| Raise concurrency (`AXE_CONCURRENCY`, `PA11YCI_CONCURRENCY`, `WORKER_POOL_SIZE`) | Single powerful machine |
| `--limit` / `--offset` shards | Multiple machines or cron jobs |
| `scripts/accessibility/lambda_handler.py` | AWS Lambda + Step Functions |

**Lambda event examples:**

```json
{ "engine": "axe", "state": "AL", "offset": 0, "limit": 50, "batch_id": "shard-0", "persist": true }
```

```json
{ "engine": "verapdf", "offset": 0, "limit": 30, "batch_id": "pdf-shard-0", "persist": true }
```

Use a **container image** with Chromium for HTML engines, or `Dockerfile.verapdf-worker` for PDF. Target **10–50 URLs per invocation** so a full national batch finishes in minutes when fan-out across hundreds of functions.

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPEN_NAVIGATOR_DATABASE_URL` | — | Postgres for export + persist |
| `AXE_CONCURRENCY` | `5` | Parallel Puppeteer tabs (axe) |
| `PA11YCI_CONCURRENCY` | `5` | URLs per Pa11y-CI process |
| `WORKER_POOL_SIZE` | `4` | Parallel Pa11y-CI child processes |
| `WORKER_CHUNK_SIZE` | `25` | URLs per Pa11y child |
| `PA11Y_STANDARD` | `WCAG2AA` | Pa11y standard |
| `VERAPDF_USE_DOCKER` | `true` | Run `docker run verapdf/cli …` |
| `VERAPDF_FLAVOURS` | `ua1` | e.g. `ua1`, `ua2`, `1b`, `2b` |
| `VERAPDF_WORKERS` | `4` | Parallel PDF download + validate |
| `VERAPDF_MAX_BYTES` | `15728640` | Skip PDFs over 15 MiB |
| `ACCESSIBILITY_USER_AGENT` | Open Navigator bot | HTTP User-Agent |

---

## Troubleshooting

| Symptom | What to try |
|---------|-------------|
| Empty export | Run `dbt run --select int_jurisdiction_websites`; confirm rows in `intermediate.int_jurisdiction_websites` |
| Chromium fails on WSL | `npx puppeteer browsers install chrome`; see meetings Playwright notes in discovery docs |
| veraPDF “not available” | Install Docker or set `VERAPDF_USE_DOCKER=false` with local `verapdf` on PATH |
| Many `download_failed` PDFs | Site blocks bots; increase timeout; check `ACCESSIBILITY_USER_AGENT` |
| Timeouts on large states | Use `--limit` and shard with `--offset` |

---

## Related documentation

- [Jurisdiction discovery](/docs/data-sources/jurisdiction-discovery) — how homepage URLs enter the warehouse
- [dbt quick reference](/docs/dbt/quick-reference) — rebuilding `int_jurisdiction_websites`
- [Quick start](/docs/quickstart) — general repo setup
