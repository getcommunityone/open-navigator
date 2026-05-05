#!/bin/bash
# Helper script to download ACS data with proper Python environment
# Usage: ./download_acs.sh [options]

# Recreate venv if needed (fixes broken symlinks)
if [ ! -f .venv/bin/python ] || [ "$(head -1 .venv/bin/pip | grep 'oral-health-policy-pulse')" ]; then
    echo "🔧 Virtual environment has issues, recreating..."
    rm -rf .venv
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
fi

# Activate venv
source .venv/bin/activate

# Run the download script with all arguments passed through
python examples/download_acs_to_d_drive.py "$@"
