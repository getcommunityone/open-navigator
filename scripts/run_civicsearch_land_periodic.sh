#!/usr/bin/env bash
# Periodically land the growing CivicSearch JSONL caches into Postgres while the
# harvesters keep scraping. Each portal's loader is an idempotent upsert keyed by
# vid_id (ON CONFLICT DO UPDATE), so re-landing the whole file every cycle simply
# inserts the newly-harvested meetings and refreshes existing ones — safe to run
# repeatedly against a file that's still growing.
#
#   cities/meetings.jsonl  -> bronze.bronze_events_civicsearch
#   schools/meetings.jsonl -> bronze.bronze_events_civicsearch_schools
#
# Runs until BOTH harvest supervisors have exited (scrape complete), then does
# one final land and stops. Interval via INTERVAL (default 600s).
set -uo pipefail
cd "$(dirname "$0")/.."

INTERVAL="${INTERVAL:-600}"
set -a; source .env 2>/dev/null; set +a
mkdir -p data/logs

land() {
  echo "[$(date +%H:%M:%S)] landing cities + schools..."
  python -m ingestion.civicsearch.events \
    --jsonl data/cache/civicsearch/cities/meetings.jsonl 2>&1 \
    | grep -E "pipeline_complete|error" | tail -1
  python -m ingestion.civicsearch.events --schools \
    --jsonl data/cache/civicsearch/schools/meetings.jsonl 2>&1 \
    | grep -E "pipeline_complete|error" | tail -1
}

harvesters_alive() {
  pgrep -f "run_civicsearch_harvest_supervised.sh" >/dev/null 2>&1
}

while harvesters_alive; do
  # only land if the cache files exist
  [ -s data/cache/civicsearch/cities/meetings.jsonl ] && land
  sleep "$INTERVAL"
done

echo "[$(date +%H:%M:%S)] harvest supervisors gone — final land."
land
echo "[$(date +%H:%M:%S)] periodic landing finished."
