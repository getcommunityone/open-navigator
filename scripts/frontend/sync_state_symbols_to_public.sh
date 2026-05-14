#!/usr/bin/env bash
# Legacy: state flag / collage JPGs from ``data/cache/state_symbols`` (State Symbols USA).
# License plates for the home hero now use ``sync_wikicommons_plates_public.sh`` + ``/wikicommons/``.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="${ROOT}/data/cache/state_symbols"
DST="${ROOT}/frontend/public/state-symbols"
mkdir -p "${DST}"
shopt -s nullglob
cp -f "${SRC}"/*.jpg "${DST}/"
echo "Synced $(ls -1 "${DST}"/*.jpg 2>/dev/null | wc -l) images into ${DST}"
