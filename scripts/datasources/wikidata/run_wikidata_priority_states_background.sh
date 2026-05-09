#!/usr/bin/env bash
# Load Wikidata for the six PRIORITY_STATES (AL, GA, IN, MA, WA, WI) with settings
# suited to long unattended runs on a VPS or workstation (not Colab).
#
# Usage:
#   ./scripts/datasources/wikidata/run_wikidata_priority_states_background.sh
#   RUN_FOREGROUND=1 ./scripts/datasources/wikidata/run_wikidata_priority_states_background.sh
#
# Logs: data/logs/wikidata_priority_<timestamp>.log
# Checkpoint: beside WIKIDATA_CACHE_DIR (default data/cache/wikidata/).
#
# Same DB URL must already have Census gazetteer bronze rows (+ *_wikidata shells):
#   scripts/deployment/neon/run_bronze_jurisdictions_to_cloud.sh
# CSV cache first: scripts/datasources/census/download_census_gazetteer.py
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing ${PY} — create .venv and pip install -r requirements.txt first." >&2
  exit 1
fi

SCRIPT="${ROOT}/scripts/datasources/wikidata/load_jurisdictions_wikidata.py"
LOG_DIR="${ROOT}/data/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/wikidata_priority_${STAMP}.log"
PID_FILE="${LOG_DIR}/wikidata_priority_latest.pid"

# Be polite to WDQS; override in your environment if needed.
export WIKIDATA_INCREMENTAL_MERGE="${WIKIDATA_INCREMENTAL_MERGE:-1}"
export WIKIDATA_THROTTLE_SECONDS="${WIKIDATA_THROTTLE_SECONDS:-10}"
export WIKIDATA_RETRY_AFTER_MAX_SECONDS="${WIKIDATA_RETRY_AFTER_MAX_SECONDS:-120}"
export WIKIDATA_TASK_SLEEP_SECONDS="${WIKIDATA_TASK_SLEEP_SECONDS:-4}"
export WIKIDATA_CACHE_TTL_SECONDS="${WIKIDATA_CACHE_TTL_SECONDS:-604800}"

LAUNCH=(
  "$PY" "$SCRIPT"
  --priority-states
  --types "${WIKIDATA_LOAD_TYPES:-city,county,state,school_district}"
  --incremental-merge
  --no-retry-county-gap-states
  --no-all-us-states
  --no-force
)

echo "Logging to: $LOG_FILE"
printf '%s\n' "Command: ${LAUNCH[*]}" | tee "$LOG_FILE"

if [[ "${RUN_FOREGROUND:-0}" == "1" ]] || [[ "${RUN_FOREGROUND:-}" == "true" ]]; then
  exec "${LAUNCH[@]}" 2>&1 | tee -a "$LOG_FILE"
else
  nohup "${LAUNCH[@]}" >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  echo "Started PID $(cat "$PID_FILE") (saved to $PID_FILE). Tail: tail -f $LOG_FILE"
fi
