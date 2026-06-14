# RAG Chat App — from-scratch setup runbook

Stand up the DevHub **RAG Chat App** (streaming RAG over Lakebase pgvector + Model
Serving) on the trial Azure Databricks workspace, end to end. For *why* each step
exists and the gotchas behind them, see
[`../../templates/LESSONS-LEARNED-databricks-rag.md`](../../templates/LESSONS-LEARNED-databricks-rag.md).

## TL;DR

```bash
cd apps/rag-chat-app

# one-time, interactive (opens a browser):
databricks auth login \
  --host https://adb-7405608833986267.7.azuredatabricks.net \
  --profile opennav-prod

# everything else (idempotent):
./setup.sh
```

`setup.sh` installs the CLI + skills if missing, checks auth, capability-checks the
workspace, creates the Lakebase project, writes `.env`, `npm install`s, deploys, and
prints the corpus row count + app URL.

## Prerequisites (already provisioned)

- **Azure**: subscription `opennav-prod`, Databricks workspace
  `dbw-opennav-prod-eastus-001` (`adb-7405608833986267.7.azuredatabricks.net`).
  See [`infra/azure`](../../infra/azure) for the subscription/budget IaC.
- **Local**: `node` v22+, `npm`, `python3`, `curl`, and (optional) `psql` for the
  corpus check. No `sudo` needed — the CLI installs rootless into `~/.local/bin`.

## What gets created

| Resource | Name | Notes |
| --- | --- | --- |
| Databricks CLI | `~/.local/bin/databricks` v1.3.0 | rootless |
| Agent skills | `~/.claude/skills/databricks-*` | `databricks aitools install` |
| Lakebase project | `opennav-rag-chat` | autoscaling, scale-to-zero |
| Genie space | `NYC Taxi Analytics` | AI/BI Genie over `samples.nyctaxi.trips` |
| Databricks App | `rag-chat-app` | serverless hosting (two features, see below) |
| Local `.env` | `apps/rag-chat-app/.env` | gitignored, profile-auth (no secrets) |

## Two features in one app

- **RAG Chat** (`/`) — streaming retrieval-augmented chat over the Lakebase pgvector corpus.
- **NYC Taxi Analytics** (`/analytics`) — AI/BI **Genie** conversational analytics. Ask
  plain-English questions; Genie writes + runs SQL against `samples.nyctaxi.trips` (a
  Databricks sample table). The page shows the catalog/schema/table + columns so the
  underlying data source is always clear. Genie space id lives in `databricks.yml`
  (`genie_space_id`) and `.env` (`DATABRICKS_GENIE_SPACE_ID`); `setup.sh` creates the
  space if missing. Requires `user_api_scopes: [dashboards.genie]` (already declared).

## Config knobs (env vars for `setup.sh`)

| Var | Default | Purpose |
| --- | --- | --- |
| `CHAT_ENDPOINT` | `databricks-gpt-oss-20b` | chat model (cheapest available) |
| `EMBED_ENDPOINT` | `databricks-gte-large-en` | 1024-dim, matches `vector(1024)` |
| `LB_PROJECT` | `opennav-rag-chat` | Lakebase project id |
| `SUSPEND_SECONDS` | `300` | Lakebase scale-to-zero idle timeout |
| `SKIP_DEPLOY` | `0` | `1` = set up but don't deploy |

> Changing the chat model also requires editing `app.yaml` (`DATABRICKS_ENDPOINT`) —
> that value drives the **deployed** runtime; `.env` only drives local dev.

## Key fixes baked in (don't lose these)

1. **`server/lib/` + `client/src/lib/` un-ignored** in the root `.gitignore` — the
   monorepo's `lib/` rule otherwise hides them, breaking the Databricks host build.
2. **`User-Agent` on the Wikipedia fetch** (`server/lib/seed-data.ts`) — without it,
   seeding gets an HTML block page and the corpus stays empty.
3. **Chat model overridden** to one that exists (`databricks-gpt-5-4-mini` is not in
   this workspace).
4. **`.env` written by hand** — `apps init`'s Lakebase auto-resolve API is outdated.

## Verify

```bash
# corpus seeded? (expect 69 from the 9 default articles)
EP=projects/opennav-rag-chat/branches/production/endpoints/primary
HOST=$(databricks postgres get-endpoint $EP -o json | python3 -c "import json,sys;print(json.load(sys.stdin)['status']['hosts']['host'])")
TOKEN=$(databricks postgres generate-database-credential $EP -o json | python3 -c "import json,sys;print(json.load(sys.stdin)['token'])")
PGPASSWORD="$TOKEN" psql "host=$HOST user=$(databricks current-user me -o json | python3 -c 'import json,sys;print(json.load(sys.stdin)["userName"])') dbname=databricks_postgres sslmode=require" -tAc "SELECT count(*) FROM rag.documents;"

# app status + logs
databricks apps get rag-chat-app --profile opennav-prod
databricks apps logs rag-chat-app --profile opennav-prod | tail -40
```

Open the printed app URL (Databricks OAuth-gated; sign in with the workspace account).

## Re-seed / local dev

- **Re-seed** the corpus: set `RAG_RESEED=true` in `app.yaml`, `npm run deploy`, then
  set it back to `false`.
- **Local dev** (`npm run dev`): needs `DATABRICKS_WORKSPACE_ID` in `.env` (setup.sh
  writes it). Always **deploy before first local run** so the app's service principal
  owns the Lakebase schema (else `permission denied for schema`).

## Cost & teardown

- Model Serving is pay-per-token; Lakebase bills compute until it scales to zero
  (`SUSPEND_SECONDS`). The **trial sku expires ~2026-06-28**. The `opennav-prod`
  `$400/mo` budget only *alerts* (80%/100%) — it does not stop spend.
- Teardown: `databricks apps delete rag-chat-app` and
  `databricks postgres delete-project projects/opennav-rag-chat` (⚠️ deletes all data).
