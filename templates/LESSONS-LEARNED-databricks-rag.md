# Lessons learned — DevHub RAG Chat App generation (2026-06-14)

Concrete gotchas from setting up the DevHub **rag-chat** example on the **trial Azure
Databricks** workspace (`dbw-opennav-prod-eastus-001`,
`adb-7405608833986267.7.azuredatabricks.net`). Read this BEFORE the next run — it
turns a multi-detour session into a straight line.

## 0. Environment is bare — install rootless (no sudo on this box)

- `databricks` CLI was NOT installed and `sudo` needs a password. Install rootless:
  download the release zip and extract into `~/.local/bin` (already on PATH).
  ```bash
  ver=1.3.0
  curl -fsSL "https://github.com/databricks/cli/releases/download/v${ver}/databricks_cli_${ver}_linux_amd64.zip" -o /tmp/db.zip
  .venv/bin/python -c "import zipfile;zipfile.ZipFile('/tmp/db.zip').extractall('$HOME/.local/bin')"
  chmod +x ~/.local/bin/databricks
  ```
  (Same trick already used for `az` and `terraform`.)
- Agent skills: `databricks aitools install` → installs 9 skills into **`~/.claude/skills/`**
  (NOT `~/.agents/skills`, which only had `microsoft-foundry`). Check both scopes; a
  stale `.agents/skills` copy can shadow the fresh one.
- Auth is interactive (browser) — the USER must run it; you can't:
  ```bash
  databricks auth login --host https://adb-7405608833986267.7.azuredatabricks.net --profile opennav-prod
  ```

## 1. Capability-check the workspace BEFORE scaffolding (trial = not everything is on)

```bash
databricks serving-endpoints list --profile opennav-prod   # chat + embedding models
databricks apps list --profile opennav-prod                # Apps hosting enabled?
databricks postgres -h                                      # Lakebase = `postgres` group
```

Findings on this workspace:
- Embeddings `databricks-gte-large-en` ✅ present (1024-dim → matches the template's `vector(1024)`).
- **The template's default chat model `databricks-gpt-5-4-mini` does NOT exist here.** Available
  chat models include `databricks-gpt-oss-20b` (cheapest), `databricks-meta-llama-3-3-70b-instruct`,
  `databricks-claude-opus-4-8`. **You MUST override `DATABRICKS_ENDPOINT`** or the app fails.
- Apps hosting ✅; Lakebase ✅ (Public Preview, autoscaling).

## 2. Lakebase = `databricks postgres`, not `databricks database`

- `databricks database ...` is the OLD Provisioned API (returns empty here). Lakebase Autoscaling
  (the current default) is the **`databricks postgres`** command group.
- Create once; it auto-makes a `production` branch + `primary` endpoint:
  ```bash
  databricks postgres create-project opennav-rag-chat \
    --json '{"spec":{"display_name":"Open Navigator RAG Chat"}}' --profile opennav-prod
  ```
- ⚠️ **Default endpoint suspend timeout is 24h (`86400s`)** → bills ~1 CU idle for a full day
  before scaling to zero. Drop it to `300s` for cost (`databricks postgres update-endpoint ... -h`).
- IDs are RFC-1123: branch=`production`, database id=`databricks-postgres`
  (postgres db name = `databricks_postgres`).

## 3. `databricks apps init` gotchas (the real time-sinks)

- The rag-chat template needs **all three** postgres fields set together, not just branch+database:
  ```
  Error: incomplete resource "postgres": missing fields [postgres.project] (all fields must be set together)
  ```
  Correct invocation (run from `apps/` so it lands in `apps/rag-chat-app/`):
  ```bash
  databricks apps init \
    --template https://github.com/databricks/app-templates/tree/main/rag-chat \
    --name rag-chat-app \
    --set lakebase.postgres.project=opennav-rag-chat \
    --set lakebase.postgres.branch=production \
    --set lakebase.postgres.database=databricks-postgres
  ```
- **Auto-resolve of the Lakebase `.env` FAILS** with
  `No API found for 'GET /postgres/production/endpoints'` — the AppKit plugin calls an outdated
  endpoint path, so **no `.env` is written**. Don't chase it: the deploy-first flow injects
  connection vars from the bound resource; for local dev set vars manually.
- `npm install` during init flaked once (`exit status 217`) but auto-retried and succeeded —
  `node_modules/` ends up present. Node v24 / npm 11 worked fine.
- `--name` ⇒ non-interactive; no `--profile` flag — it uses the default profile (export
  `DATABRICKS_CONFIG_PROFILE=opennav-prod` to be safe).

## 4. Build/run order: DEPLOY FIRST, then local

The `databricks-lakebase` skill's #1 rule: **deploy before running locally**, or you hit
`permission denied for schema` (the app's service principal must create+own the schema; if your
user creds create it first, the SP can't use it and you can't easily fix it without dropping data).

- Override the chat model in `app.yaml` first: `DATABRICKS_ENDPOINT: 'databricks-gpt-oss-20b'`.
- Then `npm run deploy` (runs `scripts/sync-bundle-vars.mjs` → hydrates bundle vars from the bound
  postgres resource → `databricks bundle deploy` + `run`). Prints the app URL.
- Local dev (`npm run dev`) additionally needs the **numeric** `DATABRICKS_WORKSPACE_ID` in `.env`
  (used to build the AI Gateway URL):
  ```bash
  databricks api get /api/2.1/unity-catalog/current-metastore-assignment \
    | python3 -c "import json,sys;print(json.load(sys.stdin)['workspace_id'])"
  ```

## 4a. Build FAILS: the monorepo `.gitignore` swallows `server/lib/` (BIG one)

Symptom — `npm run deploy` uploads + installs, then the **host** build dies:
```
[UNRESOLVED_IMPORT] Could not resolve './lib/rag-store' in server/server.ts   (x4)
```
…even though `npm run build` passes **locally**. Tell-tale: only the `./lib/*` imports
fail; `./routes/*` resolve fine.

Cause — the app is nested inside the `open-navigator` git repo, and
`databricks bundle deploy` honors `.gitignore`. The root `.gitignore` has `lib/`
(Python build-output pattern), which matches `apps/rag-chat-app/server/lib/` **and**
`client/src/lib/` → those files are never uploaded (and would never be committed either).

Fix — re-include them in the **root** `.gitignore` (mirrors the existing
`!web_app/src/lib/` line):
```gitignore
!apps/rag-chat-app/server/lib/
!apps/rag-chat-app/client/src/lib/
```
Verify: `git check-ignore apps/rag-chat-app/server/lib/rag-store.ts` prints nothing.

## 4b. Seeding FAILS: Wikipedia needs a `User-Agent` (cloud IPs get an HTML block page)

Symptom — app starts, but every article logs:
```
[seed] Databricks failed: Unexpected token '<', "<!DOCTYPE "... is not valid JSON
```
`rag.documents` stays empty → retrieval returns nothing.

Cause — `server/lib/seed-data.ts` calls `fetch(url)` with **no headers**. Wikimedia
returns an HTML block page (not JSON) to UA-less requests, especially from cloud egress
IPs like Databricks Apps. (Local machine works because curl/Node send a default UA.)

Fix — add a descriptive UA per Wikimedia policy:
```ts
const res = await fetch(url, {
  headers: {
    'User-Agent': 'open-navigator-rag-chat/1.0 (https://github.com/getcommunityone/open-navigator; johnbowyer@getcommunityone.onmicrosoft.com)',
    Accept: 'application/json',
  },
});
if (!res.ok) throw new Error(`Wikipedia ${title}: HTTP ${res.status}`);
```
After redeploy, verify the corpus landed (69 chunks from the 9 default articles):
```bash
EP=projects/opennav-rag-chat/branches/production/endpoints/primary
HOST=$(databricks postgres get-endpoint $EP -o json | python3 -c "import json,sys;print(json.load(sys.stdin)['status']['hosts']['host'])")
TOKEN=$(databricks postgres generate-database-credential $EP -o json | python3 -c "import json,sys;print(json.load(sys.stdin)['token'])")
PGPASSWORD="$TOKEN" psql "host=$HOST user=$(databricks current-user me -o json | python3 -c 'import json,sys;print(json.load(sys.stdin)["userName"])') dbname=databricks_postgres sslmode=require" -tAc "SELECT count(*) FROM rag.documents;"
```

## 4c. The `.env` that `apps init` failed to write — exact keys

Because §3's auto-resolve fails, write `apps/rag-chat-app/.env` by hand. The minimum the
deploy (`scripts/sync-bundle-vars.mjs`) and local dev need:
```bash
DATABRICKS_CONFIG_PROFILE=opennav-prod
DATABRICKS_HOST=https://adb-7405608833986267.7.azuredatabricks.net
DATABRICKS_WORKSPACE_ID=7405608833986267
LAKEBASE_ENDPOINT=projects/opennav-rag-chat/branches/production/endpoints/primary  # resource PATH, not host
PGDATABASE=databricks_postgres
DATABRICKS_ENDPOINT=databricks-gpt-oss-20b
DATABRICKS_EMBEDDING_ENDPOINT=databricks-gte-large-en
RAG_RESEED=false
```
`sync-bundle-vars.mjs` derives the bundle's `postgres_branch` from `LAKEBASE_ENDPOINT`
(regex on `projects/…/branches/…`), so it MUST be the resource path.

## 5. Organization & cost

- Keep the app self-contained in **`apps/rag-chat-app/`**; its `.gitignore` already excludes
  `node_modules/`, `.env`, `.databricks/`, `dist/` — safe to commit via PR.
- Cost realities: Model Serving is pay-per-token; Lakebase bills compute when not suspended;
  the **trial sku expires ~2026-06-28**. Keep the cheapest chat model and a short Lakebase
  suspend timeout. The `$400/mo` budget alert (opennav-prod) emails at 80%/100% — it does NOT
  stop spend.

## TL;DR fast path for next time

1. Ensure CLI + `aitools install` + `databricks auth login` (user does login).
2. `serving-endpoints list` → pick an existing chat model; confirm `gte-large-en`.
3. `databricks postgres create-project …` → lower suspend timeout to 300s.
4. `apps init …` with **project+branch+database** all set; ignore the `.env` auto-resolve warning, then write `.env` by hand (§4c).
5. Set `DATABRICKS_ENDPOINT` in `app.yaml` to the existing chat model.
6. Re-include `server/lib/` + `client/src/lib/` in root `.gitignore` (§4a), and add a `User-Agent` to the Wikipedia fetch (§4b).
7. `npm run deploy` (deploy-first), verify `rag.documents` count, then patch `DATABRICKS_WORKSPACE_ID` for local `npm run dev`.

> **Or just run [`apps/rag-chat-app/setup.sh`](../apps/rag-chat-app/setup.sh)** — it automates 1–7 (CLI install, skills, capability check, Lakebase create, `.env`, deploy) and stops only for the interactive `auth login`. See [`apps/rag-chat-app/SETUP.md`](../apps/rag-chat-app/SETUP.md).
