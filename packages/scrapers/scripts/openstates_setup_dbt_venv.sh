#!/usr/bin/env bash
# Create an isolated virtualenv for dbt only (recommended).
# Keeps protobuf/pathspec/click compatible with the main .venv (grpc, black, mypy, google-generativeai).
#
# Usage (from repo root):
#   ./scripts/datasources/openstates/setup_dbt_venv.sh
#
# Then run the mapping pipeline; it prefers .venv-dbt/bin/dbt automatically.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT}"

PY="python3"
if ! command -v "${PY}" >/dev/null 2>&1; then
  echo "ERROR: python3 not found" >&2
  exit 1
fi

if [[ ! -d "${ROOT}/.venv-dbt" ]]; then
  "${PY}" -m venv "${ROOT}/.venv-dbt"
fi

"${ROOT}/.venv-dbt/bin/pip" install -U pip wheel
"${ROOT}/.venv-dbt/bin/pip" install -r "${ROOT}/requirements-dbt.txt"

echo ""
echo "OK: dbt is in ${ROOT}/.venv-dbt/bin/dbt"
"${ROOT}/.venv-dbt/bin/dbt" --version
