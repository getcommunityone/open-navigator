#!/usr/bin/env bash
# Re-run municipality Wikidata for states with no *_wikidata shells (e.g. VT, WA, WV, WY).
#
# Pipeline per state batch:
#   1. Ensure bronze *_wikidata DDL
#   2. Seed municipality *_wikidata rows from Census gazetteer
#   3. Stamp wikidata_id from fips_gnis_map.parquet (no WDQS)
#   4. Hydrate official_website via wbgetentities
#
# Usage:
#   ./packages/scrapers/src/scrapers/wikidata/run_municipality_websites_gap_states.sh
#   ./packages/scrapers/src/scrapers/wikidata/run_municipality_websites_gap_states.sh --states VT,WA,WV,WY
#   ./packages/scrapers/src/scrapers/wikidata/run_municipality_websites_gap_states.sh --discover
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing ${PY}" >&2
  exit 1
fi

export WIKIDATA_HTTPS_PROXY="${WIKIDATA_HTTPS_PROXY:-}"
export WIKIDATA_HTTP_PROXY="${WIKIDATA_HTTP_PROXY:-}"

STATES="${GAP_STATES:-VT,WA,WV,WY}"
DISCOVER=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --states)
      STATES="$2"
      shift 2
      ;;
    --discover)
      DISCOVER=1
      shift
      ;;
    -h|--help)
      sed -n '1,22p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

if [[ "${DISCOVER}" == "1" ]]; then
  STATES="$("$PY" "${ROOT}/packages/scrapers/src/scrapers/wikidata/discover_municipality_website_gaps.py" --mode no_wikidata)"
fi

if [[ -z "${STATES// }" ]]; then
  echo "No gap states found (nothing to do)." >&2
  exit 0
fi

echo "Municipality gap states: ${STATES}"
echo "Log dir: ${ROOT}/data/logs"

"$PY" "${ROOT}/scripts/deployment/neon/ensure_bronze_jurisdictions_cloud.py" --schema-only

export GAP_RUN_STATES="${STATES}"
export OPEN_NAVIGATOR_ROOT="${ROOT}"

echo "=== Seeding bronze.bronze_jurisdictions_municipalities_wikidata from Census ==="
"$PY" -c "
import os, sys
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(os.environ['OPEN_NAVIGATOR_ROOT'])
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')
from scrapers.wikidata.load_jurisdictions_wikidata import DATABASE_URL, JurisdictionsWikiDataLoader
states = [s.strip().upper() for s in os.environ['GAP_RUN_STATES'].split(',') if s.strip()]
loader = JurisdictionsWikiDataLoader(DATABASE_URL)
try:
    for us in states:
        loader._seed_wikidata_table(us, 'city')
        print(f'  seeded {us}')
    loader.conn.commit()
finally:
    loader.close()
"

PARQUET="${ROOT}/data/cache/wikidata/fips_gnis_map.parquet"
if [[ -f "${PARQUET}" ]]; then
  echo "=== Stamping wikidata_id from parquet ==="
  "$PY" "${ROOT}/packages/scrapers/src/scrapers/wikidata/warm_geography_cache_from_parquet.py" \
    --apply-bronze --states "${STATES}" --types city
else
  echo "WARN: ${PARQUET} missing — skip parquet Q-id stamp; hydrate may still WDQS-map." >&2
fi

echo "=== Hydrating official_website (wbgetentities) ==="
"$PY" "${ROOT}/packages/scrapers/src/scrapers/wikidata/hydrate_municipality_websites_from_wikidata.py" \
  --states "${STATES}" \
  --force

echo "Done. Re-run your coverage SQL to verify pct_in_wikidata / pct_with_url for: ${STATES}"
