#!/usr/bin/env bash
# Delegate to repo-root scripts/dbt.sh (run from dbt_project without cd ..).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec "${ROOT}/scripts/dbt.sh" "$@"
