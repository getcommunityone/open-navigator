#!/usr/bin/env python3
"""
Rewrite ``_manifest.json`` under the scraped-meetings tree so ``pdfs[].year`` is a JSON string.

Older manifests used numeric years; the meetings pipeline now emits strings. This script migrates
existing files in place (optional ``--dry-run``).

Default root: ``SCRAPED_MEETINGS_ROOT`` env, else ``<repo>/data/cache/scraped_meetings``.

Usage::

    .venv/bin/python scripts/discovery/fix_scraped_meetings_manifest_years.py --dry-run
    .venv/bin/python scripts/discovery/fix_scraped_meetings_manifest_years.py
    .venv/bin/python scripts/discovery/fix_scraped_meetings_manifest_years.py --root /path/to/scraped_meetings
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

_root = Path(__file__).resolve().parents[2]
for _p in (str(_root), str(_root / "packages" / "core-lib" / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from core_lib.gdrive_paths import resolve_scraped_meetings_output_root
except Exception:  # pragma: no cover
    resolve_scraped_meetings_output_root = None  # type: ignore[misc,assignment]


def _default_root() -> Path:
    raw = (os.getenv("SCRAPED_MEETINGS_ROOT") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    if resolve_scraped_meetings_output_root:
        return Path(resolve_scraped_meetings_output_root()).resolve()
    return (_root / "data" / "cache" / "scraped_meetings").resolve()


def _fix_pdf_years(pdfs: Any) -> Tuple[int, List[Dict[str, Any]]]:
    if not isinstance(pdfs, list):
        return 0, []
    changed = 0
    out: List[Dict[str, Any]] = []
    for row in pdfs:
        if not isinstance(row, dict):
            out.append(row)  # type: ignore[arg-type]
            continue
        y = row.get("year")
        if isinstance(y, int) and 1000 <= y <= 9999:
            row = {**row, "year": str(y)}
            changed += 1
        elif isinstance(y, float) and y == int(y) and 1000 <= int(y) <= 9999:
            row = {**row, "year": str(int(y))}
            changed += 1
        out.append(row)
    return changed, out


def fix_manifest(path: Path, *, dry_run: bool) -> int:
    raw = path.read_text(encoding="utf-8")
    data: Dict[str, Any] = json.loads(raw)
    n, pdfs = _fix_pdf_years(data.get("pdfs"))
    if n == 0:
        return 0
    data["pdfs"] = pdfs
    if dry_run:
        return n
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description="Coerce pdfs[].year to string in scraped meetings manifests.")
    ap.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Directory containing jurisdiction trees with _manifest.json (default: SCRAPED_MEETINGS_ROOT or data/cache/scraped_meetings)",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print counts only; do not write files")
    args = ap.parse_args()
    root = (args.root or _default_root()).resolve()
    if not root.is_dir():
        print(f"error: root is not a directory: {root}", file=sys.stderr)
        return 1

    manifests = sorted(root.rglob("_manifest.json"))
    total_files = 0
    total_fields = 0
    for m in manifests:
        n = fix_manifest(m, dry_run=args.dry_run)
        if n:
            total_files += 1
            total_fields += n
            print(f"{'would update' if args.dry_run else 'updated'} {n} year field(s): {m}")

    print(
        f"done: {len(manifests)} manifest(s) scanned, "
        f"{total_files} file(s) with int/float years, {total_fields} pdf year field(s) coerced to string"
        + (" (dry-run)" if args.dry_run else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
