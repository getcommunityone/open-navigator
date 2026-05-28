#!/usr/bin/env bash
# GA jurisdiction vs YouTube / bronze coverage gaps (see SQL header for interpretation).
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

FULL_SQL="${ROOT}/packages/scrapers/src/scrapers/youtube/audit_ga_jurisdiction_youtube_gaps.sql"
MIN_SQL="${ROOT}/packages/scrapers/src/scrapers/youtube/audit_ga_jurisdiction_youtube_gaps_minimal.sql"

echo "==> Database: ${DB_URL%%@*}@…"

has_details="$(
  psql "$DB_URL" -tAc "
    SELECT CASE
      WHEN EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'jurisdiction'
          AND EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'jurisdiction'
              AND column_name = 'youtube_channels'
          )
      ) THEN 1 ELSE 0 END;
  " 2>/dev/null || echo 0
)"

if [[ "${has_details:-0}" == "1" ]]; then
  echo "==> Running (full): ${FULL_SQL}"
  psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$FULL_SQL"
else
  echo "==> jurisdiction missing youtube_channels column — running minimal audit only."
  echo "==> Load details (e.g. scripts/datasources/jurisdictions/load_details_to_postgres.py) for sections 2–6."
  echo "==> Running: ${MIN_SQL}"
  psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$MIN_SQL"
fi
