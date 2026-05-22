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
#   N=2 ./scripts/datasources/youtube/run_priority_states_last_n.sh each
#     — round-robin jurisdictions: captions then analyze per place, then next
#
# Optional env:
#   STATES=AL,GA,IN,MA,MT,WA,WI
#   COOKIES=youtube_cookies.txt
#   DELAY=10
#   MAX_JURISDICTIONS=50   — cap per run (round-robin order preserved)
#   NO_CLEAR_TOMBSTONES=1  — pass --no-clear-tombstones (avoid retrying old permanent misses)
#   SKIP_PROBE=1           — pass --skip-probe (faster; fewer per-jurisdiction probe calls)
#   PROXY=http://user:pass@host:port  — pass --proxy to caption backfill (or YOUTUBE_TRANSCRIPT_PROXY)
#   DRY_RUN=1          — print jurisdictions / dry-run loaders only
#   SKIP_CATALOG=1     — skip step 1
#   CATALOG_FORCE=1    — pass --force (last N videos, not incremental-only-after-last insert)
#   CATALOG_YTDLP=1    — unset YOUTUBE_API_KEY for catalog (avoid googleapis.com hangs; use yt-dlp)
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
MAX_JURISDICTIONS="${MAX_JURISDICTIONS:-}"
PROXY_ARG="${PROXY:-${YOUTUBE_TRANSCRIPT_PROXY:-}}"

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing $PYTHON — create .venv first." >&2
  exit 1
fi

format_duration() {
  local total_sec="${1:-0}"
  if [[ "$total_sec" -lt 0 ]]; then
    total_sec=0
  fi
  local h=$(( total_sec / 3600 ))
  local m=$(( (total_sec % 3600) / 60 ))
  local s=$(( total_sec % 60 ))
  printf '%02d:%02d:%02d' "$h" "$m" "$s"
}

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
    local -a cat_args=(
      --states "$STATES"
      --max-videos "$N"
      --skip-transcripts
    )
    [[ -n "${CATALOG_FORCE:-}" ]] && cat_args+=(--force)
    "$PYTHON" scripts/datasources/youtube/load_youtube_events_to_postgres.py \
      "${cat_args[@]}" \
      "${extra[@]}"
    return 0
  fi
  echo "=== Catalog order: round-robin across states ==="
  local st jid name
  while IFS=$'\t' read -r st jid name; do
    echo "--- Catalog: $st — $name ($jid) ---"
    local -a cat_argv=(--jurisdiction-id "$jid" --max-videos "$N" --skip-transcripts)
    [[ -n "${CATALOG_FORCE:-}" ]] && cat_argv+=(--force)
    if [[ -n "${CATALOG_YTDLP:-}" ]]; then
      env -u YOUTUBE_API_KEY "$PYTHON" scripts/datasources/youtube/load_youtube_events_to_postgres.py \
        "${cat_argv[@]}" "${extra[@]}" || echo "WARN: catalog failed for $jid" >&2
    else
      "$PYTHON" scripts/datasources/youtube/load_youtube_events_to_postgres.py \
        "${cat_argv[@]}" "${extra[@]}" || echo "WARN: catalog failed for $jid" >&2
    fi
  done < <(export STATES DATABASE_URL="${DATABASE_URL:-}" ROUND_ROBIN=1; list_jurisdictions)
}

run_captions() {
  local jid st name
  local processed=0
  local success=0
  local failed=0
  local -a rows=()
  mapfile -t rows < <(export STATES DATABASE_URL="${DATABASE_URL:-}" ROUND_ROBIN="${ROUND_ROBIN:-1}"; list_jurisdictions)

  if (( ${#rows[@]} == 0 )); then
    echo "No jurisdictions found for captions step."
    return 0
  fi

  local target_total="${#rows[@]}"
  if [[ -n "$MAX_JURISDICTIONS" ]] && (( MAX_JURISDICTIONS < target_total )); then
    target_total="$MAX_JURISDICTIONS"
  fi

  local start_ts
  start_ts="$(date +%s)"
  echo "=== Captions batch: target jurisdictions=$target_total (states=$STATES, N=$N) ==="

  for row in "${rows[@]}"; do
    IFS=$'\t' read -r st jid name <<< "$row"
    if [[ -n "$MAX_JURISDICTIONS" ]] && (( processed >= MAX_JURISDICTIONS )); then
      echo "Reached MAX_JURISDICTIONS=$MAX_JURISDICTIONS; stopping captions step early."
      break
    fi
    local idx=$((processed + 1))
    echo "=== Captions ($N newest) [$idx/$target_total]: $st — $name ($jid) ==="
    local -a cap_args=(
      --jurisdiction-id "$jid"
      --state "$st"
      --newest "$N"
      --order-by published_at
      --delay "$DELAY"
    )
    if [[ -n "${NO_CLEAR_TOMBSTONES:-}" ]]; then
      cap_args+=(--no-clear-tombstones)
    fi
    if [[ -n "${SKIP_PROBE:-}" ]]; then
      cap_args+=(--skip-probe)
    fi
    if [[ -f "$COOKIES" ]]; then
      cap_args+=(--cookies "$COOKIES")
    fi
    if [[ -n "$PROXY_ARG" ]]; then
      cap_args+=(--proxy "$PROXY_ARG")
    fi
    if [[ -n "${DRY_RUN:-}" ]]; then
      cap_args+=(--dry-run)
    fi
    if ! "$PYTHON" scripts/datasources/youtube/backfill_jurisdiction_transcripts.py "${cap_args[@]}"; then
      ((failed+=1))
      echo "WARN: captions failed for $jid" >&2
    else
      ((success+=1))
    fi
    ((processed+=1))

    local now elapsed remaining avg_per eta
    now="$(date +%s)"
    elapsed=$((now - start_ts))
    remaining=$((target_total - processed))
    if (( remaining < 0 )); then
      remaining=0
    fi
    avg_per=0
    eta=0
    if (( processed > 0 )); then
      avg_per=$((elapsed / processed))
      eta=$((avg_per * remaining))
    fi
    echo "--- Progress: done=$processed/$target_total success=$success failed=$failed remaining=$remaining elapsed=$(format_duration "$elapsed") eta=$(format_duration "$eta")"
  done

  echo "=== Captions complete: processed=$processed success=$success failed=$failed target=$target_total ==="
}

run_analyze() {
  local jid st name
  while IFS=$'\t' read -r st jid name; do
    echo "=== Analyze ($N newest): $st — $name ($jid) ==="
    local -a ana_args=(
      --newest "$N"
      --jurisdiction-id "$jid"
      --state "$st"
    )
    if [[ -n "${DRY_RUN:-}" ]]; then
      ana_args+=(--dry-run)
    fi
    if ! "$PYTHON" scripts/gemini/meeting_transcript_policy.py "${ana_args[@]}"; then
      ec=$?
      if [[ $ec -eq 1 ]]; then
        echo "WARN: analyze skipped for $jid (usually no captions yet — run: $0 captions)" >&2
      else
        echo "WARN: analyze failed for $jid (exit $ec)" >&2
      fi
    fi
  done < <(export STATES DATABASE_URL="${DATABASE_URL:-}" ROUND_ROBIN="${ROUND_ROBIN:-1}"; list_jurisdictions)
}

# One jurisdiction at a time (round-robin list order): catalog (optional) → captions → analyze.
run_each_jurisdiction() {
  local -a cat_extra=()
  local processed=0
  if [[ -n "$DAYS" ]]; then
    cat_extra+=(--days "$DAYS")
  fi
  local st jid name
  while IFS=$'\t' read -r st jid name; do
    if [[ -n "$MAX_JURISDICTIONS" ]] && (( processed >= MAX_JURISDICTIONS )); then
      echo "Reached MAX_JURISDICTIONS=$MAX_JURISDICTIONS; stopping each step early."
      break
    fi
    echo "=== Pipeline ($N newest): $st — $name ($jid) ==="
    if [[ -z "${SKIP_CATALOG:-}" ]]; then
      if [[ -n "${DRY_RUN:-}" ]]; then
        echo "  [dry-run] catalog --max-videos $N ${cat_extra[*]}"
      else
        echo "--- Catalog: $st — $name ($jid) ---"
        local -a cat_argv=(
          --jurisdiction-id "$jid"
          --max-videos "$N"
          --skip-transcripts
        )
        [[ -n "${CATALOG_FORCE:-}" ]] && cat_argv+=(--force)
        if [[ -n "${CATALOG_YTDLP:-}" ]]; then
          env -u YOUTUBE_API_KEY "$PYTHON" scripts/datasources/youtube/load_youtube_events_to_postgres.py \
            "${cat_argv[@]}" "${cat_extra[@]}" || echo "WARN: catalog failed for $jid" >&2
        else
          "$PYTHON" scripts/datasources/youtube/load_youtube_events_to_postgres.py \
            "${cat_argv[@]}" "${cat_extra[@]}" || echo "WARN: catalog failed for $jid" >&2
        fi
      fi
    fi
    echo "--- Captions: $st — $name ($jid) ---"
    local -a cap_args=(
      --jurisdiction-id "$jid"
      --state "$st"
      --newest "$N"
      --order-by published_at
      --delay "$DELAY"
    )
    if [[ -n "${NO_CLEAR_TOMBSTONES:-}" ]]; then
      cap_args+=(--no-clear-tombstones)
    fi
    if [[ -n "${SKIP_PROBE:-}" ]]; then
      cap_args+=(--skip-probe)
    fi
    if [[ -f "$COOKIES" ]]; then
      cap_args+=(--cookies "$COOKIES")
    fi
    if [[ -n "$PROXY_ARG" ]]; then
      cap_args+=(--proxy "$PROXY_ARG")
    fi
    if [[ -n "${DRY_RUN:-}" ]]; then
      cap_args+=(--dry-run)
    elif ! "$PYTHON" scripts/datasources/youtube/backfill_jurisdiction_transcripts.py "${cap_args[@]}"; then
      echo "WARN: captions failed for $jid" >&2
    fi
    echo "--- Analyze: $st — $name ($jid) ---"
    local -a ana_args=(
      --newest "$N"
      --jurisdiction-id "$jid"
      --state "$st"
    )
    if [[ -n "${DRY_RUN:-}" ]]; then
      ana_args+=(--dry-run)
    elif ! "$PYTHON" scripts/gemini/meeting_transcript_policy.py "${ana_args[@]}"; then
      ec=$?
      if [[ $ec -eq 1 ]]; then
        echo "WARN: analyze skipped for $jid (usually no captions yet)" >&2
      else
        echo "WARN: analyze failed for $jid (exit $ec)" >&2
      fi
    fi
    ((processed+=1))
  done < <(export STATES DATABASE_URL="${DATABASE_URL:-}" ROUND_ROBIN="${ROUND_ROBIN:-1}"; list_jurisdictions)
}

case "$STEP" in
  catalog) run_catalog ;;
  captions) run_captions ;;
  analyze) run_analyze ;;
  each) run_each_jurisdiction ;;
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
    echo "Usage: $0 [catalog|captions|analyze|each|all|list]" >&2
    echo "  each — round-robin: per jurisdiction, captions then analyze, then next" >&2
    exit 1
    ;;
esac

echo "Done ($STEP, N=$N, states=$STATES)."
