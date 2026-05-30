#!/usr/bin/env bash
# Load Open States jurisdictions into bronze + rebuild int_jurisdictions via dbt.
#
# Uses the project virtualenv when present (same pattern as packages/hosting/scripts/neon/run_jurisdiction_id_migration.sh).
#
# Usage:
#   ./scripts/datasources/openstates/run_openstates_jurisdiction_mapping.sh --migrate
#   ./scripts/datasources/openstates/run_openstates_jurisdiction_mapping.sh --dry-run
#
# Prereqs:
#   pip install -r requirements.txt           # main app / loaders (.venv)
#   ./scripts/datasources/openstates/setup_dbt_venv.sh   # isolated dbt (.venv-dbt — avoids protobuf/pathspec clashes)
#   OPENSTATES_DATABASE_URL, OPEN_NAVIGATOR_DATABASE_URL / NEON_DATABASE_URL_DEV / NEON_DATABASE_URL
#   First-time dbt config:
#     mkdir -p ~/.dbt && cp --update=none dbt_project/profiles.yml.example ~/.dbt/profiles.yml || true
#     edit ~/.dbt/profiles.yml
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
cd "${ROOT}"

if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi

if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PY="${ROOT}/.venv/bin/python"
elif [[ -x "${ROOT}/venv/bin/python" ]]; then
  PY="${ROOT}/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="$(command -v python3)"
else
  echo "ERROR: No Python found. Example: cd ${ROOT} && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

if [[ -x "${ROOT}/.venv-dbt/bin/dbt" ]]; then
  DBT="${ROOT}/.venv-dbt/bin/dbt"
elif [[ -x "${ROOT}/.venv/bin/dbt" ]]; then
  DBT="${ROOT}/.venv/bin/dbt"
elif command -v dbt >/dev/null 2>&1; then
  DBT="$(command -v dbt)"
else
  echo "ERROR: dbt not found. Create isolated venv (recommended):" >&2
  echo "  ${ROOT}/scripts/datasources/openstates/setup_dbt_venv.sh" >&2
  exit 1
fi

RUN_DBT=1
for arg in "$@"; do
  if [[ "$arg" == "--dry-run" || "$arg" == "-h" || "$arg" == "--help" ]]; then
    RUN_DBT=0
    break
  fi
done

"${PY}" "${ROOT}/scripts/datasources/openstates/map_openstates_jurisdiction_ids.py" "$@"

if [[ "${RUN_DBT}" -eq 1 ]]; then
  mkdir -p "${HOME}/.dbt"
  (cd "${ROOT}/dbt_project" && "${DBT}" run -s int_jurisdictions)
fi
