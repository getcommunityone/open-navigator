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
for f in "${SRC}"/*_silhouette*.svg; do
  [[ -e "$f" ]] || continue
  base="$(basename "$f")"
  cp -f "$f" "${DST}/${base}"
  n=$((n + 1))
done
export ROOT
python3 <<'PY'
import json
import os
import re
import shutil
from pathlib import Path

root = Path(os.environ["ROOT"])
src = root / "data/cache/wikimedia"
dst = root / "frontend/public/wikimedia"
out_json = root / "frontend/src/data/wikimediaStateSilhouettes.json"
manifest_path = src / "_manifest.json"
manifest: dict = {}
if manifest_path.is_file():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

by_usps: dict[str, str] = {}
by_usps_state: dict[str, str] = {}

for usps, entry in (manifest.get("files") or {}).items():
    if len(usps) != 2 or not usps.isalpha():
        continue
    variants = entry.get("variants") or {}
    locator = (variants.get("locator") or {}).get("local_file")
    state = (variants.get("state") or {}).get("local_file")
    if locator and (src / locator).is_file():
        by_usps[usps] = locator
    if state and (src / state).is_file():
        by_usps_state[usps] = state

for p in sorted(src.glob("*_silhouette_locator.svg")):
    usps = p.name.split("_")[0].upper()
    if len(usps) == 2 and usps.isalpha():
        by_usps.setdefault(usps, p.name)

for p in sorted(src.glob("*_silhouette_state.svg")):
    usps = p.name.split("_")[0].upper()
    if len(usps) == 2 and usps.isalpha():
        by_usps_state.setdefault(usps, p.name)

for p in sorted(src.glob("*_silhouette.svg")):
    name = p.name
    if name == "USA_silhouette.svg":
        continue
    usps = name.split("_")[0].upper()
    if len(usps) != 2 or not usps.isalpha():
        continue
    if usps in by_usps:
        continue
    # Legacy single file: map by old manifest strategy until re-download adds both variants.
    legacy_locator = src / f"{usps}_silhouette_locator.svg"
    if not legacy_locator.is_file():
        strategy = ((manifest.get("files") or {}).get(usps) or {}).get("strategy")
        if strategy == "state_of":
            by_usps_state.setdefault(usps, name)
        else:
            by_usps.setdefault(usps, name)

usa = src / "USA_silhouette.svg"
default_silhouette = "USA_silhouette.svg" if usa.is_file() else None
if usa.is_file():
    shutil.copy2(usa, dst / usa.name)

by_usps_outline: dict[str, str] = {}
usa_public = dst / "USA_silhouette.svg"
outline_dir = dst / "outlines"
if usa_public.is_file():
    outline_dir.mkdir(parents=True, exist_ok=True)
    try:
        from svgpathtools import parse_path
    except ImportError:
        parse_path = None  # type: ignore[misc, assignment]

    text = usa_public.read_text(encoding="utf-8")
    pattern = re.compile(r'<path\s+id="([A-Z]{2})"[^>]*\sd="([^"]+)"', re.DOTALL)
    for pid, d in pattern.findall(text):
        if parse_path is not None:
            p = parse_path(d)
            x0, x1, y0, y1 = p.bbox()
            pad = 3
            x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
            w, h = max(x1 - x0, 1), max(y1 - y0, 1)
            vb = f"{x0:.2f} {y0:.2f} {w:.2f} {h:.2f}"
        else:
            vb = "0 0 100 100"
        fname = f"{pid}_outline.svg"
        svg = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">\n'
            f'  <path fill="#52796F" d="{d}"/>\n'
            "</svg>\n"
        )
        (outline_dir / fname).write_text(svg, encoding="utf-8")
        by_usps_outline[pid] = f"outlines/{fname}"

payload = {
    "default_silhouette": default_silhouette,
    "default_variant": manifest.get("default_variant") or "locator",
    "by_usps": by_usps,
    "by_usps_state": by_usps_state,
    "by_usps_outline": by_usps_outline,
}
out_json.parent.mkdir(parents=True, exist_ok=True)
out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(
    f"wrote {out_json} ({len(by_usps)} locator, {len(by_usps_state)} state, "
    f"{len(by_usps_outline)} outline, default={default_silhouette!r})"
)
PY
echo "Copied ${n} silhouette SVG file(s) into ${DST}"
