#!/usr/bin/env bash
# Backfill published_at / event_date / event_time from yt-dlp metadata for bronze rows
# where both event_date and published_at are NULL (see sql/preview_bronze_youtube_blank_publish_dates.sql).
#
# Usage (repo root):
#   ./packages/scrapers/src/scrapers/youtube/run_backfill_bronze_youtube_publish_dates.sh --dry-run --limit 20
#   ./packages/scrapers/src/scrapers/youtube/run_backfill_bronze_youtube_publish_dates.sh --states AL,GA,IN,MA,MT,WA,WI --sleep 3 --extract-retries 4
#   ./packages/scrapers/src/scrapers/youtube/run_backfill_bronze_youtube_publish_dates.sh --cookies-from-browser chrome --sleep 4
#
# Resolves DB URL like other scripts: OPEN_NAVIGATOR_DATABASE_URL, NEON_DATABASE_URL_DEV, NEON_DATABASE_URL,
# DATABASE_URL, else local docker postgres on 5433.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi

exec .venv/bin/python packages/scrapers/src/scrapers/youtube/backfill_bronze_youtube_publish_dates.py "$@"
