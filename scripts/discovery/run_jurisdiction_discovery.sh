#!/usr/bin/env bash
# One entrypoint: same as python -m scripts.discovery.jurisdiction_discovery_pipeline
# Example: ./scripts/discovery/run_jurisdiction_discovery.sh --state AL --include-states
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
exec .venv/bin/python -m scripts.discovery.jurisdiction_discovery_pipeline "$@"
