#!/usr/bin/env bash
# Scrape NACo County Explorer → data/cache/naco, then bronze_jurisdictions_*_naco (see load_naco_to_bronze.py).
#
# Usage (from repo root, or any cwd — script cds to open-navigator root):
#   ./scripts/datasources/naco/run_naco_pipeline.sh
#   ./scripts/datasources/naco/run_naco_pipeline.sh AL,GA,MA
#
# Optional env:
#   STATES=AL,GA ./scripts/datasources/naco/run_naco_pipeline.sh
#   INCREMENTAL=1 ./scripts/datasources/naco/run_naco_pipeline.sh AL
#       (still uses --force so registry is rebuilt; profiles reused from same-day cache when fresh.)
#   For same-day cache-only refresh (no registry redownload): drop --force from SCRAPE below or run Python:
#     ./.venv/bin/python scripts/datasources/naco/scrape_naco_counties.py --incremental --states AL
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$ROOT"

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing ${PY} — run: python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

PICK="${1:-${STATES:-}}"

SCRAPE=( "$PY" scripts/datasources/naco/scrape_naco_counties.py --force )
LOAD=( "$PY" scripts/datasources/naco/load_naco_to_bronze.py )

if [[ -n "$PICK" ]]; then
  SCRAPE+=( --states "$PICK" )
  LOAD+=( --states "$PICK" )
fi

if [[ "${INCREMENTAL:-}" == "1" ]]; then
  SCRAPE+=( --incremental )
fi

"${SCRAPE[@]}"
"${LOAD[@]}"
echo "NACo pipeline finished."
