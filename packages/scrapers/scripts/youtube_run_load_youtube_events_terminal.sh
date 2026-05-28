#!/usr/bin/env bash
# Load YouTube events with live Loguru progress on stderr (no nohup).
#
# Usage (repo root):
#   ./packages/scrapers/src/scrapers/youtube/run_load_youtube_events_terminal.sh
#
# Optional env:
#   STATES=ALL                   # 50 states + DC + PR (see ALL_US_STATES below)
#   STATES=AL,GA,IN,MA,WA,WI     # or any comma-separated list
#   CHANNEL_SOURCE=auto          # golden intermediate.int_events_channels when set
#   CHANNEL_SOURCE=counties-scraped   # bronze_jurisdictions_counties_scraped
#   CHANNEL_SOURCE=municipalities-scraped
#
# All states, catalog only (no captions):
#   STATES=ALL MAX_VIDEOS=100 SKIP_TRANSCRIPTS=1 WORKERS=4 \
#     ./packages/scrapers/src/scrapers/youtube/run_load_youtube_events_terminal.sh
#   MAX_VIDEOS=100
#   MAX_TRANSCRIPTS=4
#   WORKERS=1
#   TRANSCRIPT_WORKERS=1
#   TRANSCRIPT_DELAY=10
#   COOKIES=youtube_cookies.txt
#   TRANSCRIPT_SOURCE=auto         # captions: youtube-transcript-api, yt-dlp fallback
#   PROXY_USER_NAME / PROXY_PASSWORD → Webshare rotating residential (captions)
#   WEBSHARE_FILTER_IP_LOCATIONS=us,de  → limit IP rotation pool (optional)
#   TEXT_TRANSCRIPTS_ONLY=1      # legacy alias for api-only captions
#   SKIP_TRANSCRIPTS=1        # catalog only
#   LOG_FILE=path.log         # tee stdout/stderr; detailed yt-dlp still in data/bronze/youtube_loader_logs/
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
set -a
[ -f .env ] && . ./.env
set +a
export PYTHONUNBUFFERED=1

# 50 states + DC + PR (matches packages/ingestion/.../census/states.py US_STATES)
ALL_US_STATES="AK,AL,AR,AZ,CA,CO,CT,DE,DC,FL,GA,HI,ID,IL,IN,IA,KS,KY,LA,ME,MD,MA,MI,MN,MS,MO,MT,NE,NV,NH,NJ,NM,NY,NC,ND,OH,OK,OR,PA,PR,RI,SC,SD,TN,TX,UT,VT,VA,WA,WV,WI,WY"

_raw_states="${STATES:-ALL}"
if [[ "$_raw_states" == "ALL" || "$_raw_states" == "all" ]]; then
  STATES="$ALL_US_STATES"
else
  STATES="$_raw_states"
fi
unset _raw_states
CHANNEL_SOURCE="${CHANNEL_SOURCE:-auto}"
MAX_VIDEOS="${MAX_VIDEOS:-100}"
MAX_TRANSCRIPTS="${MAX_TRANSCRIPTS:-4}"
WORKERS="${WORKERS:-1}"
TRANSCRIPT_WORKERS="${TRANSCRIPT_WORKERS:-1}"
TRANSCRIPT_DELAY="${TRANSCRIPT_DELAY:-15}"
COOKIES="${COOKIES:-youtube_cookies.txt}"
TRANSCRIPT_SOURCE="${TRANSCRIPT_SOURCE:-api-only}"

cmd=(
  .venv/bin/python -u packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py
  --channel-source "$CHANNEL_SOURCE"
  --states "$STATES"
  --max-videos "$MAX_VIDEOS"
  --max-transcripts-per-channel "$MAX_TRANSCRIPTS"
  --resolve-channels-ytdlp
  --cookies "$COOKIES"
  --workers "$WORKERS"
  --transcript-workers "$TRANSCRIPT_WORKERS"
  --transcript-delay "$TRANSCRIPT_DELAY"
)
[ "${SKIP_TRANSCRIPTS:-0}" = "1" ] && cmd+=(--skip-transcripts)
if [ -n "${TRANSCRIPT_SOURCE:-}" ]; then
  cmd+=(--transcript-source "$TRANSCRIPT_SOURCE")
elif [ "${TEXT_TRANSCRIPTS_ONLY:-0}" = "1" ]; then
  cmd+=(--transcript-source api-only)
fi
# Writes data/cache/gemini_transcript_policy/.../01_transcripts/*.json (+ .caption_raw_data.json)

echo ">>> ${cmd[*]}"
echo ">>> Per-county lines on stderr; full detail: data/bronze/youtube_loader_logs/run_*.log"
if [ -n "${LOG_FILE:-}" ]; then
  mkdir -p "$(dirname "$LOG_FILE")"
  "${cmd[@]}" 2>&1 | tee -a "$LOG_FILE"
else
  exec "${cmd[@]}"
fi
