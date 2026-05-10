#!/usr/bin/env bash
# If you ran: .venv/bin/pip install -r requirements-dbt.txt
# your main venv may have protobuf 6 + pathspec 0.12 (breaks grpc, Gemini client, black, mypy).
#
# This script removes dbt packages from .venv and restores common pins for the rest of the stack.
# Afterward use .venv-dbt for dbt: ./scripts/datasources/openstates/setup_dbt_venv.sh
#
# Usage (from repo root):
#   ./scripts/datasources/openstates/repair_main_venv_after_dbt_conflict.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
VPIP="${ROOT}/.venv/bin/pip"

if [[ ! -x "${VPIP}" ]]; then
  echo "ERROR: ${VPIP} not found" >&2
  exit 1
fi

echo "==> Uninstalling dbt-related packages from .venv (if any) ..."
mapfile -t DBT_PKGS < <("${VPIP}" freeze | awk -F= '/^dbt-/ {print $1}' || true)
if [[ ${#DBT_PKGS[@]} -gt 0 ]]; then
  "${VPIP}" uninstall -y "${DBT_PKGS[@]}" || true
else
  echo "    (none found)"
fi

echo "==> Restoring protobuf / pathspec / click pins compatible with grpc + black + mypy ..."
"${VPIP}" install 'protobuf>=5.26.1,<6' 'pathspec>=1.1.0' 'click>=8.1.7,<8.3'

echo ""
echo "OK. Run: ./scripts/datasources/openstates/setup_dbt_venv.sh"
echo "Then:  ./scripts/datasources/openstates/run_openstates_jurisdiction_mapping.sh --migrate"
