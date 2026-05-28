#!/usr/bin/env bash
set -euo pipefail

# Repo root (this file: packages/scrapers/src/scrapers/wikidata/)
# For long unattended runs on priority dev USPS, use run_wikidata_priority_states_background.sh.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

if [[ ! -x "${ROOT}/.venv/bin/python" ]]; then
  echo "Missing ${ROOT}/.venv/bin/python — create the venv and pip install -r requirements.txt first." >&2
  exit 1
fi

exec "${ROOT}/.venv/bin/python" "${ROOT}/packages/scrapers/src/scrapers/wikidata/load_jurisdictions_wikidata.py" "$@"
