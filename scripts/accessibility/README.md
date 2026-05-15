# Jurisdiction website accessibility scans

Bulk WCAG testing for canonical homepages in **`intermediate.int_jurisdiction_websites`** (dbt: `dbt run --select int_jurisdiction_websites`). Results land in **`bronze.bronze_jurisdiction_website_accessibility`**.

Three engines:

| Engine | Tooling | Best for |
|--------|---------|----------|
| **axe** | `@axe-core/puppeteer` | Rich violation JSON, custom rules, full control |
| **pa11y** | **Pa11y-CI** + worker pool | HTML_CodeSniffer / axe rules via Pa11y, high concurrency |
| **verapdf** | [veraPDF](https://verapdf.org/) CLI / Docker | Machine-verifiable **PDF/UA** and **PDF/A** on jurisdiction PDFs |

## Prerequisites

- Postgres with `intermediate.int_jurisdiction_websites` built
- Python deps: `pip install -r requirements.txt`
- Node 18+ in `scripts/accessibility/`:

```bash
cd scripts/accessibility && npm install
npx puppeteer browsers install chrome   # axe / Pa11y need Chromium
```

## Quick start (one state)

```bash
./scripts/accessibility/run_accessibility_scan.sh --engine axe --state AL
```

This exports URLs → runs axe with default concurrency 5 → upserts bronze rows.

## Step-by-step

### 1. Export URL manifest (one row per `jurisdiction_id`)

```bash
.venv/bin/python -m scripts.accessibility.export_urls --state AL \
  --out data/cache/accessibility/urls-al.json
```

Sharding for large batches (Lambda / parallel hosts):

```bash
.venv/bin/python -m scripts.accessibility.export_urls --limit 50 --offset 0 --batch-id shard-0
.venv/bin/python -m scripts.accessibility.export_urls --limit 50 --offset 50 --batch-id shard-1
```

### 2a. axe-core + Puppeteer

```bash
cd scripts/accessibility
AXE_CONCURRENCY=10 node run_axe_scan.mjs \
  --urls ../../data/cache/accessibility/urls-al.json
```

### 2b. Pa11y-CI (parallel chunks)

```bash
cd scripts/accessibility
PA11YCI_CONCURRENCY=8 WORKER_POOL_SIZE=6 WORKER_CHUNK_SIZE=25 \
  node run_pa11y_workers.mjs --urls ../../data/cache/accessibility/urls-al.json
```

### 3. Persist to Postgres

```bash
.venv/bin/python -m scripts.accessibility.persist_results --ensure-ddl \
  --scanner axe --input data/cache/accessibility/axe-<batch>.ndjson

.venv/bin/python -m scripts.accessibility.persist_results --ensure-ddl \
  --scanner pa11y --input data/cache/accessibility/pa11y-<batch>/pa11y-results-merged.json
```

Apply DDL on Neon without Python:

```bash
psql "$OPEN_NAVIGATOR_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f scripts/deployment/neon/migrations/032_create_bronze_jurisdiction_website_accessibility.sql
```

## Scale (~20k sites)

- **Local**: raise `AXE_CONCURRENCY` or `PA11YCI_CONCURRENCY` + `WORKER_POOL_SIZE`; export in shards (`--limit` / `--offset`).
- **Lambda**: use `scripts/accessibility/lambda_handler.py` — fan out Step Functions with `{ "offset": N, "limit": 50, "engine": "axe" }` per invocation. Use a **container image** with Chromium; 10–50 URLs per function finishes the full batch in minutes.
- **Worker pool**: `run_pa11y_workers.mjs` already spawns multiple `pa11y-ci` child processes; axe uses an in-process concurrency pool.

## Query results

```sql
SELECT jurisdiction_id, website_url, scanner, violation_count, status, scanned_at
FROM bronze.bronze_jurisdiction_website_accessibility
WHERE batch_id = '20260515T120000Z'
ORDER BY violation_count DESC
LIMIT 50;
```

## veraPDF (PDF/UA + PDF/A)

Open-source CLI validator for **machine-verifiable** PDF accessibility. Discovers `.pdf` links on each jurisdiction homepage from `int_jurisdiction_websites`, downloads them, and validates with profiles such as **`ua1`** (PDF/UA-1) or **`1b`** (PDF/A-1b).

### Prerequisites

- **Docker** (recommended): pulls `verapdf/cli` on first run, or use the bundled worker image.
- List profiles: `docker run --rm verapdf/cli:v1.30.1 -l`

### Quick start

```bash
./scripts/accessibility/run_verapdf_scan.sh --state AL --max-pdfs-per-site 3
```

Or step-by-step:

```bash
# 1. Crawl homepages for PDF links
.venv/bin/python -m scripts.accessibility.export_pdf_urls --state AL \
  --out data/cache/accessibility/pdf-urls-al.json

# 2. Validate (Docker wraps veraPDF by default)
VERAPDF_FLAVOURS=ua1 docker run --rm \
  -v "$(pwd)/data:/app/data" -v /var/run/docker.sock:/var/run/docker.sock \
  -e VERAPDF_USE_DOCKER=true \
  open-navigator/verapdf-worker  # see docker-compose below

# Local (veraPDF installed on host):
VERAPDF_USE_DOCKER=false VERAPDF_BIN=verapdf \
  .venv/bin/python -m scripts.accessibility.run_verapdf_scan \
  --manifest data/cache/accessibility/pdf-urls-al.json

# 3. Persist
.venv/bin/python -m scripts.accessibility.persist_verapdf_results --ensure-ddl \
  --input data/cache/accessibility/verapdf-<batch>.ndjson
```

### Docker worker (Lambda-friendly)

```bash
docker build -f scripts/accessibility/docker/Dockerfile.verapdf-worker -t open-navigator/verapdf-worker .
docker compose -f docker-compose.verapdf.example.yml run --rm verapdf-worker --state AL --limit 50
```

Inside the image, `VERAPDF_USE_DOCKER=false` — the `verapdf` binary is already on `PATH`.

### Lambda / scale

Same sharding as HTML scans: `{ "engine": "verapdf", "offset": 0, "limit": 30 }` via `lambda_handler.py`. Use a **container image** based on `Dockerfile.verapdf-worker` (Java + veraPDF, no nested Chromium).

### Query PDF results

```sql
SELECT jurisdiction_id, pdf_url, profile_flavour, is_compliant,
       failed_rules, failed_checks, status
FROM bronze.bronze_jurisdiction_pdf_verapdf
WHERE batch_id = '20260515T120000Z'
ORDER BY failed_checks DESC NULLS LAST
LIMIT 50;
```

DDL: `scripts/deployment/neon/migrations/033_create_bronze_jurisdiction_pdf_verapdf.sql`

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPEN_NAVIGATOR_DATABASE_URL` | (Neon/local) | Postgres for export + persist |
| `AXE_CONCURRENCY` | `5` | Parallel Puppeteer pages |
| `PA11YCI_CONCURRENCY` | `5` | URLs per Pa11y-CI process |
| `WORKER_POOL_SIZE` | `4` | Parallel Pa11y-CI child processes |
| `WORKER_CHUNK_SIZE` | `25` | URLs per child |
| `PA11Y_STANDARD` | `WCAG2AA` | Pa11y standard |
| `ACCESSIBILITY_USER_AGENT` | Open Navigator bot | Request header |
| `VERAPDF_USE_DOCKER` | `true` | Run `docker run verapdf/cli …` |
| `VERAPDF_DOCKER_IMAGE` | `verapdf/cli:v1.30.1` | CLI image |
| `VERAPDF_FLAVOURS` | `ua1` | Comma-separated: `ua1`, `ua2`, `1b`, `2b`, … |
| `VERAPDF_WORKERS` | `4` | Parallel download + validate threads |
| `VERAPDF_MAX_BYTES` | `15728640` | Skip PDFs larger than 15 MiB |
| `PDF_DISCOVER_*` | — | Homepage crawl timeouts / concurrency |
