#!/bin/bash
# Helper script to download ACS data with proper Python environment
# Usage: ./download_census_acs.sh [options]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Recreate venv if needed (fixes broken symlinks)
if [ ! -f "$SCRIPT_DIR/.venv/bin/python" ] || [ "$(head -1 "$SCRIPT_DIR/.venv/bin/pip" | grep 'oral-health-policy-pulse')" ]; then
    echo "🔧 Virtual environment has issues, recreating..."
    rm -rf "$SCRIPT_DIR/.venv"
    python3 -m venv "$SCRIPT_DIR/.venv"
    source "$SCRIPT_DIR/.venv/bin/activate"
    pip install -r "$PROJECT_ROOT/requirements.txt"
fi

# Activate venv
source "$SCRIPT_DIR/.venv/bin/activate"

# Only reinstall dependencies if requirements.txt has changed
REQS_HASH_FILE="$SCRIPT_DIR/.venv/.requirements_hash"
CURRENT_HASH=$(md5sum "$PROJECT_ROOT/requirements.txt" | cut -d' ' -f1)
if [ ! -f "$REQS_HASH_FILE" ] || [ "$(cat "$REQS_HASH_FILE")" != "$CURRENT_HASH" ]; then
    echo "Installing/updating dependencies..."
    pip install -r "$PROJECT_ROOT/requirements.txt"
    echo "$CURRENT_HASH" > "$REQS_HASH_FILE"
fi

# Run from project root so `from scripts.datasources.census...` imports resolve
cd "$PROJECT_ROOT" && python "$SCRIPT_DIR/download_census_acs_data.py" --data-dir ~/gdrive/"My Drive"/CommunityOne/open_navigator_data/acs "$@"
