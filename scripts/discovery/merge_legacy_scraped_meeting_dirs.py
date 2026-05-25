#!/usr/bin/env python3
"""
Merge duplicate ``scraped_meetings`` municipality folders into the canonical path and remove legacy aliases.

Canonical folder names come from ``jurisdiction_cache_folder_name()`` (LSAD-stripped slug + GEOID).
All other on-disk folders sharing the same 7-digit GEOID suffix are merged into that directory, then deleted.

Priority states default matches ``scrape_priority_states.DEFAULT_PRIORITY_STATES``.

Usage (repo root):
  .venv/bin/python scripts/discovery/merge_legacy_scraped_meeting_dirs.py --dry-run
  .venv/bin/python scripts/discovery/merge_legacy_scraped_meeting_dirs.py
  .venv/bin/python scripts/discovery/merge_legacy_scraped_meeting_dirs.py --states AL,GA
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.datasources.jurisdiction_pilot.scrape_priority_states import DEFAULT_PRIORITY_STATES

_GEOID_SUFFIX_RE = re.compile(r"_(\d{7})$")


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return
    load_dotenv(_root / ".env")


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def merge_tree(src: Path, dst: Path, *, dry_run: bool) -> Tuple[int, int]:
    """Copy files from ``src`` into ``dst`` when dest missing or src is larger. Returns (copied, skipped)."""
    copied = skipped = 0
    if not src.is_dir():
        return copied, skipped
    for f in sorted(src.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(src)
        target = dst / rel
        if target.exists() and _file_size(target) >= _file_size(f):
            skipped += 1
            continue
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
        copied += 1
    return copied, skipped


def plan_for_state(
    root: Path,
    state_code: str,
) -> List[Dict[str, Any]]:
    from scripts.gemini.transcript_cache_paths import jurisdiction_cache_folder_name

    muni = root / state_code.upper() / "municipality"
    if not muni.is_dir():
        return []

    by_geoid: Dict[str, List[Path]] = {}
    for p in muni.iterdir():
        if not p.is_dir():
            continue
        m = _GEOID_SUFFIX_RE.search(p.name)
        if not m:
            continue
        by_geoid.setdefault(m.group(1), []).append(p)

    plans: List[Dict[str, Any]] = []
    for geoid, paths in sorted(by_geoid.items()):
        jid = f"municipality_{geoid}"
        canonical_name = jurisdiction_cache_folder_name(jid)
        canonical_path = muni / canonical_name
        on_disk = {p.name: p for p in paths}
        if canonical_name not in on_disk:
            # e.g. only legacy aliases exist — still use canonical name as target
            pass
        for name, src in sorted(on_disk.items()):
            if name == canonical_name:
                continue
            src_bytes = sum(_file_size(f) for f in src.rglob("*") if f.is_file())
            plans.append(
                {
                    "state": state_code.upper(),
                    "geoid": geoid,
                    "jurisdiction_id": jid,
                    "canonical": canonical_name,
                    "legacy": name,
                    "legacy_path": str(src),
                    "canonical_path": str(canonical_path),
                    "legacy_bytes": src_bytes,
                    "canonical_exists": canonical_path.is_dir(),
                }
            )
    return plans


def run_cleanup(
    *,
    states: Tuple[str, ...],
    root: Path,
    dry_run: bool,
) -> Dict[str, Any]:
    merged: List[Dict[str, Any]] = []
    errors: List[str] = []
    total_copied = 0
    total_deleted = 0

    for st in states:
        for plan in plan_for_state(root, st):
            src = Path(plan["legacy_path"])
            dst = Path(plan["canonical_path"])
            try:
                if not dry_run:
                    dst.mkdir(parents=True, exist_ok=True)
                copied, skipped = merge_tree(src, dst, dry_run=dry_run)
                total_copied += copied
                if not dry_run:
                    shutil.rmtree(src)
                total_deleted += 1
                plan["files_copied"] = copied
                plan["files_skipped"] = skipped
                plan["deleted"] = not dry_run
                merged.append(plan)
            except OSError as exc:
                errors.append(f"{src}: {exc!r}")

    return {
        "dry_run": dry_run,
        "states": list(states),
        "folders_merged": len(merged),
        "files_copied": total_copied,
        "folders_removed": total_deleted,
        "errors": errors,
        "details": merged,
    }


def main() -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--states",
        default=",".join(DEFAULT_PRIORITY_STATES),
        help=f"Comma-separated USPS codes (default: {','.join(DEFAULT_PRIORITY_STATES)})",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=_root / "data" / "cache" / "scraped_meetings",
        help="scraped_meetings cache root",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    states = tuple(s.strip().upper() for s in args.states.split(",") if s.strip())
    report = run_cleanup(states=states, root=args.root, dry_run=args.dry_run)
    print(json.dumps({k: v for k, v in report.items() if k != "details"}, indent=2))
    if args.dry_run and report.get("details"):
        print("\nSample merges (legacy -> canonical):")
        for row in sorted(report["details"], key=lambda r: -int(r.get("legacy_bytes") or 0))[:20]:
            print(
                f"  {row['state']} {row['legacy']} -> {row['canonical']} "
                f"({row['legacy_bytes'] / 1024:.1f} KB)"
            )
        if len(report["details"]) > 20:
            print(f"  ... +{len(report['details']) - 20} more")
    return 1 if report.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
