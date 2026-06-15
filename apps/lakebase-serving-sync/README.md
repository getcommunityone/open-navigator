# lakebase-serving-sync (DAB)

A **Databricks-driven** serving pipeline. A scheduled Lakeflow Job runs entirely
on Databricks:

```
prod Neon Postgres ──(Spark JDBC)──▶ Unity Catalog Delta ──(synced tables)──▶ Lakebase Postgres
   (public serving)                  dbw_opennav_prod_eastus_001.open_navigator_serving.*            opennav_lakebase.public.*
```

This is the Databricks-native counterpart to the local Neon copy
(`hosting.neon.sync_public_to_neon`). Instead of pushing from the laptop, a
Databricks job *pulls* from prod Neon and the sync schedule lives on Databricks.

| Task | What it does |
|------|--------------|
| `ingest_neon_to_uc` | Reads the civic-serving `public` tables from **prod Neon** over Spark JDBC → writes UC Delta tables in `dbw_opennav_prod_eastus_001.open_navigator_serving`. |
| `sync_uc_to_lakebase` | Creates/refreshes a Lakebase **synced table** for each UC Delta table (`/api/2.0/postgres/synced_tables`). |

Table list + primary keys: [`src/serving_tables.py`](src/serving_tables.py) (PKs
verified against the `gold` marts). Three civic objects with no PK are listed in
`EXCLUDED_NO_PK` and skipped (synced tables require a key; we never invent one).

## Quick start

- **Step-by-step to run tomorrow:** [`RUNBOOK.md`](RUNBOOK.md)
- **One command for setup:** `./setup.sh` (creates project + secret scope, stores the Neon secret from `.env`, validates)
- **CLI templates:** [`templates/`](templates/) — `create-project.json`, `register-catalog.json`, `synced-table.example.json`

## One-time setup

All commands use the `opennav-prod` profile. (`./setup.sh` automates this.)

**1. Lakebase project** (skip if `opennav-serving` already exists — check with
`databricks postgres list-projects --profile opennav-prod`):

```bash
databricks postgres create-project opennav-serving \
  --json '{"spec": {"display_name": "Open Navigator serving"}}' \
  --profile opennav-prod
```

> Or reuse the existing `opennav-rag-chat` project by setting
> `--var lakebase_project_id=opennav-rag-chat` at deploy time.

**2. Neon connection secret** — the prod Neon libpq URL
(`postgresql://user:pass@host/db?sslmode=require`, i.e. `NEON_DATABASE_URL`):

```bash
databricks secrets create-scope open-navigator --profile opennav-prod   # once
databricks secrets put-secret open-navigator neon-prod-url --profile opennav-prod
# paste the prod Neon URL when prompted
```

The UC catalog registration (`opennav_lakebase`) and the serving schema/volume
are created automatically by the job — no manual step.

## Deploy & run

```bash
cd apps/lakebase-serving-sync

databricks bundle validate --strict --target dev --profile opennav-prod
databricks bundle deploy --target dev --profile opennav-prod

# Run once on demand (the schedule ships PAUSED — see below)
databricks bundle run serving_sync --target dev --profile opennav-prod
```

Deploy `--target prod` for the production job (real name, no `[dev …]` prefix).

## Schedule

Ships **PAUSED** (`schedule_pause` var) so deploying never silently starts
creating Lakebase pipelines (billable). Unpause when you're happy:

```bash
databricks bundle deploy --target prod --var schedule_pause=UNPAUSED --profile opennav-prod
```

Default cadence: daily 08:00 America/Chicago (`schedule_cron`).

## Configuration (override with `--var key=value`)

| Variable | Default | Notes |
|----------|---------|-------|
| `catalog` | `dbw_opennav_prod_eastus_001` | UC catalog for the Delta source + pipeline storage (regular catalog, NOT the Lakebase one). |
| `serving_schema` | `open_navigator_serving` | UC schema for the Delta source tables. |
| `lakebase_project_id` | `opennav-serving` | Lakebase Autoscaling project. |
| `lakebase_catalog` | `opennav_lakebase` | UC catalog the Lakebase DB is registered as. |
| `sync_schema` | `public` | Schema in Lakebase for the synced tables. |
| `sync_mode` | `SNAPSHOT` | `SNAPSHOT` \| `TRIGGERED` \| `CONTINUOUS`. Non-snapshot enables CDF on the UC source automatically. |
| `neon_secret_scope` / `neon_secret_key` | `open-navigator` / `neon-prod-url` | Where the prod Neon URL secret lives. |
| `schedule_cron` | `0 0 8 * * ?` | Quartz cron. |
| `schedule_pause` | `PAUSED` | Set `UNPAUSED` to enable the schedule. |

## Notes & limits

- **Sync mode:** `SNAPSHOT` (default) full-refreshes from the freshly-ingested
  UC Delta each run. `TRIGGERED`/`CONTINUOUS` use Change Data Feed (enabled on
  the UC source by the ingest task) for incremental refresh.
- **Compute:** **serverless** (no cluster block) — this trial subscription has
  no spare Azure VM quota in eastus (classic clusters failed with both
  `CLOUD_PROVIDER_RESOURCE_STOCKOUT` and `AZURE_QUOTA_EXCEEDED_EXCEPTION`).
  Serverless runs on Databricks-managed compute, consumes no subscription VM
  quota, and bundles the Postgres JDBC driver. The classic-cluster fallback (and
  its `node_type_id` / `spark_version` / `postgres_jdbc_coordinates` vars) is
  documented in the header of `resources/serving_sync.job.yml` for workspaces
  that have VM quota but no serverless.
- **`event_documents`** (transcript search, ~13.7 GB) is excluded — it has a
  dedicated slim loader on the Neon side. Add a dedicated UC ingest if Lakebase
  should serve transcript search.
- **App access:** a Databricks App reading these synced tables needs its service
  principal granted `SELECT` — see the lakebase skill's "Grant app SP access to
  synced tables".
