#!/usr/bin/env bash
# Run dbt using the repo-root dbt_project.yml (for Cursor / IDE) while still loading
# profiles.yml from dbt_project/. Without DBT_PROFILES_DIR, dbt falls back to ~/.dbt
# and seeds/runs often hit a different database than Neon.
#
# Usage (from repo root):
#   ./scripts/dbt-root.sh seed --select jurisdiction_website_url_overrides
#   ./scripts/dbt-root.sh run --select int_jurisdiction_websites
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DBT_PROFILES_DIR="${ROOT}/dbt_project"
cd "${ROOT}"
exec "${ROOT}/.venv-dbt/bin/dbt" "$@"
