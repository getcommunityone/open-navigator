#!/usr/bin/env bash
# Selectively push Census gazetteer + jurisdiction bronze DDL to Postgres (typically Neon).
# No pg_dump: applies idempotent DDL then runs CSV loaders via resolve_target_database_url.
#
# Prereqs: download CSVs →  python -m scrapers.census.download_census_gazetteer
#
# Usage:
#   Set NEON_DATABASE_URL_DEV (or NEON_DATABASE_URL / OPEN_NAVIGATOR_DATABASE_URL) in .env, then:
#     ./scripts/deployment/neon/run_bronze_jurisdictions_to_cloud.sh
#   Priority states subset + skip national ZCTA:
#     ./scripts/deployment/neon/run_bronze_jurisdictions_to_cloud.sh --filter-usps AL,GA,IN,MA,MT,WA,WI
#   Gazetteer CLI flags pass through last step only (everything after `--`):

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

PY="${ROOT}/.venv/bin/python"
[[ -x "$PY" ]] || {
  echo "Missing venv interpreter: ${PY}"
  exit 1
}

if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi

"${PY}" "${ROOT}/scripts/deployment/neon/ensure_bronze_jurisdictions_cloud.py" --schema-only

exec "${PY}" -m ingestion.census.gazetteer "$@"
