#!/usr/bin/env bash
# Catalog + caption backfill + Gemini policy analysis for the last N uploads per
# jurisdiction in priority states (default N=2).
#
# Usage (repo root):
#   ./scripts/datasources/youtube/run_priority_states_last_n.sh
#   N=2 ./scripts/datasources/youtube/run_priority_states_last_n.sh catalog
#   N=2 ./scripts/datasources/youtube/run_priority_states_last_n.sh captions
#   N=2 ./scripts/datasources/youtube/run_priority_states_last_n.sh analyze
#   DAYS=7 N=2 ./scripts/datasources/youtube/run_priority_states_last_n.sh all
#
# Optional env:
#   STATES=AL,GA,IN,MA,MT,WA,WI
#   COOKIES=youtube_cookies.txt
#   DELAY=10
#   DRY_RUN=1          — print jurisdictions / dry-run loaders only
#   SKIP_CATALOG=1     — skip step 1
#   ROUND_ROBIN=0      — process state-by-state (default: interleave states for diversity)
#   DATABASE_URL=...   — override .env

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
STATES="${STATES:-AL,GA,IN,MA,MT,WA,WI}"
N="${N:-2}"
DAYS="${DAYS:-}"
COOKIES="${COOKIES:-youtube_cookies.txt}"
DELAY="${DELAY:-10}"
STEP="${1:-all}"

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing $PYTHON — create .venv first." >&2
  exit 1
fi

list_jurisdictions() {
  "$PYTHON" - <<'PY'
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv(".env")
states = [s.strip().upper() for s in os.environ["STATES"].split(",") if s.strip()]
url = (
    os.environ.get("DATABASE_URL")
    or os.getenv("NEON_DATABASE_URL_DEV")
    or os.getenv("NEON_DATABASE_URL")
)
if not url:
    sys.exit("Set DATABASE_URL or NEON_DATABASE_URL_DEV in .env")

with psycopg2.connect(url) as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute(
        """
        SELECT DISTINCT state_code, jurisdiction_id, jurisdiction_name
        FROM bronze.bronze_events_youtube
        WHERE state_code = ANY(%s)
          AND jurisdiction_id IS NOT NULL
          AND BTRIM(jurisdiction_id) <> ''
        ORDER BY state_code, jurisdiction_name
        """,
        (states,),
    )
    rows = cur.fetchall()

if not rows:
    sys.exit(f"No bronze YouTube jurisdictions for states: {', '.join(states)}")

round_robin = os.environ.get("ROUND_ROBIN", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)
if round_robin:
    from collections import defaultdict

    buckets: dict[str, list] = defaultdict(list)
    for r in rows:
        buckets[r["state_code"]].append(r)
    active = [s for s in states if buckets.get(s)]
    max_len = max((len(buckets[s]) for s in active), default=0)
    ordered: list = []
    for i in range(max_len):
        for s in active:
            if i < len(buckets[s]):
                ordered.append(buckets[s][i])
    rows = ordered

for r in rows:
    print(f"{r['state_code']}\t{r['jurisdiction_id']}\t{r['jurisdiction_name']}")
PY
}

run_catalog() {
  local -a extra=()
  if [[ -n "$DAYS" ]]; then
    extra+=(--days "$DAYS")
  fi
  local rr=1
  if [[ "${ROUND_ROBIN:-1}" =~ ^(0|false|no|off)$ ]]; then
    rr=0
  fi
  if [[ -n "${DRY_RUN:-}" ]]; then
    if [[ "$rr" -eq 1 ]]; then
      echo "[dry-run] catalog per jurisdiction (round-robin order), --max-videos $N ${extra[*]}"
      export STATES DATABASE_URL="${DATABASE_URL:-}" ROUND_ROBIN=1
      list_jurisdictions | while IFS=$'\t' read -r st jid name; do
        echo "  would catalog: $st $name ($jid)"
      done
    else
      echo "[dry-run] would run load_youtube_events_to_postgres --states $STATES --max-videos $N ${extra[*]} --skip-transcripts"
    fi
    return 0
  fi
  echo "=== Catalog: max $N video(s) per channel; states=$STATES ${DAYS:+(last $DAYS days)} ==="
  if [[ "$rr" -eq 0 ]]; then
    "$PYTHON" scripts/datasources/youtube/load_youtube_events_to_postgres.py \
      --states "$STATES" \
      --max-videos "$N" \
      --skip-transcripts \
      "${extra[@]}"
    return 0
  fi
  echo "=== Catalog order: round-robin across states ==="
  local st jid name
  while IFS=$'\t' read -r st jid name; do
    echo "--- Catalog: $st — $name ($jid) ---"
    "$PYTHON" scripts/datasources/youtube/load_youtube_events_to_postgres.py \
      --jurisdiction-id "$jid" \
      --max-videos "$N" \
      --skip-transcripts \
      "${extra[@]}" || echo "WARN: catalog failed for $jid" >&2
  done < <(export STATES DATABASE_URL="${DATABASE_URL:-}" ROUND_ROBIN=1; list_jurisdictions)
}

run_captions() {
  local jid st name
  while IFS=$'\t' read -r st jid name; do
    echo "=== Captions ($N newest): $st — $name ($jid) ==="
    local -a cmd=(
      scripts/datasources/youtube/backfill_jurisdiction_transcripts.py
      --jurisdiction-id "$jid"
      --newest "$N"
      --order-by published_at
      --delay "$DELAY"
    )
    if [[ -f "$COOKIES" ]]; then
      cmd+=(--cookies "$COOKIES")
    fi
    if [[ -n "${DRY_RUN:-}" ]]; then
      cmd+=(--dry-run)
    fi
    if ! "${cmd[@]/#/$PYTHON }"; then
      echo "WARN: captions failed for $jid" >&2
    fi
  done < <(export STATES DATABASE_URL="${DATABASE_URL:-}" ROUND_ROBIN="${ROUND_ROBIN:-1}"; list_jurisdictions)
}

run_analyze() {
  local jid st name
  while IFS=$'\t' read -r st jid name; do
    echo "=== Analyze ($N newest): $st — $name ($jid) ==="
    local -a cmd=(
      scripts/gemini/meeting_transcript_policy.py
      --newest "$N"
      --jurisdiction-id "$jid"
      --state "$st"
    )
    if [[ -n "${DRY_RUN:-}" ]]; then
      cmd+=(--dry-run)
    fi
    if ! "${cmd[@]/#/$PYTHON }"; then
      echo "WARN: analyze failed for $jid" >&2
    fi
  done < <(export STATES DATABASE_URL="${DATABASE_URL:-}" ROUND_ROBIN="${ROUND_ROBIN:-1}"; list_jurisdictions)
}

case "$STEP" in
  catalog) run_catalog ;;
  captions) run_captions ;;
  analyze) run_analyze ;;
  all)
    [[ -z "${SKIP_CATALOG:-}" ]] && run_catalog
    run_captions
    run_analyze
    ;;
  list)
    export STATES DATABASE_URL="${DATABASE_URL:-}" ROUND_ROBIN="${ROUND_ROBIN:-1}"
    list_jurisdictions
    ;;
  *)
    echo "Usage: $0 [catalog|captions|analyze|all|list]" >&2
    exit 1
    ;;
esac

echo "Done ($STEP, N=$N, states=$STATES)."
