#!/usr/bin/env bash
# Load YouTube events with live Loguru progress on stderr (no nohup).
#
# Usage (repo root):
#   ./scripts/datasources/youtube/run_load_youtube_events_terminal.sh
#
# Optional env:
#   STATES=AL,GA,IN,MA,WA,WI
#   CHANNEL_SOURCE=counties-scraped
#   MAX_VIDEOS=100
#   MAX_TRANSCRIPTS=4
#   WORKERS=6
#   TRANSCRIPT_DELAY=10
#   COOKIES=youtube_cookies.txt
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

STATES="${STATES:-AL,GA,IN,MA,WA,WI}"
CHANNEL_SOURCE="${CHANNEL_SOURCE:-counties-scraped}"
MAX_VIDEOS="${MAX_VIDEOS:-100}"
MAX_TRANSCRIPTS="${MAX_TRANSCRIPTS:-4}"
WORKERS="${WORKERS:-6}"
TRANSCRIPT_DELAY="${TRANSCRIPT_DELAY:-10}"
COOKIES="${COOKIES:-youtube_cookies.txt}"

cmd=(
  .venv/bin/python -u scripts/datasources/youtube/load_youtube_events_to_postgres.py
  --channel-source "$CHANNEL_SOURCE"
  --states "$STATES"
  --max-videos "$MAX_VIDEOS"
  --max-transcripts-per-channel "$MAX_TRANSCRIPTS"
  --resolve-channels-ytdlp
  --cookies "$COOKIES"
  --workers "$WORKERS"
  --transcript-delay "$TRANSCRIPT_DELAY"
  --text-transcripts-only
)
[ "${SKIP_TRANSCRIPTS:-0}" = "1" ] && cmd+=(--skip-transcripts)

echo ">>> ${cmd[*]}"
echo ">>> Per-county lines on stderr; full detail: data/bronze/youtube_loader_logs/run_*.log"
if [ -n "${LOG_FILE:-}" ]; then
  mkdir -p "$(dirname "$LOG_FILE")"
  "${cmd[@]}" 2>&1 | tee -a "$LOG_FILE"
else
  exec "${cmd[@]}"
fi
