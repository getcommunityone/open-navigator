#!/usr/bin/env bash
# NACo end-to-end: scrape county officials (FETCH) then land to bronze (LAND).
#
# Usage (repo root):
#   ./packages/scrapers/scripts/run_naco.sh                 # all states
#   ./packages/scrapers/scripts/run_naco.sh AL,GA,MA        # subset
#   STATES=AL,GA ./packages/scrapers/scripts/run_naco.sh
#   INCREMENTAL=1 ./packages/scrapers/scripts/run_naco.sh AL
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
PY="${PY:-./.venv/bin/python}"
if [[ ! -x "$PY" ]]; then
  echo "Missing ${PY} — run: python3 -m venv .venv && ./.venv/bin/pip install -e packages/scrapers -e packages/ingestion" >&2
  exit 1
fi

PICK="${1:-${STATES:-}}"

# FETCH: scrape -> data/cache/naco/  (was scripts/datasources/naco/scrape_naco_counties.py)
SCRAPE=( "$PY" -m scrapers.naco.scrape_counties --force )
# LAND: data/cache/naco/ -> bronze  (ported to ingestion.naco.counties)
LOAD=( "$PY" -m ingestion.naco.counties )

if [[ -n "$PICK" ]]; then
  SCRAPE+=( --states "$PICK" )
  LOAD+=( --states "$PICK" )
fi

if [[ "${INCREMENTAL:-}" == "1" ]]; then
  SCRAPE+=( --incremental )
fi

"${SCRAPE[@]}"
"${LOAD[@]}"
