#!/usr/bin/env bash
# Run audit_youtube_jurisdiction_coverage.sql (one state: match rates + top 5 gaps by population).
#
# Usage (repo root):
#   ./packages/scrapers/src/scrapers/youtube/run_audit_youtube_jurisdiction_coverage.sh GA

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

if [[ -z "${1:-}" ]] || [[ "${#1}" -ne 2 ]]; then
  echo "Usage: $0 <STATE>   # two-letter USPS code, e.g. GA AL TX" >&2
  exit 1
fi

STATE="$(echo "$1" | tr '[:lower:]' '[:upper:]')"

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

SQL="${ROOT}/packages/scrapers/src/scrapers/youtube/audit_youtube_jurisdiction_coverage.sql"
echo "==> Database: ${DB_URL%%@*}@…"
echo "==> State: $STATE"
echo "==> Running: $SQL"

psql "$DB_URL" -v ON_ERROR_STOP=1 -v "one_state=$STATE" -f "$SQL"
