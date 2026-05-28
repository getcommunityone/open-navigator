#!/usr/bin/env bash
# Full YouTube channel pipeline for priority states:
# 1) Discover missing county channel candidates per state
# 2) Load candidates to bronze/events catalog
# 3) Enrich channel metadata from YouTube About pages
# 4) Rebuild dbt intermediates for channel mapping
#
# Usage (repo root):
#   ./packages/scrapers/src/scrapers/youtube/run_priority_states_channel_pipeline.sh
#
# Optional env:
#   STATES=AL,GA,IN,MA,MT,WA,WI
#   PYTHON=.venv/bin/python
#   MAX_VIDEOS=100
#   MIN_DURATION_SECONDS=120
#   JURISDICTION_TYPE=county
#   OUTPUT_DIR=/tmp/youtube-channel-candidates
#   SKIP_HOMEPAGE_SCRAPE=0
#   ABOUT_SLEEP=1.25
#   ABOUT_LIMIT=0
#   SKIP_DISCOVERY=0
#   SKIP_LOAD=0
#   SKIP_ABOUT=0
#   LOAD_TRANSCRIPTS=0
#   TRANSCRIPT_DELAY=6
#   YOUTUBE_COOKIES=/path/to/youtube_cookies.txt
#   YOUTUBE_TRANSCRIPT_PROXY=socks5://127.0.0.1:9090
#   RUN_DBT=1
#   DBT_PROJECT_DIR=dbt_project
#   DBT_CMD=dbt
#   DBT_SELECT="int_jurisdiction_homepage_youtube_channels int_events_channels int_events_channels_enriched"

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
STATES="${STATES:-AL,GA,IN,MA,MT,WA,WI}"
MAX_VIDEOS="${MAX_VIDEOS:-100}"
MIN_DURATION_SECONDS="${MIN_DURATION_SECONDS:-120}"
JURISDICTION_TYPE="${JURISDICTION_TYPE:-county}"
OUTPUT_DIR="${OUTPUT_DIR:-/tmp/youtube-channel-candidates}"
SKIP_HOMEPAGE_SCRAPE="${SKIP_HOMEPAGE_SCRAPE:-0}"
ABOUT_SLEEP="${ABOUT_SLEEP:-1.25}"
ABOUT_LIMIT="${ABOUT_LIMIT:-0}"

SKIP_DISCOVERY="${SKIP_DISCOVERY:-0}"
SKIP_LOAD="${SKIP_LOAD:-0}"
SKIP_ABOUT="${SKIP_ABOUT:-0}"
LOAD_TRANSCRIPTS="${LOAD_TRANSCRIPTS:-0}"
TRANSCRIPT_DELAY="${TRANSCRIPT_DELAY:-6}"
YOUTUBE_COOKIES="${YOUTUBE_COOKIES:-}"
YOUTUBE_TRANSCRIPT_PROXY="${YOUTUBE_TRANSCRIPT_PROXY:-}"
RUN_DBT="${RUN_DBT:-1}"

DBT_PROJECT_DIR="${DBT_PROJECT_DIR:-$ROOT/dbt_project}"
DBT_CMD="${DBT_CMD:-}"
DBT_SELECT="${DBT_SELECT:-int_jurisdiction_homepage_youtube_channels int_events_channels int_events_channels_enriched}"

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing Python executable: $PYTHON" >&2
  exit 1
fi

if [[ -z "$DBT_CMD" ]]; then
  if command -v dbt >/dev/null 2>&1; then
    DBT_CMD="dbt"
  fi
fi

mkdir -p "$OUTPUT_DIR"

IFS=',' read -r -a STATE_LIST <<< "$STATES"

echo "=== Priority-state channel pipeline ==="
echo "states: $STATES"
echo "python: $PYTHON"
echo "output_dir: $OUTPUT_DIR"
echo "load_transcripts: $LOAD_TRANSCRIPTS"
echo "min_duration_seconds: $MIN_DURATION_SECONDS"

for raw_state in "${STATE_LIST[@]}"; do
  state="$(echo "$raw_state" | tr '[:lower:]' '[:upper:]' | xargs)"
  if [[ -z "$state" ]]; then
    continue
  fi

  csv_path="$OUTPUT_DIR/${state,,}_channel_candidates.csv"
  echo
  echo "=== [$state] candidate discovery ==="

  if [[ "$SKIP_DISCOVERY" != "1" ]]; then
    disc_args=(
      packages/scrapers/src/scrapers/youtube/load_missing_county_channels.py
      --state "$state"
      --output "$csv_path"
    )
    if [[ "$SKIP_HOMEPAGE_SCRAPE" == "1" ]]; then
      disc_args+=(--skip-homepage-scrape)
    fi
    "$PYTHON" "${disc_args[@]}"
  else
    echo "skip discovery enabled; expecting existing file: $csv_path"
  fi

  if [[ ! -f "$csv_path" ]]; then
    echo "ERROR: candidate CSV not found for $state: $csv_path" >&2
    exit 1
  fi

  echo "=== [$state] load candidates to catalog ==="
  if [[ "$SKIP_LOAD" != "1" ]]; then
    load_args=(
      packages/scrapers/src/scrapers/youtube/load_channel_candidates_to_catalog.py
      --input "$csv_path"
      --state "$state"
      --jurisdiction-type "$JURISDICTION_TYPE"
      --max-videos "$MAX_VIDEOS"
      --min-duration-seconds "$MIN_DURATION_SECONDS"
      --python "$PYTHON"
    )

    if [[ "$LOAD_TRANSCRIPTS" == "1" ]]; then
      load_args+=(--load-transcripts --transcript-delay "$TRANSCRIPT_DELAY")
      if [[ -n "$YOUTUBE_COOKIES" ]]; then
        load_args+=(--cookies "$YOUTUBE_COOKIES")
      fi
      if [[ -n "$YOUTUBE_TRANSCRIPT_PROXY" ]]; then
        load_args+=(--proxy "$YOUTUBE_TRANSCRIPT_PROXY")
      fi
    fi

    "$PYTHON" "${load_args[@]}"
  else
    echo "skip load enabled"
  fi
done

echo
echo "=== Channel About enrichment ==="
if [[ "$SKIP_ABOUT" != "1" ]]; then
  about_args=(
    packages/scrapers/src/scrapers/youtube/channel_about_links.py
    --from-bronze-youtube
    --where-null
    --sleep "$ABOUT_SLEEP"
  )
  if [[ "$ABOUT_LIMIT" != "0" ]]; then
    about_args+=(--limit "$ABOUT_LIMIT")
  fi
  "$PYTHON" "${about_args[@]}"
else
  echo "skip about enrichment enabled"
fi

echo
echo "=== dbt rebuild ==="
if [[ "$RUN_DBT" == "1" ]]; then
  if [[ -z "$DBT_CMD" ]]; then
    echo "WARNING: dbt command not found; skipping dbt run." >&2
    echo "Run manually in $DBT_PROJECT_DIR:" >&2
    echo "  dbt run --select $DBT_SELECT" >&2
  else
    (cd "$DBT_PROJECT_DIR" && $DBT_CMD run --select $DBT_SELECT)
  fi
else
  echo "dbt run skipped (RUN_DBT=$RUN_DBT)"
fi

echo
echo "Pipeline complete."
