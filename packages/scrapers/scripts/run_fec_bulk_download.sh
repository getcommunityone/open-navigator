#!/usr/bin/env bash
# Download FEC bulk ZIPs into data/cache/fec_data/ (resume-safe).
#
# Usage (repo root):
#   ./scripts/datasources/fec/run_bulk_download.sh
#   ./scripts/datasources/fec/run_bulk_download.sh --years 2022,2024 --types indiv,cn,cm
#   FEC_DATA_DIR=/other/path ./scripts/datasources/fec/run_bulk_download.sh --dry-run

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
export FEC_DATA_DIR="${FEC_DATA_DIR:-$ROOT/data/cache/fec_data}"
mkdir -p "$FEC_DATA_DIR"

LOG_DIR="$ROOT/data/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/fec_bulk_download_$(date +%Y%m%dT%H%M%S).log"

echo "FEC bulk download → $FEC_DATA_DIR"
echo "Log: $LOG"

exec "$PYTHON" -m ingestion.fec.bulk --resume "$@" 2>&1 | tee -a "$LOG"
