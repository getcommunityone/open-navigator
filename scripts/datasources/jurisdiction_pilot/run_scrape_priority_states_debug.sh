#!/usr/bin/env bash
# Verbose pilot run for debugging (single worker, every jurisdiction logged, YouTube DEBUG).
#
# Examples (repo root):
#   # One county by id
#   JURISDICTION_ID=county_13095 STATES=GA ./scripts/datasources/jurisdiction_pilot/run_scrape_priority_states_debug.sh
#
#   # First 5 counties in GA (default include-types), no elections
#   STATES=GA INCLUDE_TYPES=county LIMIT_PER_STATE=5 SKIP_ELECTIONS=1 \
#     ./scripts/datasources/jurisdiction_pilot/run_scrape_priority_states_debug.sh
#
#   # One city after counties are done
#   JURISDICTION_ID=abbeville_0100124 STATES=AL INCLUDE_TYPES=municipality SKIP_ELECTIONS=1 \
#     ./scripts/datasources/jurisdiction_pilot/run_scrape_priority_states_debug.sh
#
# Env:
#   STATES, INCLUDE_TYPES, JURISDICTION_ID (comma-separated ok)
#   LIMIT_PER_STATE, WORKERS (default 1), COOKIES
#   SKIP_ELECTIONS=1 | ELECTIONS=1
#   SKIP_IMAGES=1 | SKIP_YOUTUBE=1
#   MIN_CHANNEL_CONFIDENCE=0   # audit: keep all YouTube candidates in bronze
#   HTTP_DEBUG=1             # log every requests/urllib3 line
#   LOG_FILE=path            # tee stdout/stderr
#   NEW_BATCH=1              # ignore BATCH_ID; start fresh checkpoint uuid
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
set -a
[ -f .env ] && . ./.env
set +a
export PYTHONUNBUFFERED=1

STATES="${STATES:-GA}"
INCLUDE_TYPES="${INCLUDE_TYPES:-county}"
WORKERS="${WORKERS:-1}"
COOKIES="${COOKIES:-youtube_cookies.txt}"
MIN_CHANNEL_CONFIDENCE="${MIN_CHANNEL_CONFIDENCE:-0}"

cmd=(
  .venv/bin/python -u -m scripts.datasources.jurisdiction_pilot.scrape_priority_states
  --states "$STATES"
  --include-types "$INCLUDE_TYPES"
  --workers "$WORKERS"
  --cookies "$COOKIES"
  --progress-every 1
  --verbose
  --youtube-debug
  --min-channel-confidence "$MIN_CHANNEL_CONFIDENCE"
)

[ -n "${LIMIT_PER_STATE:-}" ] && cmd+=(--limit-per-state "$LIMIT_PER_STATE")
[ -n "${JURISDICTION_ID:-}" ] && cmd+=(--jurisdiction-id "$JURISDICTION_ID")
[ "${NEW_BATCH:-0}" != "1" ] && [ -n "${BATCH_ID:-}" ] && cmd+=(--batch-id "$BATCH_ID")
[ "${SKIP_ELECTIONS:-0}" = "1" ] || [ "${ELECTIONS:-0}" = "1" ] && true
if [ "${SKIP_ELECTIONS:-0}" != "1" ] && [ "${ELECTIONS:-0}" = "1" ]; then
  cmd+=(--elections)
fi
[ "${SKIP_IMAGES:-0}" = "1" ] && cmd+=(--skip-images)
[ "${SKIP_YOUTUBE:-0}" = "1" ] && cmd+=(--skip-youtube)
[ "${HTTP_DEBUG:-0}" = "1" ] && cmd+=(--http-debug)

echo ">>> ${cmd[*]}"
if [ -n "${LOG_FILE:-}" ]; then
  mkdir -p "$(dirname "$LOG_FILE")"
  "${cmd[@]}" 2>&1 | tee -a "$LOG_FILE"
else
  exec "${cmd[@]}"
fi
