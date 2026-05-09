#!/usr/bin/env bash
set -euo pipefail

# Repo root (this file: scripts/datasources/wikidata/)
# For long unattended runs on six priority USPS, use run_wikidata_priority_states_background.sh.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

if [[ ! -x "${ROOT}/.venv/bin/python" ]]; then
  echo "Missing ${ROOT}/.venv/bin/python — create the venv and pip install -r requirements.txt first." >&2
  exit 1
fi

exec "${ROOT}/.venv/bin/python" "${ROOT}/scripts/datasources/wikidata/load_jurisdictions_wikidata.py" "$@"
