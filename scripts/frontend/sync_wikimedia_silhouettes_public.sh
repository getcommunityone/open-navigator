#!/usr/bin/env bash
# Copy Wikimedia-cached state silhouette SVGs into the Vite public folder and
# regenerate the USPS → filename map consumed by the UI (see frontend/src/utils/wikimediaStateSilhouette.ts).
# Source: data/cache/wikimedia (from scripts/wikimedia/download_state_silhouettes.py).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="${ROOT}/data/cache/wikimedia"
DST="${ROOT}/frontend/public/wikimedia"
DATA_JSON="${ROOT}/frontend/src/data/wikimediaStateSilhouettes.json"
mkdir -p "${DST}"
mkdir -p "$(dirname "${DATA_JSON}")"
shopt -s nullglob
n=0
for f in "${SRC}"/*_silhouette.svg; do
  [[ -e "$f" ]] || continue
  base="$(basename "$f")"
  cp -f "$f" "${DST}/${base}"
  n=$((n + 1))
done
export ROOT
python3 <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["ROOT"])
src = root / "data/cache/wikimedia"
out_json = root / "frontend/src/data/wikimediaStateSilhouettes.json"
by_usps: dict[str, str] = {}
for p in sorted(src.glob("*_silhouette.svg")):
    name = p.name
    usps = name.split("_")[0].upper()
    if len(usps) == 2 and usps.isalpha():
        by_usps[usps] = name

default_silhouette = by_usps.get("GA") or (next(iter(by_usps.values())) if by_usps else None)
payload = {"default_silhouette": default_silhouette, "by_usps": by_usps}
out_json.parent.mkdir(parents=True, exist_ok=True)
out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(f"wrote {out_json} ({len(by_usps)} USPS keys, default={default_silhouette!r})")
PY
echo "Copied ${n} *_silhouette.svg file(s) into ${DST}"
