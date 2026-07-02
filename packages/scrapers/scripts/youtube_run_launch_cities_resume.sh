#!/usr/bin/env bash
# Resume launch-cities pipeline from Seattle analyze onward (after catalog + captions).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
source .venv/bin/activate

COOKIES="${COOKIES:-youtube_cookies.txt}"
LOG="${LOG:-/tmp/launch-cities-resume.log}"
exec > >(tee -a "$LOG") 2>&1

echo "=== launch-cities RESUME $(date -Iseconds) ==="

run_load() {
  local jid="$1" name="$2" state="$3" channel="$4"
  echo "--- load_youtube $name ($jid) channel=$channel ---"
  python -m scrapers.youtube.load_youtube_for_jurisdiction \
    --jurisdiction-id "$jid" \
    --jurisdiction-name "$name" \
    --state "$state" \
    --channel-id "$channel" \
    --max-videos 150 \
    --cookies "$COOKIES" \
    --transcript-delay 6 \
    --force || echo "WARN: load failed $name $channel"
}

run_backfill() {
  local jid="$1" name="$2"
  echo "--- backfill transcripts $name ($jid) ---"
  python -m scrapers.youtube.backfill_jurisdiction_transcripts \
    --jurisdiction-id "$jid" \
    --cookies "$COOKIES" \
    --delay 6 \
    --limit 40 \
    --order-by published_at || echo "WARN: backfill failed $name"
}

run_analyze_14d() {
  local jid="$1" state="$2"
  echo "--- analyze last 14d $jid ---"
  local vids
  vids=$(psql "${DATABASE_URL:-postgresql://postgres:password@localhost:5433/open_navigator}" -tA -c "
    SELECT y.video_id
    FROM bronze.bronze_event_youtube y
    JOIN bronze.bronze_event_youtube_transcript t ON t.video_id = y.video_id AND t.has_transcript
    LEFT JOIN bronze.bronze_events_analysis_ai a
      ON a.structured_analysis->>'video_id' = y.video_id
      AND NOT (a.structured_analysis ? '_error')
    WHERE y.jurisdiction_id = '$jid'
      AND COALESCE(y.published_at, y.event_date::timestamp, y.loaded_at) >= NOW() - INTERVAL '14 days'
      AND a.id IS NULL
    ORDER BY COALESCE(y.published_at, y.event_date::timestamp, y.loaded_at) DESC;
  ")
  if [[ -z "${vids// /}" ]]; then
    echo "No videos to analyze for $jid"
    return 0
  fi
  for vid in $vids; do
    echo "=== analyze $jid $vid $(date -Iseconds) ==="
    python -m llm.gemini.meeting_transcript_policy \
      --video-id "$vid" \
      --jurisdiction-id "$jid" \
      --state "$state" \
      --use-local-transcript \
      --run-part-2 \
      --persist-bronze || echo "FAILED analyze $vid"
  done
}

# Seattle: catalog + captions already done 2026-06-22
run_analyze_14d seattle_5363000 WA

for ch in UCiMB3gH6PLe-JMDhxX4ZsmA UCImopNmmU11qfuWBbiXdowQ UCHsQucHjLMXpJo2Z8WYwJyg UCRdMSsbwr4-n02KUd65oRDA; do
  run_load boston_2507000 Boston MA "$ch"
done
run_backfill boston_2507000 Boston
run_analyze_14d boston_2507000 MA

run_load atlanta_1304000 Atlanta GA UCMdVz77sRLkqJe5NLVB7uTQ
run_backfill atlanta_1304000 Atlanta
run_analyze_14d atlanta_1304000 GA

run_load san_francisco_0667000 "San Francisco" CA UCLKkoNhtPapzj5DiH4W3Q4w
run_backfill san_francisco_0667000 "San Francisco"
run_analyze_14d san_francisco_0667000 CA

echo "--- final dbt rebuild ---"
./scripts/dbt.sh run --select bronze_meetings_from_ai+ event_meeting+ meeting_browse event_meeting_document

echo "=== DONE launch-cities RESUME $(date -Iseconds) ==="
