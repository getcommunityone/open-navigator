# Jurisdiction website accessibility scans

**User guide (Docusaurus):** [Accessibility testing](https://www.communityone.com/docs/guides/accessibility-testing) — or local `cd website && npm run start` → `/docs/guides/accessibility-testing`.

Bulk WCAG testing for canonical homepages in **`intermediate.int_jurisdiction_websites`** (dbt: `dbt run --select int_jurisdiction_websites`). HTML scanners land in **`bronze.bronze_jurisdiction_website_accessibility`** (axe/Pa11y); **Lighthouse** lands in **`bronze.bronze_jurisdiction_website_lighthouse`**; join both on `(batch_id, jurisdiction_id, website_url)` via **`public.v_jurisdiction_audits_axe_lighthouse`**.

Engines:

| Engine | Tooling | Best for |
|--------|---------|----------|
| **axe** | `@axe-core/puppeteer` | Rich axe violation JSON, custom rules |
| **pa11y** | **Pa11y-CI** + worker pool | High concurrency HTML_CodeSniffer-style runs |
| **lighthouse** | **Lighthouse** + `chrome-launcher` | Accessibility / perf / best-practices scores + full Lighthouse report JSON (`lhr`) |
| **verapdf** | [veraPDF](https://verapdf.org/) CLI / Docker | Machine-verifiable **PDF/UA** and **PDF/A** on jurisdiction PDFs |

## Prerequisites

- Postgres with `intermediate.int_jurisdiction_websites` built
- Python deps: `pip install -r requirements.txt`
- Node 18+ in `packages/accessibility/src/accessibility/`:

```bash
cd packages/accessibility/src/accessibility && npm install
npx puppeteer browsers install chrome   # axe / Pa11y need Chromium
```

## Quick start (one state)

```bash
./packages/accessibility/src/accessibility/run_accessibility_scan.sh --engine axe --state AL
```

This exports URLs → runs axe with default concurrency 5 → upserts bronze rows.

## Step-by-step

### 1. Export URL manifest (one row per `jurisdiction_id`)

```bash
.venv/bin/python -m accessibility.export_urls --state AL \
  --out data/cache/accessibility/urls-al.json
```

Sharding for large batches (Lambda / parallel hosts):

```bash
.venv/bin/python -m accessibility.export_urls --limit 50 --offset 0 --batch-id shard-0
.venv/bin/python -m accessibility.export_urls --limit 50 --offset 50 --batch-id shard-1
```

### 2a. axe-core + Puppeteer

```bash
cd packages/accessibility/src/accessibility
AXE_CONCURRENCY=10 node run_axe_scan.mjs \
  --urls ../../data/cache/accessibility/urls-al.json
```

### 2b. Pa11y-CI (parallel chunks)

```bash
cd packages/accessibility/src/accessibility
PA11YCI_CONCURRENCY=8 WORKER_POOL_SIZE=6 WORKER_CHUNK_SIZE=25 \
  node run_pa11y_workers.mjs --urls ../../data/cache/accessibility/urls-al.json
```

### 2c. Lighthouse (Chrome Launcher)

Runs **sequentially on one Chrome** per process (heavy). Scale with **Export sharding** + Lambda / parallel hosts. Use the **same `--batch-id` / urls manifest** as axe so Postgres can join audits.

From the **repository root**:

```bash
cd packages/accessibility/src/accessibility
# Optional: LIGHTHOUSE_CATEGORIES=accessibility,performance,best-practices
node run_lighthouse_scan.mjs --urls ../../data/cache/accessibility/urls-al.json
```

### 3. Persist to Postgres

```bash
.venv/bin/python -m accessibility.persist_results --ensure-ddl \
  --scanner axe --input data/cache/accessibility/axe-<batch>.ndjson

.venv/bin/python -m accessibility.persist_results --ensure-ddl \
  --scanner pa11y --input data/cache/accessibility/pa11y-<batch>/pa11y-results-merged.json

.venv/bin/python -m accessibility.persist_lighthouse_results --ensure-ddl \
  --input data/cache/accessibility/lighthouse-<batch>.ndjson
```

Apply DDL on Neon without Python:

```bash
psql "$OPEN_NAVIGATOR_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f packages/hosting/scripts/neon/migrations/032_create_bronze_jurisdiction_website_accessibility.sql

psql "$OPEN_NAVIGATOR_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f packages/hosting/scripts/neon/migrations/034_create_bronze_jurisdiction_website_lighthouse.sql
```

### 4. Query merged axe + Lighthouse (same `batch_id`)

```sql
SELECT jurisdiction_id,
       axe_violation_count,
       lighthouse_accessibility_score,
       lighthouse_performance_score,
       axe_final_url,
       lighthouse_final_url
FROM public.v_jurisdiction_audits_axe_lighthouse
WHERE batch_id = '20260515T120000Z'
ORDER BY axe_violation_count DESC NULLS LAST
LIMIT 50;
```

## Scale (~20k sites)

- **Local**: raise `AXE_CONCURRENCY` or `PA11YCI_CONCURRENCY` + `WORKER_POOL_SIZE`; export in shards (`--limit` / `--offset`).
- **Lambda**: use `packages/accessibility/src/accessibility/lambda_handler.py` — fan out Step Functions with `{ "offset": N, "limit": 50, "engine": "axe" }` per invocation. Use a **container image** with Chromium; 10–50 URLs per function finishes the full batch in minutes.
- **Worker pool**: `run_pa11y_workers.mjs` already spawns multiple `pa11y-ci` child processes; axe uses an in-process concurrency pool.
- **Lighthouse**: one Chrome instance per runner, **sequential** URL audits (`run_lighthouse_scan.mjs`). Scale horizontally with **`export_urls` shards** + `{ "engine": "lighthouse" }` in `lambda_handler.py`. Run **after** axe on the same manifest if you want fewer wasted Lighthouse runs on dead URLs (or run both in parallel shards if rate limits allow).

## Query results

**Axe / Pa11y** (per-row `scanner`):

```sql
SELECT jurisdiction_id, website_url, scanner, violation_count, status, scanned_at
FROM bronze.bronze_jurisdiction_website_accessibility
WHERE batch_id = '20260515T120000Z'
ORDER BY violation_count DESC
LIMIT 50;
```

**Lighthouse** (bronze table):

```sql
SELECT jurisdiction_id, website_url, score_accessibility, score_performance, status
FROM bronze.bronze_jurisdiction_website_lighthouse
WHERE batch_id = '20260515T120000Z'
ORDER BY score_accessibility ASC NULLS LAST
LIMIT 50;
```

**Merged axe + Lighthouse** — use **section 4** SQL (`public.v_jurisdiction_audits_axe_lighthouse`) when both audits share `batch_id`.

## OSS reference — reuse without adopting a foreign stack

Use other projects for **patterns and optional components**, not as plug-in replacements. Check **each repository’s LICENSE** before copying code.

### Crawler (URL discovery)

- **[A11yWatch Lite](https://github.com/a11ywatch/a11ywatch)** ships a Rust **crawler** (see their `docker-compose` and linked **crawler** repo) that is useful **inspiration** or a **standalone sidecar** if you need fast multi-page discovery.
- **Open Navigator** today uses **canonical homepages** from `intermediate.int_jurisdiction_websites` via `export_urls`. Dropping in their crawler still means **your own manifest format**, auth, and rate limits—plan integration work, not a one-line swap.

### Pagemind / Chrome (flaky pages, CDP)

- Their **pagemind** / **chrome** services illustrate **timeouts, waits, and headless browser** tuning under Docker.
- This repo’s first line of defense is **env-tunable** Puppeteer (axe) and Pa11y defaults—see **Environment** (`AXE_NAV_TIMEOUT_MS`, **`AXE_NAV_RETRIES`**, **`AXE_RETRY_BACKOFF_MS`**, `PA11Y_TIMEOUT_MS`, `PA11Y_WAIT_MS`, `AXE_HEADLESS`). Wait-for-selector and custom CDP tuning can be added incrementally.

### “Database” / aggregation

- A11yWatch Lite’s compose targets **MongoDB** for the product API, not a portable **Postgres star schema** for axe violations.
- Sensible alignment here: keep **`bronze.bronze_jurisdiction_website_accessibility`** (row per scan + **`results` JSONB**), then add **dbt** (or SQL views) to explode violations into **rule-level facts** for dashboards—same *idea* as commercial UIs, **your** warehouse shape.

## veraPDF (PDF/UA + PDF/A)

Open-source CLI validator for **machine-verifiable** PDF accessibility. Discovers `.pdf` links on each jurisdiction homepage from `int_jurisdiction_websites`, downloads them, and validates with profiles such as **`ua1`** (PDF/UA-1) or **`1b`** (PDF/A-1b).

### Prerequisites

- **Docker** (recommended): pulls `verapdf/cli` on first run, or use the bundled worker image.
- List profiles: `docker run --rm verapdf/cli:v1.30.1 -l`

### Quick start

```bash
./packages/accessibility/src/accessibility/run_verapdf_scan.sh --state AL --max-pdfs-per-site 3
```

Or step-by-step:

```bash
# 1. Crawl homepages for PDF links
.venv/bin/python -m accessibility.export_pdf_urls --state AL \
  --out data/cache/accessibility/pdf-urls-al.json

# 2. Validate (Docker wraps veraPDF by default)
VERAPDF_FLAVOURS=ua1 docker run --rm \
  -v "$(pwd)/data:/app/data" -v /var/run/docker.sock:/var/run/docker.sock \
  -e VERAPDF_USE_DOCKER=true \
  open-navigator/verapdf-worker  # see docker-compose below

# Local (veraPDF installed on host):
VERAPDF_USE_DOCKER=false VERAPDF_BIN=verapdf \
  .venv/bin/python -m accessibility.run_verapdf_scan \
  --manifest data/cache/accessibility/pdf-urls-al.json

# 3. Persist
.venv/bin/python -m accessibility.persist_verapdf_results --ensure-ddl \
  --input data/cache/accessibility/verapdf-<batch>.ndjson
```

### Docker worker (Lambda-friendly)

```bash
docker build -f packages/accessibility/src/accessibility/docker/Dockerfile.verapdf-worker -t open-navigator/verapdf-worker .
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

DDL: `packages/hosting/scripts/neon/migrations/033_create_bronze_jurisdiction_pdf_verapdf.sql`

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPEN_NAVIGATOR_DATABASE_URL` | (Neon/local) | Postgres for export + persist |
| `AXE_CONCURRENCY` | `5` | Parallel Puppeteer pages |
| `AXE_NAV_TIMEOUT_MS` | `45000` | Puppeteer `page.goto` timeout (`run_axe_scan.mjs`); raise for slow sites |
| `AXE_NAV_RETRIES` | `3` | Re-open page and retry on navigation / axe failures |
| `AXE_RETRY_BACKOFF_MS` | `2500` | Linear backoff between attempts (`backoff × attempt`) |
| `AXE_HEADLESS` | `true` | Set `false` locally to debug flaky pages (non-headful) |
| `PA11YCI_CONCURRENCY` | `5` | URLs per Pa11y-CI process |
| `PA11YCI_THRESHOLD` | `9007199254740991` (max safe integer) | Pa11y-CI exits **2** if total issues ≥ threshold; raise for scans, use `0` for strict CI |
| `WORKER_POOL_SIZE` | `4` | Parallel Pa11y-CI child processes |
| `WORKER_CHUNK_SIZE` | `25` | URLs per child |
| `PA11Y_STANDARD` | `WCAG2AA` | Pa11y standard |
| `PA11Y_TIMEOUT_MS` | `60000` | Per-page Pa11y timeout (`pa11yci.config.cjs`) |
| `PA11Y_WAIT_MS` | `1000` | Wait after load before audit (`pa11yci.config.cjs`) |
| `LIGHTHOUSE_CATEGORIES` | `accessibility,performance,best-practices` | Comma list for Lighthouse `onlyCategories` |
| `LIGHTHOUSE_LOG_LEVEL` | `error` | Lighthouse log level |
| `LIGHTHOUSE_CHROME_FLAGS` | (headless + sandbox-safe defaults) | Space-separated Chrome flags |
| `LIGHTHOUSE_CHROME_PATH` | Puppeteer’s Chromium | `chrome-launcher` binary |
| `LIGHTHOUSE_CHROME_RESTART_EVERY` | `0` | Restart Chrome every N URLs (`0` = never) |
| `LIGHTHOUSE_NAV_RETRIES` | (uses `AXE_NAV_RETRIES`) | Retries per URL if Lighthouse run throws (same backoff as axe unless overridden) |
| `LIGHTHOUSE_RETRY_BACKOFF_MS` | (uses `AXE_RETRY_BACKOFF_MS`) | Linear backoff between Lighthouse attempts |
| `LIGHTHOUSE_MAX_WAIT_FOR_LOAD_MS` | (uses `AXE_NAV_TIMEOUT_MS` or `60000`) | Lighthouse **`maxWaitForLoad`** (page load cap) |
| `ACCESSIBILITY_USER_AGENT` | Open Navigator bot | Request header |
| `VERAPDF_USE_DOCKER` | `true` | Run `docker run verapdf/cli …` |
| `VERAPDF_DOCKER_IMAGE` | `verapdf/cli:v1.30.1` | CLI image |
| `VERAPDF_FLAVOURS` | `ua1` | Comma-separated: `ua1`, `ua2`, `1b`, `2b`, … |
| `VERAPDF_WORKERS` | `4` | Parallel download + validate threads |
| `VERAPDF_MAX_BYTES` | `15728640` | Skip PDFs larger than 15 MiB |
| `PDF_DISCOVER_*` | — | Homepage crawl timeouts / concurrency |
