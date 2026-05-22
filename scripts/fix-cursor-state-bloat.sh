#!/usr/bin/env bash
# Cursor global state DB often bloats to GBs and triggers "not enough local storage".
# Quit Cursor completely before running this script.
set -euo pipefail

GLOBAL="${CURSOR_GLOBAL_STORAGE:-$HOME/../../Users/jcbow/AppData/Roaming/Cursor/User/globalStorage}"
# WSL default for this machine:
if [[ ! -d "$GLOBAL" ]]; then
  GLOBAL="/mnt/c/Users/jcbow/AppData/Roaming/Cursor/User/globalStorage"
fi

if tasklist.exe 2>/dev/null | grep -qi '^Cursor\.exe'; then
  echo "Close all Cursor windows first (File → Exit), then run this again." >&2
  exit 1
fi

if [[ ! -f "$GLOBAL/state.vscdb" ]]; then
  echo "No state.vscdb at $GLOBAL" >&2
  exit 1
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
ARCHIVE="$GLOBAL/archive-bloat-$STAMP"
mkdir -p "$ARCHIVE"

for f in state.vscdb state.vscdb.backup state.vscdb-shm state.vscdb-wal; do
  if [[ -e "$GLOBAL/$f" ]]; then
    mv "$GLOBAL/$f" "$ARCHIVE/"
    echo "Archived $f"
  fi
done

ls -lah "$ARCHIVE"
echo ""
echo "Done. Start Cursor again (cursor .). It will create a fresh state.vscdb."
echo "Archived files kept at: $ARCHIVE"
echo "You can delete that folder later to free ~7+ GB on C:."
