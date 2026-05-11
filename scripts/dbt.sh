#!/usr/bin/env bash
# Run dbt from repo root. The dbt project lives in dbt_project/.
#
# Usage (from repo root):
#   ./scripts/dbt.sh compile --select int_jurisdiction_websites
#   ./scripts/dbt.sh run
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}/dbt_project"
exec "${ROOT}/.venv-dbt/bin/dbt" "$@"
