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
#   HOMEPAGE_CHANNELS=0    — only jurisdictions that already have videos (default also
#                            includes cities/counties whose channel is linked from their website)
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
#   COHORT=            — priority|data_centers|all (default unset = all jurisdictions in STATES)
#   VPN_WAIT_POLL_SECONDS=30  — on child exit 5, poll vpn_guard this often until up, then retry (#644)
#   DATABASE_URL=...   — override .env

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

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

# YouTube is only reached through the VPN (#488). Children exit 5 when the tunnel
# (or the vpn_guard check) fails. This crawl waits and retries the same step (#644)
# instead of ending the whole overnight job.
VPN_WAIT_POLL_SECONDS="${VPN_WAIT_POLL_SECONDS:-30}"

wait_until_vpn_up() {
  local what="${1:-YouTube step}"
  echo "VPN down during $what; waiting until vpn_guard passes (poll ${VPN_WAIT_POLL_SECONDS}s)..." >&2
  while true; do
    if "$PYTHON" -m scrapers.youtube.vpn_guard; then
      echo "VPN up again; retrying $what" >&2
      return 0
    fi
    sleep "$VPN_WAIT_POLL_SECONDS"
  done
}

# Run "$@"; on exit 5 wait for VPN and retry forever; other non-zero returns that code.
run_with_vpn_retry() {
  local what="$1"
  shift
  while true; do
    local ec=0
    "$@" || ec=$?
    if [[ "$ec" -eq 0 ]]; then
      return 0
    fi
    if [[ "$ec" -eq 5 ]]; then
      wait_until_vpn_up "$what"
      continue
    fi
    echo "WARN: $what failed (exit $ec)" >&2
    return "$ec"
  done
}

if [[ -z "${DRY_RUN:-}" ]]; then
  if ! "$PYTHON" -m scrapers.youtube.vpn_guard; then
    wait_until_vpn_up "startup vpn_guard"
  fi
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
  BATCH_JOB_ID="$("$PYTHON" -m api.batch_jobs.batch_job_status start \
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
  "$PYTHON" -m api.batch_jobs.batch_job_status finish \
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

# Also crawl cities/counties whose channel was found on their own website but that
# have no videos yet (HOMEPAGE_CHANNELS=0 turns this off).
include_homepage = os.environ.get("HOMEPAGE_CHANNELS", "1").strip().lower() not in (
    "0", "false", "no", "off",
)
cohort = (os.environ.get("COHORT") or "").strip() or None
runs = fetch_batch_plan_jurisdictions(
    states,
    round_robin=round_robin,
    database_url=url,
    include_homepage_channels=include_homepage,
    cohort=cohort,
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
      --states "$st"
      --max-videos "$MAX_VIDEOS"
      --skip-transcripts
      --channel-source "$ch_src"
    )
    [[ -n "${CATALOG_FORCE:-}" ]] && cat_argv+=(--force)
    if [[ -n "${CATALOG_YTDLP:-}" ]]; then
      run_with_vpn_retry "catalog for $jid" \
        env -u YOUTUBE_API_KEY "$PYTHON" packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py \
        "${cat_argv[@]}" "${extra[@]}" || true
    else
      run_with_vpn_retry "catalog for $jid" \
        "$PYTHON" packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py \
        "${cat_argv[@]}" "${extra[@]}" || true
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
    run_with_vpn_retry "captions for $jid" \
      "$PYTHON" packages/scrapers/src/scrapers/youtube/backfill_jurisdiction_transcripts.py "${cap_args[@]}" \
      || cap_ec=$?
    if [[ "$cap_ec" -ne 0 ]]; then
      ((failed+=1))
    else
      ((success+=1))
    fi
    if [[ -n "${BATCH_JOB_ID:-}" && "$cap_ec" -ne 0 ]]; then
      "$PYTHON" -m api.batch_jobs.batch_job_status jurisdiction-finish \
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

# Jev meeting-kind gate for analyze (#704). data_centers cohort defaults to 0.6;
# override with SKIP_JEV_MEETING_BELOW= (empty to disable) or an explicit float.
append_jev_analyze_flags() {
  local -n _arr=$1
  local t="${SKIP_JEV_MEETING_BELOW-}"
  if [[ -z "${t}" && "${COHORT:-}" == "data_centers" ]]; then
    t="0.6"
  fi
  if [[ -n "${t}" ]]; then
    _arr+=(--skip-jev-meeting-below "$t")
  fi
  if [[ -n "${SKIP_JEV_BELOW:-}" ]]; then
    _arr+=(--skip-jev-below "$SKIP_JEV_BELOW")
  fi
}

# ANALYZE_TIER=light|full (default light). FULL_FILTERS=comma keys for full.
# PART2_ONLY=1 → --part-2-only (reports-light / reports-full).
analyze_one() {
  local st="$1" jid="$2" name="$3"
  local tier="${ANALYZE_TIER:-light}"
  local label="Analyze"
  [[ -n "${PART2_ONLY:-}" ]] && label="Reports"
  echo "=== ${label} ${tier} ($N newest): $st — $name ($jid) ==="
  local -a ana_args=(
    --jurisdiction-id "$jid"
    --state "$st"
    --analysis-tier "$tier"
  )
  if [[ -n "${PART2_ONLY:-}" ]]; then
    ana_args+=(--part-2-only --limit "$N")
  else
    ana_args+=(--newest "$N")
  fi
  if [[ -n "${FULL_FILTERS:-}" ]]; then
    ana_args+=(--full-filters "$FULL_FILTERS")
  fi
  # Light tier skips Gemini: DeepSeek writes Part 1 / Part 2 (#774). Full keeps the
  # Gemini default. LIGHT_MODEL= (empty) or a gemini-* id restores Gemini for light.
  if [[ "$tier" == "light" ]]; then
    local light_model="${LIGHT_MODEL-deepseek-flash}"
    if [[ -n "$light_model" ]]; then
      ana_args+=(--model "$light_model" --part-2-model "$light_model")
    fi
  fi
  append_jev_analyze_flags ana_args
  if [[ -n "${DRY_RUN:-}" ]]; then
    ana_args+=(--dry-run)
  fi
  local ec=0
  "$PYTHON" -m llm.gemini.meeting_transcript_policy "${ana_args[@]}" || ec=$?
  if (( ec != 0 )); then
    if (( ec == 1 )); then
      echo "WARN: ${label} skipped for $jid (usually no captions/analysis yet)" >&2
    else
      echo "WARN: ${label} failed for $jid (exit $ec)" >&2
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

run_analyze_light() {
  ANALYZE_TIER=light PART2_ONLY= run_analyze
}

run_reports_light() {
  ANALYZE_TIER=light PART2_ONLY=1 run_analyze
}

run_analyze_full() {
  ANALYZE_TIER=full PART2_ONLY= run_analyze
}

run_reports_full() {
  ANALYZE_TIER=full PART2_ONLY=1 run_analyze
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
          --states "$st"
          --max-videos "$MAX_VIDEOS"
          --skip-transcripts
          --channel-source "$ch_src"
        )
        [[ -n "${CATALOG_FORCE:-}" ]] && cat_argv+=(--force)
        if [[ -n "${CATALOG_YTDLP:-}" ]]; then
          run_with_vpn_retry "catalog for $jid" \
            env -u YOUTUBE_API_KEY "$PYTHON" packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py \
            "${cat_argv[@]}" "${cat_extra[@]}" || true
        else
          run_with_vpn_retry "catalog for $jid" \
            "$PYTHON" packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py \
            "${cat_argv[@]}" "${cat_extra[@]}" || true
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
    else
      run_with_vpn_retry "captions for $jid" \
        "$PYTHON" packages/scrapers/src/scrapers/youtube/backfill_jurisdiction_transcripts.py "${cap_args[@]}" \
        || true
    fi
    echo "--- Analyze light: $st — $name ($jid) ---"
    ANALYZE_TIER=light PART2_ONLY= analyze_one "$st" "$jid" "$name"
    echo "--- Reports light: $st — $name ($jid) ---"
    ANALYZE_TIER=light PART2_ONLY=1 analyze_one "$st" "$jid" "$name"
    ((processed+=1))
  done < <(export STATES DATABASE_URL="${DATABASE_URL:-}" ROUND_ROBIN="${ROUND_ROBIN:-1}"; list_jurisdictions)
}

case "$STEP" in
  catalog) run_catalog ;;
  captions) run_captions ;;
  analyze|analyze-light) run_analyze_light ;;
  reports-light) run_reports_light ;;
  analyze-full) run_analyze_full ;;
  reports-full) run_reports_full ;;
  each) run_each_jurisdiction ;;
  all)
    # Stages 2–5 of Run all (#755): catalog → captions → analyze-light → reports-light.
    # Discover is chained by the API before this shell step.
    [[ -z "${SKIP_CATALOG:-}" ]] && run_catalog
    run_captions
    run_analyze_light
    run_reports_light
    ;;
  list)
    export STATES DATABASE_URL="${DATABASE_URL:-}" ROUND_ROBIN="${ROUND_ROBIN:-1}"
    list_jurisdictions
    ;;
  *)
    echo "Usage: $0 [catalog|captions|analyze|analyze-light|reports-light|analyze-full|reports-full|each|all|list]" >&2
    echo "  each — round-robin: per jurisdiction, captions then light analyze/report" >&2
    echo "  all  — catalog → captions → analyze-light → reports-light (#755)" >&2
    exit 1
    ;;
esac

echo "Done ($STEP, N=$N captions, MAX_VIDEOS=$MAX_VIDEOS catalog, states=$STATES)."
