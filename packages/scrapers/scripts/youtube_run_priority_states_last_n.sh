#!/usr/bin/env bash
# Catalog + caption backfill + Gemini policy analysis for the last N uploads per
# jurisdiction in priority states (default N=10; override with N= env).
#
# Usage (repo root):
#   ./packages/scrapers/src/scrapers/youtube/run_priority_states_last_n.sh
#   ./packages/scrapers/src/scrapers/youtube/run_priority_states_last_n.sh catalog
#   ./packages/scrapers/src/scrapers/youtube/run_priority_states_last_n.sh captions
#   ./packages/scrapers/src/scrapers/youtube/run_priority_states_last_n.sh analyze
#   DAYS=7 ./packages/scrapers/src/scrapers/youtube/run_priority_states_last_n.sh all
#   ./packages/scrapers/src/scrapers/youtube/run_priority_states_last_n.sh each
#     — round-robin jurisdictions: captions then analyze per place, then next
#
# Optional env:
#   STATES=AL,GA,IN,MA,MT,WA,WI
#   N=10                 — newest N videos for captions/analyze per jurisdiction (default 10)
#   MAX_VIDEOS=100       — event catalog: max videos per channel/jurisdiction (default: N)
#   CATALOG_N=           — alias for MAX_VIDEOS
#   BATCH_STATUS=0       — disable batch job JSON + dashboard updates
#   COOKIES=youtube_cookies.txt
#   DELAY=10
#   MAX_JURISDICTIONS=50   — cap per run (round-robin order preserved)
#   PARALLEL=4             — analyze step only: run up to N jurisdictions at once
#                            (each is its own Gemini process; ceiling is the API rate
#                            limit, not CPU). Default 1 = sequential. Output interleaves.
#   NO_CLEAR_TOMBSTONES=1  — pass --no-clear-tombstones (avoid retrying old permanent misses)
#   NO_TOMBSTONES=1        — pass --no-tombstones (do not write new tombstone:* rows)
#   NO_PREFER_UNTRIED=1    — pass --no-prefer-untried (retry order by date only)
#   SKIP_PROBE=1           — pass --skip-probe (faster; fewer per-jurisdiction probe calls)
#   PROXY=http://user:pass@host:port  — pass --proxy to caption backfill (or YOUTUBE_TRANSCRIPT_PROXY)
#   TRANSCRIPT_SOURCE=ytdlp-only       — skip youtube-transcript-api; use yt-dlp subtitles only
#   YOUTUBE_USE_WEBSHARE=0           — opt out of Webshare (direct egress + cookies)
#   DRY_RUN=1          — print jurisdictions / dry-run loaders only
#   SKIP_CATALOG=1     — skip step 1
#   CATALOG_FORCE=1    — pass --force (last N videos, not incremental-only-after-last insert)
#   CATALOG_YTDLP=1    — unset YOUTUBE_API_KEY for catalog (avoid googleapis.com hangs; use yt-dlp)
#   CHANNEL_SOURCE=    — override per-jurisdiction catalog source (auto|counties-scraped|municipalities-scraped)
#   ROUND_ROBIN=0      — process state-by-state (default: interleave states for diversity)
#   DATABASE_URL=...   — override .env

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
# Webshare on by default when PROXY_USER_NAME / PROXY_PASSWORD are set (see transcript_api_client).
if [[ "${YOUTUBE_USE_WEBSHARE:-}" == "0" ]]; then
  export YOUTUBE_USE_WEBSHARE=0
else
  unset YOUTUBE_USE_WEBSHARE
fi

PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
STATES="${STATES:-AL,GA,IN,MA,MT,WA,WI}"
N="${N:-10}"
MAX_VIDEOS="${MAX_VIDEOS:-${CATALOG_N:-$N}}"
DAYS="${DAYS:-}"
COOKIES="${COOKIES:-youtube_cookies.txt}"
DELAY="${DELAY:-10}"
STEP="${1:-all}"
MAX_JURISDICTIONS="${MAX_JURISDICTIONS:-}"
PARALLEL="${PARALLEL:-1}"
if ! [[ "$PARALLEL" =~ ^[0-9]+$ ]] || (( PARALLEL < 1 )); then
  PARALLEL=1
fi
PROXY_ARG="${PROXY:-${YOUTUBE_TRANSCRIPT_PROXY:-}}"

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing $PYTHON — create .venv first." >&2
  exit 1
fi

batch_dashboard_refresh() {
  if [[ -n "${BATCH_STATUS:-}" && "${BATCH_STATUS}" == "0" ]]; then
    return 0
  fi
  "$PYTHON" packages/scrapers/src/scrapers/youtube/batch_job_dashboard.py --build --no-refresh-files 2>/dev/null || true
}

batch_start() {
  local step="$1"
  local total="$2"
  if [[ -n "${BATCH_STATUS:-}" && "${BATCH_STATUS}" == "0" ]]; then
    BATCH_JOB_ID=""
    return 0
  fi
  local rr=1
  if [[ "${ROUND_ROBIN:-1}" =~ ^(0|false|no|off)$ ]]; then
    rr=0
  fi
  BATCH_JOB_ID="$("$PYTHON" packages/scrapers/src/scrapers/youtube/batch_job_status.py start \
    --step "$step" \
    --states "$STATES" \
    --n "$N" \
    --delay "$DELAY" \
    --total-jurisdictions "$total" \
    --transcript-source "${TRANSCRIPT_SOURCE:-auto}" \
    --max-jurisdictions "${MAX_JURISDICTIONS:-0}" \
    --round-robin "$rr")"
  export BATCH_JOB_ID
  echo "Batch job: $BATCH_JOB_ID"
  batch_dashboard_refresh
}

batch_finish() {
  local status="${1:-completed}"
  if [[ -z "${BATCH_JOB_ID:-}" ]]; then
    return 0
  fi
  "$PYTHON" packages/scrapers/src/scrapers/youtube/batch_job_status.py finish \
    --batch-id "$BATCH_JOB_ID" --status "$status" || true
  batch_dashboard_refresh
  echo "Dashboard: /data-explorer/batch-jobs (React app; API reads data/cache/batch_jobs/)"
}

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

# Per-jurisdiction catalog: cities must use municipalities-scraped, counties use counties-scraped.
resolve_catalog_channel_source() {
  local jtype="${1:-}"
  if [[ -n "${CHANNEL_SOURCE:-}" ]]; then
    echo "$CHANNEL_SOURCE"
    return 0
  fi
  jtype="${jtype,,}"
  if [[ "$jtype" == "county" ]]; then
    echo "counties-scraped"
  elif [[ -n "$jtype" && "$jtype" != "unknown" ]]; then
    echo "municipalities-scraped"
  else
    echo "auto"
  fi
}

list_jurisdictions() {
  "$PYTHON" - <<'PY'
import os
import sys
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

round_robin = os.environ.get("ROUND_ROBIN", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)

from api.batch_jobs.batch_job_status import fetch_batch_plan_jurisdictions

runs = fetch_batch_plan_jurisdictions(
    states,
    round_robin=round_robin,
    database_url=url,
)
if not runs:
    sys.exit(f"No jurisdictions with YouTube bronze for states: {', '.join(states)}")

for j in runs:
    jtype = (j.jurisdiction_type or "").strip() or "unknown"
    print(f"{j.state_code}\t{j.jurisdiction_id}\t{j.jurisdiction_name}\t{jtype}")
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
      echo "[dry-run] catalog per jurisdiction (round-robin order), --max-videos $MAX_VIDEOS ${extra[*]}"
      export STATES DATABASE_URL="${DATABASE_URL:-}" ROUND_ROBIN=1
      list_jurisdictions | while IFS=$'\t' read -r st jid name jtype; do
        ch_src="$(resolve_catalog_channel_source "$jtype")"
        echo "  would catalog: $st $name ($jid) channel-source=$ch_src"
      done
    else
      echo "[dry-run] would run load_youtube_events_to_postgres --states $STATES --max-videos $MAX_VIDEOS ${extra[*]} --skip-transcripts"
    fi
    return 0
  fi
  echo "=== Catalog: max $MAX_VIDEOS video(s) per channel; states=$STATES ${DAYS:+(last $DAYS days)} ==="
  if [[ "$rr" -eq 0 ]]; then
    local bulk_src="${CHANNEL_SOURCE:-auto}"
    local -a cat_args=(
      --states "$STATES"
      --max-videos "$MAX_VIDEOS"
      --skip-transcripts
      --channel-source "$bulk_src"
    )
    [[ -n "${CATALOG_FORCE:-}" ]] && cat_args+=(--force)
    "$PYTHON" packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py \
      "${cat_args[@]}" \
      "${extra[@]}"
    return 0
  fi
  echo "=== Catalog order: round-robin across states ==="
  local st jid name jtype ch_src
  while IFS=$'\t' read -r st jid name jtype; do
    ch_src="$(resolve_catalog_channel_source "$jtype")"
    echo "--- Catalog: $st — $name ($jid) [channel-source=$ch_src] ---"
    local -a cat_argv=(
      --jurisdiction-id "$jid"
      --max-videos "$MAX_VIDEOS"
      --skip-transcripts
      --channel-source "$ch_src"
    )
    [[ -n "${CATALOG_FORCE:-}" ]] && cat_argv+=(--force)
    if [[ -n "${CATALOG_YTDLP:-}" ]]; then
      env -u YOUTUBE_API_KEY "$PYTHON" packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py \
        "${cat_argv[@]}" "${extra[@]}" || echo "WARN: catalog failed for $jid" >&2
    else
      "$PYTHON" packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py \
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
  echo "=== Captions batch: target jurisdictions=$target_total (states=$STATES, N=$N transcripts) ==="
  batch_start captions "$target_total"

  for row in "${rows[@]}"; do
    IFS=$'\t' read -r st jid name _jtype <<< "$row"
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
    if [[ -n "${NO_TOMBSTONES:-}" ]]; then
      cap_args+=(--no-tombstones)
    fi
    if [[ -n "${NO_PREFER_UNTRIED:-}" ]]; then
      cap_args+=(--no-prefer-untried)
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
    if [[ -n "${TRANSCRIPT_SOURCE:-}" ]]; then
      cap_args+=(--transcript-source "$TRANSCRIPT_SOURCE")
    fi
    if [[ -n "${BATCH_JOB_ID:-}" ]]; then
      cap_args+=(--batch-id "$BATCH_JOB_ID" --jurisdiction-name "$name")
    fi
    if [[ -n "${DRY_RUN:-}" ]]; then
      cap_args+=(--dry-run)
    fi
    local cap_ec=0
    if ! "$PYTHON" packages/scrapers/src/scrapers/youtube/backfill_jurisdiction_transcripts.py "${cap_args[@]}"; then
      cap_ec=$?
      ((failed+=1))
      echo "WARN: captions failed for $jid (exit $cap_ec)" >&2
    else
      ((success+=1))
    fi
    if [[ -n "${BATCH_JOB_ID:-}" && "$cap_ec" -ne 0 ]]; then
      "$PYTHON" packages/scrapers/src/scrapers/youtube/batch_job_status.py jurisdiction-finish \
        --batch-id "$BATCH_JOB_ID" \
        --jurisdiction-id "$jid" \
        --exit-code "$cap_ec" \
        --stats "{\"shell_exit\":$cap_ec}" 2>/dev/null || true
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
    batch_dashboard_refresh
  done

  batch_finish completed
  echo "=== Captions complete: processed=$processed success=$success failed=$failed target=$target_total ==="
}

analyze_one() {
  local st="$1" jid="$2" name="$3"
  echo "=== Analyze ($N newest): $st — $name ($jid) ==="
  local -a ana_args=(
    --newest "$N"
    --jurisdiction-id "$jid"
    --state "$st"
  )
  if [[ -n "${DRY_RUN:-}" ]]; then
    ana_args+=(--dry-run)
  fi
  local ec=0
  "$PYTHON" -m llm.gemini.meeting_transcript_policy "${ana_args[@]}" || ec=$?
  if (( ec != 0 )); then
    if (( ec == 1 )); then
      echo "WARN: analyze skipped for $jid (usually no captions yet — run: $0 captions)" >&2
    else
      echo "WARN: analyze failed for $jid (exit $ec)" >&2
    fi
  fi
}

run_analyze() {
  local jid st name
  local running=0
  while IFS=$'\t' read -r st jid name _jtype; do
    if (( PARALLEL > 1 )); then
      analyze_one "$st" "$jid" "$name" &
      if (( ++running >= PARALLEL )); then
        wait -n
        (( running-=1 ))
      fi
    else
      analyze_one "$st" "$jid" "$name"
    fi
  done < <(export STATES DATABASE_URL="${DATABASE_URL:-}" ROUND_ROBIN="${ROUND_ROBIN:-1}"; list_jurisdictions)
  if (( PARALLEL > 1 )); then
    wait
  fi
}

# One jurisdiction at a time (round-robin list order): catalog (optional) → captions → analyze.
run_each_jurisdiction() {
  local -a cat_extra=()
  local processed=0
  if [[ -n "$DAYS" ]]; then
    cat_extra+=(--days "$DAYS")
  fi
  local st jid name jtype ch_src
  while IFS=$'\t' read -r st jid name jtype; do
    if [[ -n "$MAX_JURISDICTIONS" ]] && (( processed >= MAX_JURISDICTIONS )); then
      echo "Reached MAX_JURISDICTIONS=$MAX_JURISDICTIONS; stopping each step early."
      break
    fi
    echo "=== Pipeline ($N newest): $st — $name ($jid) ==="
    if [[ -z "${SKIP_CATALOG:-}" ]]; then
      ch_src="$(resolve_catalog_channel_source "$jtype")"
      if [[ -n "${DRY_RUN:-}" ]]; then
        echo "  [dry-run] catalog --max-videos $MAX_VIDEOS channel-source=$ch_src ${cat_extra[*]}"
      else
        echo "--- Catalog: $st — $name ($jid) [channel-source=$ch_src] ---"
        local -a cat_argv=(
          --jurisdiction-id "$jid"
          --max-videos "$MAX_VIDEOS"
          --skip-transcripts
          --channel-source "$ch_src"
        )
        [[ -n "${CATALOG_FORCE:-}" ]] && cat_argv+=(--force)
        if [[ -n "${CATALOG_YTDLP:-}" ]]; then
          env -u YOUTUBE_API_KEY "$PYTHON" packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py \
            "${cat_argv[@]}" "${cat_extra[@]}" || echo "WARN: catalog failed for $jid" >&2
        else
          "$PYTHON" packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py \
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
    if [[ -n "${NO_TOMBSTONES:-}" ]]; then
      cap_args+=(--no-tombstones)
    fi
    if [[ -n "${NO_PREFER_UNTRIED:-}" ]]; then
      cap_args+=(--no-prefer-untried)
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
    if [[ -n "${TRANSCRIPT_SOURCE:-}" ]]; then
      cap_args+=(--transcript-source "$TRANSCRIPT_SOURCE")
    fi
    if [[ -n "${BATCH_JOB_ID:-}" ]]; then
      cap_args+=(--batch-id "$BATCH_JOB_ID" --jurisdiction-name "$name")
    fi
    if [[ -n "${DRY_RUN:-}" ]]; then
      cap_args+=(--dry-run)
    elif ! "$PYTHON" packages/scrapers/src/scrapers/youtube/backfill_jurisdiction_transcripts.py "${cap_args[@]}"; then
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
    elif ! "$PYTHON" -m llm.gemini.meeting_transcript_policy "${ana_args[@]}"; then
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

echo "Done ($STEP, N=$N captions, MAX_VIDEOS=$MAX_VIDEOS catalog, states=$STATES)."
