#!/usr/bin/env bash
# Download YouTube audio for Alabama only (bronze_event_youtube.state_code = 'AL').
# Extra args are forwarded, e.g.:
#   ./packages/scrapers/src/scrapers/youtube/download_youtube_audio_al.sh --limit 20 --not-yet-downloaded
#   ./packages/scrapers/src/scrapers/youtube/download_youtube_audio_al.sh --bronze-channels-only --government-channel-types-only --meetings-only --exclude-news --years-back 5 --not-yet-downloaded
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
exec .venv/bin/python packages/scrapers/src/scrapers/youtube/download_audio_to_drive.py \
  --states AL \
  "$@"
