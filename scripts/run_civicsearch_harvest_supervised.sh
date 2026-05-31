#!/usr/bin/env bash
# Supervisor: keep a CivicSearch harvester alive across transient API failures.
#
# The harvester exhausts its per-request retries on a run of HTTP 500s and exits
# non-zero. Because it runs --incremental, restarting just resumes from the
# cached places/meetings (already-seen vid_ids are skipped), so a restart loop
# is safe and loses no work. Stops cleanly once the harvester exits 0 (frontier
# exhausted = scrape complete), or after MAX_RESTARTS consecutive failures.
#
# Usage: run_civicsearch_harvest_supervised.sh <portal>   # cities | schools
set -uo pipefail
cd "$(dirname "$0")/.."

PORTAL="${1:?usage: $0 <cities|schools>}"
MAX_RESTARTS="${MAX_RESTARTS:-50}"
BACKOFF="${BACKOFF:-30}"   # seconds between restarts (let the API recover)

set -a; source .env 2>/dev/null; set +a
mkdir -p data/logs

fails=0
attempt=0
while :; do
  attempt=$((attempt+1))
  ts=$(date +%Y%m%d_%H%M%S)
  log="data/logs/civicsearch_harvest_${PORTAL}_${ts}.log"
  echo "$log" > "/tmp/cs_${PORTAL}.logpath"
  echo "[$(date +%H:%M:%S)] start attempt $attempt ($PORTAL) -> $log"
  python -m scrapers.civicsearch.harvest \
    --portal "$PORTAL" --max-places 1000000 --incremental >> "$log" 2>&1
  rc=$?
  if [ $rc -eq 0 ]; then
    echo "[$(date +%H:%M:%S)] $PORTAL harvester completed cleanly (frontier exhausted)."
    break
  fi
  fails=$((fails+1))
  echo "[$(date +%H:%M:%S)] $PORTAL harvester exited rc=$rc (failure $fails/$MAX_RESTARTS); restarting in ${BACKOFF}s"
  if [ "$fails" -ge "$MAX_RESTARTS" ]; then
    echo "[$(date +%H:%M:%S)] $PORTAL: hit MAX_RESTARTS=$MAX_RESTARTS; giving up."
    exit 1
  fi
  sleep "$BACKOFF"
done
