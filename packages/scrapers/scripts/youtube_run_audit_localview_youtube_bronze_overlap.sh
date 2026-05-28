#!/usr/bin/env bash
# Overlap counts: bronze_events_localview vs bronze_events_youtube (by video_id).
# Usage: ./packages/scrapers/src/scrapers/youtube/run_audit_localview_youtube_bronze_overlap.sh GA

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

if [[ -z "${1:-}" ]] || [[ "${#1}" -ne 2 ]]; then
  echo "Usage: $0 <STATE>" >&2
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

SQL="${ROOT}/packages/scrapers/src/scrapers/youtube/audit_localview_youtube_bronze_overlap.sql"
echo "==> State=$STATE  $SQL"
psql "$DB_URL" -v ON_ERROR_STOP=1 -v "one_state=$STATE" -f "$SQL"
