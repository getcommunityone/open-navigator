# Open Navigator on Databricks Apps

Ready-to-deploy [Databricks Apps](https://docs.databricks.com/aws/en/dev-tools/databricks-apps)
config for the existing Open Navigator web app: the FastAPI backend
(`api.main:app`) serving the built React/Vite frontend **and** the Docusaurus docs
as static files, all in one process, pointed at the already-loaded **Neon prod**
Postgres.

This is a **fallback** for the HuggingFace Space (when it is paused/flagged). It
mirrors what the HF `Dockerfile.huggingface` builds, adapted to the Databricks
Apps platform (one process, no nginx, no Docker, `requirements.txt` only).

## How it works

| Path | Served by |
|------|-----------|
| `/` | built React SPA (`api/static/index.html`) |
| `/assets/*` | Vite hashed JS/CSS |
| `/docs/*` | Docusaurus documentation (`api/static/docs`) |
| `/data/*`, `/static/*` | public JSON marts + logos/pdfs (`web_app/public`) |
| `/api/*` | FastAPI routes |
| `/api/docs`, `/redoc` | Swagger UI / ReDoc |

On HuggingFace, nginx fronts three services. Databricks Apps run **one process on
one port**, so `api/main.py` itself serves the SPA + docs (added: a `/{full_path}`
catch-all + the `root()` SPA fallback, both no-ops when no build is present).

## Key design decisions

- **Entry point: `api.main:app`** (the real, full app) — not the stale `api.app:app`.
- **Port:** bound to `0.0.0.0:${DATABRICKS_APP_PORT}` (hardcoding causes 502).
- **Workspace packages (`packages/*`) via `PYTHONPATH`, not pip.** Pip-installing
  them would pull each one's heavy transitive deps (torch via
  `sentence-transformers`, `mlflow`, `splink`, …) and blow the 10-minute startup
  budget / OOM Medium compute. Instead each import root is on `PYTHONPATH`
  (`app.yaml`), and `requirements.txt` lists **only** the serving deps. The API
  imports the heavy libs lazily (inside functions), so they are not needed to
  start or serve.
- **Self-contained source root.** `build.sh` stages `api/`, `packages/`,
  `scripts/`, `web_app/public/`, and the built `api/static` into this directory
  (all git-ignored) so the bundle uploads a minimal, self-contained tree with its
  own trimmed `requirements.txt` — without touching the repo-root
  `requirements.txt` that HuggingFace/CI depend on.
- **>10 MB files stripped** before upload (per-file platform limit), e.g.
  `web_app/public/wikicommons/GA_latest.jpg` (~36 MB) — same as the HF deploy.

## Database / secret

`NEON_DATABASE_URL` is injected from the existing secret scope
**`open-navigator`**, key **`neon-prod-url`** (already present in the
`opennav-prod` workspace), via the `neon-db-url` resource in `databricks.yml`.
`api/database.py` resolves `NEON_DATABASE_URL_DEV → NEON_DATABASE_URL →
DATABASE_URL`; we set only the prod var (and leave `*_DEV` unset) so the app
cannot fall back to a dev branch. `API_DB_SCHEMA=public`.

If the secret ever needs (re)setting:

```bash
databricks secrets put-secret open-navigator neon-prod-url --profile opennav-prod
# (paste the postgresql://...neon.tech/... URL when prompted — never echo it)
```

## Build & validate (does NOT deploy)

```bash
cd apps/open-navigator-web
./build.sh                # build docs+frontend, stage source, validate bundle
```

## Deploy (requires explicit consent + MANAGE on the secret scope)

```bash
cd apps/open-navigator-web
./build.sh --deploy
# or, with the bundle already built/staged:
databricks bundle deploy -t dev --profile opennav-prod
databricks bundle run open-navigator -t dev --profile opennav-prod
```

Then verify:

```bash
databricks apps get open-navigator --profile opennav-prod -o json   # app_status.state == RUNNING
databricks apps logs open-navigator --follow --profile opennav-prod  # (OAuth auth only)
```

## Caveats / things a human still needs to decide

- **Compute size.** Starts on the default **Medium (6 GB / 2 vCPU)**. The trimmed
  deps make this viable, but `pandas`/`plotly`/`folium` + asyncpg pools are not
  free — if startup is tight or memory-pressured, bump to **Large (12 GB)** in the
  app settings.
- **10-minute startup.** Pip install of the trimmed `requirements.txt` should be
  well under the limit (no torch/transformers). If a future change re-introduces a
  heavy lazy import into an import-time path, watch the startup clock.
- **Static `/data` marts.** These are git-ignored and copied from the live working
  tree by `build.sh`. Make sure they exist locally (the census-map JSONs) before
  building, or the maps render empty — same gotcha as the HF deploy.
