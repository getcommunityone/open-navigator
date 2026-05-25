#!/usr/bin/env bash
# Run jurisdiction pilot with live progress on stderr/stdout (no nohup).
#
# Usage (repo root):
#   ./scripts/datasources/jurisdiction_pilot/run_scrape_priority_states_terminal.sh
#
# Optional env:
#   STATES=AL,GA,IN,MA,WA,WI
#   INCLUDE_TYPES=county,municipality   # default: counties first
#   WORKERS=6
#   BATCH_ID=<uuid>          # resume
#   ELECTIONS=1              # pass --elections
#   COOKIES=youtube_cookies.txt
#   LOG_FILE=path.log        # also tee full output to this file
#   PROGRESS_EVERY=1         # log each jurisdiction (default 1 here; CLI default is 10)
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
set -a
[ -f .env ] && . ./.env
set +a
export PYTHONUNBUFFERED=1

STATES="${STATES:-AL,GA,IN,MA,WA,WI}"
INCLUDE_TYPES="${INCLUDE_TYPES:-county,municipality}"
WORKERS="${WORKERS:-6}"
COOKIES="${COOKIES:-youtube_cookies.txt}"
PROGRESS_EVERY="${PROGRESS_EVERY:-1}"

cmd=(
  .venv/bin/python -u -m scripts.datasources.jurisdiction_pilot.scrape_priority_states
  --states "$STATES"
  --include-types "$INCLUDE_TYPES"
  --workers "$WORKERS"
  --cookies "$COOKIES"
  --progress-every "$PROGRESS_EVERY"
)
[ -n "${BATCH_ID:-}" ] && cmd+=(--batch-id "$BATCH_ID")
[ "${ELECTIONS:-0}" = "1" ] && cmd+=(--elections)

echo ">>> ${cmd[*]}"
if [ -n "${LOG_FILE:-}" ]; then
  mkdir -p "$(dirname "$LOG_FILE")"
  "${cmd[@]}" 2>&1 | tee -a "$LOG_FILE"
else
  exec "${cmd[@]}"
fi
