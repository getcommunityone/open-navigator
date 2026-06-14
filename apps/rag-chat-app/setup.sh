#!/usr/bin/env bash
#
# From-scratch setup + deploy for the RAG Chat App on Databricks.
# Idempotent: safe to re-run. Automates everything except the interactive
# `databricks auth login` (browser). See SETUP.md for the full runbook.
#
# Usage:
#   ./setup.sh              # set up + deploy
#   SKIP_DEPLOY=1 ./setup.sh   # set up only (no npm run deploy)
#
set -euo pipefail

# ── Config (override via env) ─────────────────────────────────────────────────
WORKSPACE_URL="${WORKSPACE_URL:-https://adb-7405608833986267.7.azuredatabricks.net}"
PROFILE="${DATABRICKS_CONFIG_PROFILE:-opennav-prod}"
LB_PROJECT="${LB_PROJECT:-opennav-rag-chat}"
LB_DISPLAY="${LB_DISPLAY:-Open Navigator RAG Chat}"
CHAT_ENDPOINT="${CHAT_ENDPOINT:-databricks-gpt-oss-20b}"
EMBED_ENDPOINT="${EMBED_ENDPOINT:-databricks-gte-large-en}"
CLI_VERSION="${CLI_VERSION:-1.3.0}"
SUSPEND_SECONDS="${SUSPEND_SECONDS:-300}"
GENIE_TITLE="${GENIE_TITLE:-NYC Taxi Analytics}"
GENIE_TABLE="${GENIE_TABLE:-samples.nyctaxi.trips}"

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
PY="$(command -v python3 || echo python)"
ok()   { printf '\033[32m✓\033[0m %s\n' "$*"; }
info() { printf '\033[36m→\033[0m %s\n' "$*"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# ── 1. Databricks CLI (rootless install if missing) ───────────────────────────
if ! command -v databricks >/dev/null 2>&1; then
  info "Installing Databricks CLI v${CLI_VERSION} into ~/.local/bin (rootless)…"
  mkdir -p "$HOME/.local/bin"
  tmp="$(mktemp -d)"
  curl -fsSL "https://github.com/databricks/cli/releases/download/v${CLI_VERSION}/databricks_cli_${CLI_VERSION}_linux_amd64.zip" -o "$tmp/db.zip"
  "$PY" -c "import zipfile,sys;zipfile.ZipFile('$tmp/db.zip').extractall('$HOME/.local/bin')"
  chmod +x "$HOME/.local/bin/databricks"; rm -rf "$tmp"
  case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$HOME/.local/bin:$PATH";; esac
fi
ok "Databricks CLI: $(databricks --version)"

# ── 2. Agent skills ───────────────────────────────────────────────────────────
databricks aitools version >/dev/null 2>&1 || { info "Installing aitools skills…"; databricks aitools install; }
ok "aitools skills present"

# ── 3. Auth (interactive — must be done by the user) ──────────────────────────
if ! databricks current-user me --profile "$PROFILE" >/dev/null 2>&1; then
  die "Not authenticated. Run this once (opens a browser), then re-run setup.sh:
    databricks auth login --host $WORKSPACE_URL --profile $PROFILE"
fi
WHOAMI="$(databricks current-user me --profile "$PROFILE" -o json | "$PY" -c 'import json,sys;print(json.load(sys.stdin)["userName"])')"
ok "Authenticated as $WHOAMI (profile: $PROFILE)"
export DATABRICKS_CONFIG_PROFILE="$PROFILE"

# ── 4. Capability check (fail fast if the workspace lacks what we need) ────────
EPS="$(databricks serving-endpoints list -o json | "$PY" -c 'import json,sys;print("\n".join(e["name"] for e in json.load(sys.stdin)))')"
grep -qx "$CHAT_ENDPOINT"  <<<"$EPS" || die "Chat endpoint '$CHAT_ENDPOINT' not found. Available:\n$EPS"
grep -qx "$EMBED_ENDPOINT" <<<"$EPS" || die "Embedding endpoint '$EMBED_ENDPOINT' not found. Available:\n$EPS"
ok "Model Serving: $CHAT_ENDPOINT + $EMBED_ENDPOINT available"

# ── 5. Lakebase project (create if missing; lower suspend timeout for cost) ────
if databricks postgres get-project "projects/$LB_PROJECT" >/dev/null 2>&1; then
  ok "Lakebase project 'projects/$LB_PROJECT' exists"
else
  info "Creating Lakebase project '$LB_PROJECT'…"
  databricks postgres create-project "$LB_PROJECT" --json "{\"spec\":{\"display_name\":\"$LB_DISPLAY\"}}" >/dev/null
  ok "Created Lakebase project '$LB_PROJECT'"
fi
EP="projects/$LB_PROJECT/branches/production/endpoints/primary"
# Best-effort cost optimization: scale to zero after $SUSPEND_SECONDS idle.
databricks postgres update-endpoint "$EP" spec.autoscaling.suspend_timeout_duration \
  --json "{\"spec\":{\"autoscaling\":{\"suspend_timeout_duration\":\"${SUSPEND_SECONDS}s\"}}}" >/dev/null 2>&1 \
  && ok "Lakebase suspend timeout = ${SUSPEND_SECONDS}s" \
  || info "Could not set suspend timeout (non-fatal; check 'databricks postgres update-endpoint -h')"

# ── 5b. Genie space (AI/BI analytics) — resolve by title, create if missing ───
WID="$(databricks experimental aitools tools get-default-warehouse --profile "$PROFILE" -o json 2>/dev/null | "$PY" -c 'import json,sys;print(json.load(sys.stdin).get("warehouse_id",""))' 2>/dev/null || true)"
[ -n "${WID:-}" ] || WID="$(databricks warehouses list -o json | "$PY" -c 'import json,sys;d=json.load(sys.stdin);print(d[0]["id"] if d else "")')"
# Resolve an existing space by title (payload shape varies, so handle dict/list).
GENIE_SPACE_ID="$(databricks api get /api/2.0/genie/spaces | "$PY" -c "
import json,sys
d=json.load(sys.stdin)
spaces=d.get('spaces',[]) if isinstance(d,dict) else (d if isinstance(d,list) else [])
print(next((s.get('space_id','') for s in spaces if s.get('title')=='$GENIE_TITLE'),''))
" 2>/dev/null || true)"
if [ -z "${GENIE_SPACE_ID:-}" ]; then
  info "Creating Genie space '$GENIE_TITLE' over $GENIE_TABLE…"
  GENIE_SPACE_ID="$(databricks genie create-space "$WID" \
    "{\"version\":2,\"data_sources\":{\"tables\":[{\"identifier\":\"$GENIE_TABLE\"}]}}" \
    --title "$GENIE_TITLE" -o json | "$PY" -c 'import json,sys;print(json.load(sys.stdin)["space_id"])')"
  ok "Created Genie space $GENIE_SPACE_ID — update genie_space_id in databricks.yml if it changed."
else
  ok "Genie space '$GENIE_TITLE' = $GENIE_SPACE_ID"
fi

# ── 6. .env (write if missing) ────────────────────────────────────────────────
if [ -f .env ]; then
  ok ".env already present (left as-is)"
else
  info "Writing .env…"
  WSID="$(databricks api get /api/2.1/unity-catalog/current-metastore-assignment | "$PY" -c 'import json,sys;print(json.load(sys.stdin)["workspace_id"])')"
  cat > .env <<EOF
# Generated by setup.sh — gitignored. Profile-based auth (no secrets here).
DATABRICKS_CONFIG_PROFILE=$PROFILE
DATABRICKS_HOST=$WORKSPACE_URL
DATABRICKS_WORKSPACE_ID=$WSID
LAKEBASE_ENDPOINT=$EP
PGDATABASE=databricks_postgres
DATABRICKS_ENDPOINT=$CHAT_ENDPOINT
DATABRICKS_EMBEDDING_ENDPOINT=$EMBED_ENDPOINT
DATABRICKS_GENIE_SPACE_ID=$GENIE_SPACE_ID
RAG_RESEED=false
EOF
  ok "Wrote .env"
fi

# ── 7. npm deps ───────────────────────────────────────────────────────────────
[ -d node_modules ] || { info "npm install…"; npm install; }
ok "npm deps present"

# ── 8. Deploy (deploy-first: the app SP must own the Lakebase schema) ─────────
if [ "${SKIP_DEPLOY:-0}" = "1" ]; then
  info "SKIP_DEPLOY=1 — setup complete, skipping deploy."; exit 0
fi
info "Deploying (npm run deploy)…"
npm run deploy

# ── 9. Verify corpus ──────────────────────────────────────────────────────────
HOST="$(databricks postgres get-endpoint "$EP" -o json | "$PY" -c 'import json,sys;print(json.load(sys.stdin)["status"]["hosts"]["host"])')" || true
if command -v psql >/dev/null 2>&1 && [ -n "${HOST:-}" ]; then
  TOKEN="$(databricks postgres generate-database-credential "$EP" -o json | "$PY" -c 'import json,sys;print(json.load(sys.stdin)["token"])')"
  N="$(PGPASSWORD="$TOKEN" psql "host=$HOST user=$WHOAMI dbname=databricks_postgres sslmode=require" -tAc 'SELECT count(*) FROM rag.documents;' 2>/dev/null || echo '?')"
  ok "rag.documents rows: $N"
fi
APP_URL="$(databricks apps get rag-chat-app -o json | "$PY" -c 'import json,sys;print(json.load(sys.stdin).get("url",""))' 2>/dev/null || true)"
ok "Done. App: ${APP_URL:-https://rag-chat-app-<id>.azure.databricksapps.com}"
