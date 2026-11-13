#!/usr/bin/env bash
# Run ACS downloader from repo root so ``config`` loads ``.env`` from the project root.
# Passes through all arguments (e.g. ``--all-years``, ``--force`` to retry failed/missing parquets).
#
#   chmod +x packages/scrapers/scripts/census_run_acs_download.sh
#   ./packages/scrapers/scripts/census_run_acs_download.sh --all-years
#   ./packages/scrapers/scripts/census_run_acs_download.sh --all-years --force
#   ./packages/scrapers/scripts/census_run_acs_download.sh --geography sduni --all-states --all-years

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
exec "${ROOT}/.venv/bin/python" "${ROOT}/packages/scrapers/src/scrapers/census/download_census_acs_data.py" "$@"
