#!/usr/bin/env bash
# Preview or apply LocalView-based jurisdiction linking for bronze YouTube tables
# (uses intermediate.int_events_channels + int_jurisdictions; no jurisdictions_details_search).
#
# Usage (repo root):
#   ./scripts/datasources/youtube/run_link_youtube_bronze_from_localview.sh
#   ./scripts/datasources/youtube/run_link_youtube_bronze_from_localview.sh --apply

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi

DB_URL="${OPEN_NAVIGATOR_DATABASE_URL:-${NEON_DATABASE_URL_DEV:-${NEON_DATABASE_URL:-${DATABASE_URL:-}}}}"
if [[ -z "$DB_URL" ]]; then
  PGPASSWORD="${POSTGRES_PASSWORD:-password}"
  DB_URL="postgresql://postgres:${PGPASSWORD}@localhost:5433/open_navigator"
fi

echo "==> Database: ${DB_URL%%@*}@…"

if [[ "${1:-}" == "--apply" ]]; then
  SQL="${ROOT}/scripts/datasources/youtube/link_youtube_bronze_from_localview_apply.sql"
  echo "==> APPLY: ${SQL}"
else
  SQL="${ROOT}/scripts/datasources/youtube/link_youtube_bronze_from_localview_preview.sql"
  echo "==> PREVIEW: ${SQL}"
  echo "    (pass --apply to run link_youtube_bronze_from_localview_apply.sql)"
fi

psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$SQL"
