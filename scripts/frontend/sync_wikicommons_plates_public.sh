#!/usr/bin/env bash
# Copy Wikimedia Commons–cached license plate exports into the Vite public folder and
# regenerate the USPS → filename map consumed by the UI (see frontend/src/utils/wikicommonsLicensePlate.ts).
# Source: data/cache/wikicommons (from scripts/wikicommons/download_wikicommons_assets.*).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="${ROOT}/data/cache/wikicommons"
DST="${ROOT}/frontend/public/wikicommons"
DATA_JSON="${ROOT}/frontend/src/data/wikicommonsPlatesLatest.json"
mkdir -p "${DST}"
mkdir -p "$(dirname "${DATA_JSON}")"
shopt -s nullglob
n=0
for f in "${SRC}"/*_latest.*; do
  [[ -e "$f" ]] || continue
  base="$(basename "$f")"
  [[ "$base" == _* ]] && continue
  case "${base,,}" in
    *.jpg|*.jpeg|*.png|*.webp)
      cp -f "$f" "${DST}/${base}"
      n=$((n + 1))
      ;;
    *)
      ;;
  esac
done
export ROOT
python3 <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["ROOT"])
src = root / "data/cache/wikicommons"
out_json = root / "frontend/src/data/wikicommonsPlatesLatest.json"
by_usps: dict[str, str] = {}
for p in sorted(src.glob("*_latest.*")):
    name = p.name
    if name.startswith("_"):
        continue
    if p.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        continue
    usps = name.split("_")[0].upper()
    if len(usps) == 2 and usps.isalpha():
        by_usps[usps] = name

default_plate = by_usps.get("AL") or (next(iter(by_usps.values())) if by_usps else None)
payload = {"default_plate": default_plate, "by_usps": by_usps}
out_json.parent.mkdir(parents=True, exist_ok=True)
out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(f"wrote {out_json} ({len(by_usps)} USPS keys, default={default_plate!r})")
PY
echo "Copied ${n} *_latest.* file(s) into ${DST}"
