#!/usr/bin/env bash
# Hydrate official_website on bronze.bronze_jurisdictions_counties_wikidata (wbgetentities).
# Writes a JSON summary under data/logs/county_website_hydrate_*.json
#
# Examples:
#   ./scripts/datasources/wikidata/run_hydrate_county_websites.sh --states AL
#   ./scripts/datasources/wikidata/run_hydrate_county_websites.sh --priority-states
#   ./scripts/datasources/wikidata/run_hydrate_county_websites.sh --all-us-states --force
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing ${PY} — create .venv and pip install -r requirements.txt first." >&2
  exit 1
fi

export WIKIDATA_HTTPS_PROXY="${WIKIDATA_HTTPS_PROXY:-}"
export WIKIDATA_HTTP_PROXY="${WIKIDATA_HTTP_PROXY:-}"

exec "$PY" "${ROOT}/scripts/datasources/wikidata/hydrate_county_websites_from_wikidata.py" "$@"
