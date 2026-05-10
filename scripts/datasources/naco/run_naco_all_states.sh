#!/usr/bin/env bash
# Scrape NACo for all states in scraper's ALL_STATES list (50), then load into bronze_jurisdictions_*_naco tables.
#
# First run (full ~3k counties × /get/county — slow, be polite with default delays):
#   ./scripts/datasources/naco/run_naco_all_states.sh
#
# Same-day refresh: reuse merged profiles when fresh (still downloads general.js with --force):
#   INCREMENTAL=1 ./scripts/datasources/naco/run_naco_all_states.sh
#
# Later: only refetch profiles older than N days:
#   INCREMENTAL=1 PROFILE_MAX_AGE_DAYS=30 ./scripts/datasources/naco/run_naco_all_states.sh
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$ROOT"

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing ${PY} — python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

SCRAPE=( "$PY" scripts/datasources/naco/scrape_naco_counties.py --all-states --force )

if [[ "${INCREMENTAL:-}" == "1" ]]; then
  SCRAPE+=( --incremental )
fi

if [[ -n "${PROFILE_MAX_AGE_DAYS:-}" ]]; then
  SCRAPE+=( --profile-max-age-days "$PROFILE_MAX_AGE_DAYS" )
fi

"${SCRAPE[@]}"
"$PY" scripts/datasources/naco/load_naco_to_bronze.py

echo "NACo all-states pipeline finished."
