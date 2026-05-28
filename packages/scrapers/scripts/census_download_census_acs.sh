#!/bin/bash
# Helper script for ad-hoc ACS downloads with a managed venv.
#
# Prefer `python scripts/download_bronze.py --only acs` from the project's
# main venv when running as part of the bronze pipeline. This wrapper exists
# for one-off invocations on machines where the project venv isn't active.
#
# Usage:
#   ./download_census_acs.sh                            # uses default cache dir
#   ./download_census_acs.sh --state 06                 # CA counties only
#   ACS_DATA_DIR=/mnt/d/acs ./download_census_acs.sh    # custom output dir
#   ./download_census_acs.sh --data-dir /mnt/d/acs ...  # also works
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

# Recreate venv if its python is missing (e.g., broken symlinks after a move).
if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "🔧 Creating virtual environment at $VENV_DIR..."
    rm -rf "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    pip install -r "$PROJECT_ROOT/requirements.txt"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Only reinstall deps if requirements.txt changed.
REQS_HASH_FILE="$VENV_DIR/.requirements_hash"
CURRENT_HASH="$(md5sum "$PROJECT_ROOT/requirements.txt" | cut -d' ' -f1)"
if [ ! -f "$REQS_HASH_FILE" ] || [ "$(cat "$REQS_HASH_FILE")" != "$CURRENT_HASH" ]; then
    echo "Installing/updating dependencies..."
    pip install -r "$PROJECT_ROOT/requirements.txt"
    echo "$CURRENT_HASH" > "$REQS_HASH_FILE"
fi

# Allow callers to override the data dir with $ACS_DATA_DIR; otherwise let the
# Python script use its default (data/cache/census/acs under the project root).
DATA_DIR_ARGS=()
if [ -n "${ACS_DATA_DIR:-}" ]; then
    DATA_DIR_ARGS=(--data-dir "$ACS_DATA_DIR")
fi

# Run from project root so `from scripts.datasources.census...` imports resolve.
cd "$PROJECT_ROOT" && python "$SCRIPT_DIR/download_census_acs_data.py" \
    "${DATA_DIR_ARGS[@]}" "$@"
