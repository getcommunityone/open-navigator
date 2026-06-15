#!/usr/bin/env bash
#
# One-time setup for the lakebase-serving-sync DAB. Idempotent — safe to re-run.
#
#   1. Create the Lakebase project (skips if it exists)
#   2. Create the secret scope (skips if it exists)
#   3. Store the prod Neon URL secret (read from repo .env: NEON_DATABASE_URL)
#   4. Validate the bundle
#
# Usage:
#   apps/lakebase-serving-sync/setup.sh                 # defaults below
#   PROJECT_ID=opennav-rag-chat apps/lakebase-serving-sync/setup.sh   # reuse existing project
#
# After this, deploy + run: see RUNBOOK.md.
set -euo pipefail

PROFILE="${PROFILE:-opennav-prod}"
PROJECT_ID="${PROJECT_ID:-opennav-serving}"
SECRET_SCOPE="${SECRET_SCOPE:-open-navigator}"
SECRET_KEY="${SECRET_KEY:-neon-prod-url}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"

echo "▶ Profile=$PROFILE  Project=$PROJECT_ID  Secret=$SECRET_SCOPE/$SECRET_KEY"

# --- 1. Lakebase project -----------------------------------------------------
if databricks postgres list-projects --profile "$PROFILE" -o json \
   | grep -q "\"projects/$PROJECT_ID\""; then
  echo "✓ Lakebase project '$PROJECT_ID' already exists"
else
  echo "→ Creating Lakebase project '$PROJECT_ID'…"
  databricks postgres create-project "$PROJECT_ID" \
    --json "@$HERE/templates/create-project.json" \
    --profile "$PROFILE"
  echo "✓ Created '$PROJECT_ID'"
fi

# --- 2. Secret scope ---------------------------------------------------------
if databricks secrets list-scopes --profile "$PROFILE" -o json \
   | grep -q "\"$SECRET_SCOPE\""; then
  echo "✓ Secret scope '$SECRET_SCOPE' already exists"
else
  echo "→ Creating secret scope '$SECRET_SCOPE'…"
  databricks secrets create-scope "$SECRET_SCOPE" --profile "$PROFILE"
  echo "✓ Created scope '$SECRET_SCOPE'"
fi

# --- 3. Neon URL secret (from repo .env) ------------------------------------
# Strip surrounding quotes — NEON_DATABASE_URL in .env is quoted, and a quoted
# value breaks URL parsing in the job (and can leak the URL into JDBC errors).
NEON_URL="$(grep -E '^NEON_DATABASE_URL=' "$REPO_ROOT/.env" | head -1 | cut -d= -f2-)"
NEON_URL="${NEON_URL%\"}"; NEON_URL="${NEON_URL#\"}"
NEON_URL="${NEON_URL%\'}"; NEON_URL="${NEON_URL#\'}"
if [ -z "$NEON_URL" ]; then
  echo "✗ NEON_DATABASE_URL not found in $REPO_ROOT/.env — set the secret manually:"
  echo "    databricks secrets put-secret $SECRET_SCOPE $SECRET_KEY --string-value '<neon url>' --profile $PROFILE"
  exit 1
fi
echo "→ Storing prod Neon URL into $SECRET_SCOPE/$SECRET_KEY…"
databricks secrets put-secret "$SECRET_SCOPE" "$SECRET_KEY" \
  --string-value "$NEON_URL" --profile "$PROFILE"
echo "✓ Secret stored"

# --- 4. Validate the bundle --------------------------------------------------
echo "→ Validating bundle (dev)…"
( cd "$HERE" && databricks bundle validate --strict --target dev --profile "$PROFILE" )

echo
echo "✅ Setup complete. Next (see RUNBOOK.md):"
echo "    cd $HERE"
echo "    databricks bundle deploy --target dev --profile $PROFILE"
echo "    databricks bundle run serving_sync --target dev --profile $PROFILE"
