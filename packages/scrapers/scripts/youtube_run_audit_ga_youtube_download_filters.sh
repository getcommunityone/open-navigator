#!/usr/bin/env bash
# Run GA YouTube download-filter audit SQL against the configured database.
#
# Usage (from repo root):
#   ./packages/scrapers/src/scrapers/youtube/run_audit_ga_youtube_download_filters.sh
#
# Resolves URL in the same order as other loaders:
#   OPEN_NAVIGATOR_DATABASE_URL, NEON_DATABASE_URL_DEV, NEON_DATABASE_URL, DATABASE_URL
# then falls back to local docker Postgres on 5433 (see run_jurisdiction_id_migration.sh).

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

SQL="${ROOT}/packages/scrapers/src/scrapers/youtube/audit_ga_youtube_download_filters.sql"
echo "==> Database: ${DB_URL%%@*}@…"
echo "==> Running: ${SQL}"
psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$SQL"
