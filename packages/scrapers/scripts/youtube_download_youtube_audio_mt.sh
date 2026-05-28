#!/usr/bin/env bash
# Download YouTube audio for Montana only (bronze_events_youtube.state_code = 'MT').
# Extra args are forwarded, e.g.:
#   ./packages/scrapers/src/scrapers/youtube/download_youtube_audio_mt.sh --limit 25 --not-yet-downloaded
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
exec .venv/bin/python packages/scrapers/src/scrapers/youtube/download_audio_to_drive.py \
  --states MT \
  "$@"
