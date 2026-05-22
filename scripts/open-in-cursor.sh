#!/usr/bin/env bash
# Open this repo in Cursor on WSL (run from anywhere).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CURSOR="${CURSOR_BIN:-/mnt/c/Program Files/cursor/resources/app/bin/cursor}"
exec "$CURSOR" "$REPO_ROOT"
