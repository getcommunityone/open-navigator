#!/usr/bin/env bash
# Run psql against the same connection string as discovery pipelines (see resolve_database_url).
# Usage (repo root):
#   ./packages/hosting/scripts/neon/psql_resolved.sh -f packages/hosting/scripts/neon/migrations/035_create_bronze_contacts_scraped.sql
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"
if [[ ! -x .venv/bin/python ]]; then
  echo "error: need repo-root .venv (run: python -m venv .venv && .venv/bin/pip install -r requirements.txt)" >&2
  exit 1
fi
URL="$(.venv/bin/python -c "from scripts.discovery.jurisdiction_discovery_pipeline import resolve_database_url; print(resolve_database_url().strip())")"
if [[ -z "$URL" ]]; then
  echo "error: no database URL resolved. In .env set one of:" >&2
  echo "  OPEN_NAVIGATOR_DATABASE_URL, NEON_DATABASE_URL_DEV, NEON_DATABASE_URL, DATABASE_URL" >&2
  exit 1
fi
exec psql "$URL" "$@"
