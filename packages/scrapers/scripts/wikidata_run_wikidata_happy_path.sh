#!/usr/bin/env bash
set -euo pipefail

# Low-429 Wikidata jurisdiction load: enables ``--happy-path`` (see
# ``_apply_wikidata_happy_path_env_defaults`` in load_jurisdictions_wikidata.py).
# Fills ``WIKIDATA_HYBRID_ENRICH=1`` when unset (bulk id→Q + wbgetentities — not legacy FILTER batches).
# Uses one bulk WDQS query per state where applicable, slower spacing, no FILTER supplements
# for muni/school misses and no county wbsearchentities fallback — backfill later when WDQS is quiet.
#
# Examples:
#   ./packages/scrapers/src/scrapers/wikidata/run_wikidata_happy_path.sh --priority-states --types county,city
#   ./packages/scrapers/src/scrapers/wikidata/run_wikidata_happy_path.sh --states GA --types county
#
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

if [[ ! -x "${ROOT}/.venv/bin/python" ]]; then
  echo "Missing ${ROOT}/.venv/bin/python — create the venv and pip install -r requirements.txt first." >&2
  exit 1
fi

exec "${ROOT}/.venv/bin/python" "${ROOT}/packages/scrapers/src/scrapers/wikidata/load_jurisdictions_wikidata.py" --happy-path "$@"
