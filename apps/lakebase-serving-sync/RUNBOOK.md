# RUNBOOK — run tomorrow

Everything to stand up the **lakebase-serving-sync** job: prod Neon → UC Delta →
Lakebase synced tables. All commands use the `opennav-prod` profile. Run from
the repo, or `cd apps/lakebase-serving-sync` where noted.

Templates referenced below live in [`templates/`](templates/).

---

## TL;DR (fast path)

```bash
# 1. One-time setup: Lakebase project + secret scope + Neon secret + validate
apps/lakebase-serving-sync/setup.sh
#    (to reuse the existing project instead of a new one:)
# PROJECT_ID=opennav-rag-chat apps/lakebase-serving-sync/setup.sh

# 2. Deploy + run once (schedule stays PAUSED)
cd apps/lakebase-serving-sync
databricks bundle deploy --target dev --profile opennav-prod
databricks bundle run serving_sync --target dev --profile opennav-prod
```

Then verify (Step 5) and, when happy, unpause the schedule (Step 6).

---

## Step 0 — preflight

```bash
databricks auth describe --profile opennav-prod     # confirm you're logged in
databricks postgres list-projects --profile opennav-prod -o json
```

If the token is stale: `databricks auth login --profile opennav-prod`.

## Step 1 — Lakebase project

Either let `setup.sh` do it, or manually:

```bash
databricks postgres create-project opennav-serving \
  --json @apps/lakebase-serving-sync/templates/create-project.json \
  --profile opennav-prod
```

**Reuse the existing project instead?** Skip this and pass
`--var lakebase_project_id=opennav-rag-chat` on every `deploy`/`run` below.

Verify:

```bash
databricks postgres list-branches projects/opennav-serving --profile opennav-prod
```

## Step 2 — Neon secret

The job reads the prod Neon URL from a Databricks secret (no creds in the bundle).

```bash
databricks secrets create-scope open-navigator --profile opennav-prod   # once

# from the repo .env (NEON_DATABASE_URL) — strip surrounding quotes, or the
# stored value breaks URL parsing in the job:
NEON_URL="$(grep -E '^NEON_DATABASE_URL=' .env | head -1 | cut -d= -f2- | sed -E 's/^["'"'"']//; s/["'"'"']$//')"
databricks secrets put-secret open-navigator neon-prod-url \
  --string-value "$NEON_URL" --profile opennav-prod
```

Verify the key exists:

```bash
databricks secrets list-secrets open-navigator --profile opennav-prod
```

## Step 3 — validate

```bash
cd apps/lakebase-serving-sync
databricks bundle validate --strict --target dev --profile opennav-prod
```

## Step 4 — deploy + run once

```bash
# still in apps/lakebase-serving-sync
databricks bundle deploy --target dev --profile opennav-prod
databricks bundle run serving_sync --target dev --profile opennav-prod
```

`run` blocks and streams task output. First run will: create the
`dbw_opennav_prod_eastus_001.open_navigator_serving` schema + Delta tables, register the
`opennav_lakebase` UC catalog, and create one synced table per row in
`src/serving_tables.py` (SNAPSHOT).

## Step 5 — verify

```bash
# UC Delta source tables landed
databricks tables list dbw_opennav_prod_eastus_001 open_navigator_serving --profile opennav-prod

# A synced table is online
databricks postgres get-synced-table \
  "synced_tables/opennav_lakebase.public.jurisdictions" --profile opennav-prod

# Query Lakebase directly (opens psql; needs the project)
databricks postgres psql --project opennav-serving --profile opennav-prod \
  -- -c "SELECT count(*) FROM public.jurisdictions;"
```

## Step 6 — enable the schedule (when you're happy)

It ships **PAUSED** so nothing recurs by accident. Turn it on:

```bash
# production deploy with the schedule unpaused (daily 08:00 America/Chicago)
databricks bundle deploy --target prod --var schedule_pause=UNPAUSED --profile opennav-prod
```

---

## Handy overrides

```bash
# reuse existing Lakebase project
--var lakebase_project_id=opennav-rag-chat

# incremental sync instead of full snapshot (auto-enables CDF on the UC source)
--var sync_mode=TRIGGERED

# different cron
--var schedule_cron='0 0 */6 * * ?'
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `permission denied` / project not found | Project doesn't exist or wrong `lakebase_project_id`. Re-check Step 1. |
| `CLOUD_PROVIDER_RESOURCE_STOCKOUT` / `SkuNotAvailable` | Azure VM capacity stockout. The job runs on **serverless** to avoid this. If you switched to a classic cluster, change the SKU (`Standard_D4ds_v5` / `Standard_D4ads_v5`) or try another region/zone. |
| ingest task: `No suitable driver` (serverless) | Serverless DBR should include the Postgres driver; if it doesn't, fall back to a classic cluster + Maven `org.postgresql:postgresql:42.7.4` (see README → Notes). |
| ingest task: connection refused/timeout to Neon | Secret missing/wrong, or Neon URL lacks `sslmode=require`. Re-do Step 2. |
| `storage_catalog` pipeline error | `new_pipeline_spec.storage_catalog` must be a regular UC catalog (we use `dbw_opennav_prod_eastus_001`), never the Lakebase catalog. |
| `NO_SUCH_CATALOG_EXCEPTION` Catalog not found | The `catalog` var must be a real UC catalog in the workspace. List with `databricks catalogs list`; this workspace's writable one is `dbw_opennav_prod_eastus_001`. |
| synced table create says "already exists" | Expected on re-runs — the job refreshes it. |
| App can't read synced tables | Grant the app SP `SELECT` (see README → App access). |

Tear down a synced table (Postgres table remains; drop it separately):

```bash
databricks postgres delete-synced-table \
  "synced_tables/opennav_lakebase.public.<table>" --profile opennav-prod
```
