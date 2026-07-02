#!/usr/bin/env bash
# Full pipeline: catalog → caption backfill → Gemini analyze → dbt rebuild
# for Seattle, Boston, Atlanta, and San Francisco.
#
# Usage (repo root):
#   ./packages/scrapers/scripts/youtube_run_launch_cities_all.sh
#   LOG=/tmp/my-run.log ./packages/scrapers/scripts/youtube_run_launch_cities_all.sh
#
# Optional env:
#   COOKIES=youtube_cookies.txt
#   MAX_VIDEOS=150          — per channel catalog cap
#   BACKFILL_LIMIT=40       — transcripts per city backfill pass
#   BACKFILL_DELAY=12       — seconds between caption fetches
#   ANALYZE_DAYS=90         — only analyze videos published in this window
#   SKIP_LOAD=1             — skip catalog refresh (backfill + analyze only)
#   SKIP_DBT=1              — skip final dbt rebuild

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
source .venv/bin/activate

COOKIES="${COOKIES:-youtube_cookies.txt}"
MAX_VIDEOS="${MAX_VIDEOS:-150}"
BACKFILL_LIMIT="${BACKFILL_LIMIT:-40}"
BACKFILL_DELAY="${BACKFILL_DELAY:-12}"
ANALYZE_DAYS="${ANALYZE_DAYS:-90}"
LOG="${LOG:-/tmp/launch-cities-all_$(date +%Y%m%d_%H%M%S).log}"
PSQL_URL="${DATABASE_URL:-postgresql://postgres:password@localhost:5433/open_navigator}"

exec > >(tee -a "$LOG") 2>&1
echo "=== launch-cities ALL $(date -Iseconds) log=$LOG ==="

run_load() {
  local jid="$1" name="$2" state="$3" channel="$4"
  echo "--- catalog $name ($jid) channel=$channel ---"
  python -m scrapers.youtube.load_youtube_for_jurisdiction \
    --jurisdiction-id "$jid" \
    --jurisdiction-name "$name" \
    --state "$state" \
    --channel-id "$channel" \
    --max-videos "$MAX_VIDEOS" \
    --skip-transcripts \
    --force || echo "WARN: catalog failed $name $channel"
}

run_backfill() {
  local jid="$1" name="$2"
  echo "--- backfill transcripts $name ($jid) limit=$BACKFILL_LIMIT delay=${BACKFILL_DELAY}s ---"
  python -m scrapers.youtube.backfill_jurisdiction_transcripts \
    --jurisdiction-id "$jid" \
    --cookies "$COOKIES" \
    --delay "$BACKFILL_DELAY" \
    --limit "$BACKFILL_LIMIT" \
    --order-by published_at || echo "WARN: backfill failed $name"
}

fix_transcript_flags() {
  local jid="$1"
  psql "$PSQL_URL" -q -c "
    UPDATE bronze.bronze_event_youtube_transcript t
    SET has_transcript = true
    FROM bronze.bronze_event_youtube y
    WHERE y.video_id = t.video_id
      AND y.jurisdiction_id = '$jid'
      AND coalesce(t.has_transcript, false) = false
      AND length(coalesce(t.raw_text, '')) > 100;
  " || true
}

run_analyze() {
  local jid="$1" state="$2"
  fix_transcript_flags "$jid"
  echo "--- analyze last ${ANALYZE_DAYS}d $jid ---"
  local count=0
  while IFS= read -r vid; do
    [[ -z "$vid" ]] && continue
    count=$((count + 1))
    echo "=== analyze [$count] $jid $vid $(date -Iseconds) ==="
    python -m llm.gemini.meeting_transcript_policy \
      --video-id "$vid" \
      --jurisdiction-id "$jid" \
      --state "$state" \
      --use-local-transcript \
      --run-part-2 \
      --persist-bronze || echo "FAILED analyze $vid"
  done < <(
    psql "$PSQL_URL" -tA -c "
      SELECT y.video_id
      FROM bronze.bronze_event_youtube y
      JOIN bronze.bronze_event_youtube_transcript t ON t.video_id = y.video_id
        AND (t.has_transcript OR length(coalesce(t.raw_text, '')) > 100)
      LEFT JOIN bronze.bronze_events_analysis_ai a
        ON a.structured_analysis->>'video_id' = y.video_id
        AND NOT (a.structured_analysis ? '_error')
      WHERE y.jurisdiction_id = '$jid'
        AND COALESCE(y.published_at, y.event_date::timestamp, y.loaded_at)
            >= NOW() - INTERVAL '${ANALYZE_DAYS} days'
        AND a.id IS NULL
      ORDER BY COALESCE(y.published_at, y.event_date::timestamp, y.loaded_at) DESC;
    "
  )
  if (( count == 0 )); then
    echo "No videos to analyze for $jid"
  fi
}

run_city() {
  local jid="$1" name="$2" state="$3"
  shift 3
  local -a channels=("$@")
  if [[ -z "${SKIP_LOAD:-}" ]]; then
    if ((${#channels[@]})); then
      local ch
      for ch in "${channels[@]}"; do
        run_load "$jid" "$name" "$state" "$ch"
      done
    fi
  fi
  run_backfill "$jid" "$name"
  run_analyze "$jid" "$state"
}

# Seattle — Seattle Channel (official; @cityofseattle / UCMFAKdxL6sATpkRqLdJyKUg are 404)
run_city seattle_5363000 Seattle WA UCu2IUja1ASnGIr_ORrtLReg

# Boston — multiple official channels
run_city boston_2507000 Boston MA \
  UCiMB3gH6PLe-JMDhxX4ZsmA \
  UCImopNmmU11qfuWBbiXdowQ \
  UCHsQucHjLMXpJo2Z8WYwJyg \
  UCRdMSsbwr4-n02KUd65oRDA

run_city atlanta_1304000 Atlanta GA UCMdVz77sRLkqJe5NLVB7uTQ

run_city san_francisco_0667000 "San Francisco" CA UCLKkoNhtPapzj5DiH4W3Q4w

if [[ -z "${SKIP_DBT:-}" ]]; then
  echo "--- final dbt rebuild ---"
  ./scripts/dbt.sh run --select bronze_meetings_from_ai+ event_meeting+ meeting_browse event_meeting_document \
    || echo "WARN: dbt rebuild failed"
fi

echo "=== DONE launch-cities ALL $(date -Iseconds) log=$LOG ==="
