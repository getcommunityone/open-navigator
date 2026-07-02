#!/usr/bin/env bash
# National pipeline: catalog → captions → Gemini analyze for every jurisdiction
# with YouTube bronze rows (50 states + DC). Uses round-robin across states.
#
# Usage (repo root):
#   ./packages/scrapers/scripts/youtube_run_all_jurisdictions.sh
#   MAX_JURISDICTIONS=100 ./packages/scrapers/scripts/youtube_run_all_jurisdictions.sh
#   STATES=AL,GA,TX ./packages/scrapers/scripts/youtube_run_all_jurisdictions.sh
#
# Forwards env to youtube_run_priority_states_last_n.sh (N, DELAY, COOKIES, …).
# Step is always ``each`` (per jurisdiction: optional catalog → captions → analyze).

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
# load_youtube_events_to_postgres imports scripts.datasources.* (repo root).
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

WRAPPER="$ROOT/packages/scrapers/scripts/youtube_run_priority_states_last_n.sh"
LOG="${LOG:-/tmp/youtube-all-jurisdictions_$(date +%Y%m%d_%H%M%S).log}"

if [[ -z "${STATES:-}" ]]; then
  echo "Resolving state list from bronze.bronze_event_youtube…" | tee -a "$LOG"
  STATES="$(
    "$ROOT/.venv/bin/python" - <<'PY'
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(".env")
url = (
    os.environ.get("DATABASE_URL")
    or os.getenv("NEON_DATABASE_URL_DEV")
    or os.getenv("NEON_DATABASE_URL")
    or "postgresql://postgres:password@localhost:5433/open_navigator"
)
with psycopg2.connect(url) as conn, conn.cursor() as cur:
    cur.execute(
        """
        SELECT string_agg(DISTINCT state_code, ',' ORDER BY state_code)
        FROM bronze.bronze_event_youtube
        WHERE state_code IS NOT NULL AND btrim(state_code) <> ''
        """
    )
    row = cur.fetchone()
print(row[0] or "")
PY
  )"
fi

if [[ -z "${STATES:-}" ]]; then
  echo "No STATES resolved — set STATES=AL,GA,… or check DATABASE_URL." >&2
  exit 1
fi

export STATES
export BATCH_STATUS="${BATCH_STATUS:-1}"
export ROUND_ROBIN="${ROUND_ROBIN:-1}"

COUNT="$(
  STATES="$STATES" DATABASE_URL="${DATABASE_URL:-}" "$ROOT/.venv/bin/python" - <<'PY'
import os
from dotenv import load_dotenv

load_dotenv(".env")
states = [s.strip().upper() for s in os.environ["STATES"].split(",") if s.strip()]
url = (
    os.environ.get("DATABASE_URL")
    or os.getenv("NEON_DATABASE_URL_DEV")
    or os.getenv("NEON_DATABASE_URL")
)
from api.batch_jobs.batch_job_status import fetch_batch_plan_jurisdictions

runs = fetch_batch_plan_jurisdictions(states, round_robin=True, database_url=url)
print(len(runs))
PY
)"

{
  echo "=== youtube ALL jurisdictions $(date -Iseconds) ==="
  echo "states=$(echo "$STATES" | tr ',' '\n' | wc -l) jurisdictions=$COUNT"
  echo "N=${N:-10} DELAY=${DELAY:-10} MAX_JURISDICTIONS=${MAX_JURISDICTIONS:-unlimited}"
  echo "log=$LOG"
} | tee -a "$LOG"

if [[ "${COUNT:-0}" -eq 0 ]]; then
  echo "No jurisdictions in batch plan for STATES=$STATES" | tee -a "$LOG"
  exit 1
fi

exec >> >(tee -a "$LOG") 2>&1
"$WRAPPER" each

echo "=== DONE youtube ALL jurisdictions $(date -Iseconds) ==="
