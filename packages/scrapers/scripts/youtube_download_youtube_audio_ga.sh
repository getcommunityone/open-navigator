#!/usr/bin/env bash
# Download YouTube audio for Georgia only (bronze_events_youtube.state_code = 'GA').
# Extra args are forwarded, e.g.:
#   ./packages/scrapers/src/scrapers/youtube/download_youtube_audio_ga.sh --limit 20 --not-yet-downloaded
#   ./packages/scrapers/src/scrapers/youtube/download_youtube_audio_ga.sh --bronze-channels-only --government-channel-types-only \
#     --meetings-only --exclude-news --years-back 5 --not-yet-downloaded
# If many GA rows have NULL event_date and NULL published_at in bronze, add --allow-null-upload-date
# (see audit_ga_youtube_download_filters.sql params.allow_null_upload_date). --allow-null-upload-date
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
exec .venv/bin/python packages/scrapers/src/scrapers/youtube/download_audio_to_drive.py \
  --states GA \
  "$@"
