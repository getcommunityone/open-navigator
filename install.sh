#!/usr/bin/env bash
#
# Root convenience wrapper for the installer.
#
# The actual installation logic lives in scripts/deployment/install.sh. It uses
# paths relative to the current working directory (.venv/, requirements.txt,
# .env.example, logs/), so it must be run from the repository root — which is
# exactly where this wrapper lives. The docs and `make install` both invoke
# `./install.sh`, so keep this thin wrapper here rather than moving the script.
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${REPO_ROOT}/scripts/deployment/install.sh" "$@"
