#!/usr/bin/env python3
"""Print uncontested_items with presenter / timestamp fields from a Part 1 analysis JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.gemini.transcript_cache_paths import (  # noqa: E402
    iter_analysis_files,
    resolve_analysis_path,
)

DEFAULT_CACHE = _REPO / "data" / "cache" / "gemini_transcript_policy"


def resolve_analysis_paths(
    paths: List[Path],
    *,
    video_id: str = "",
    jurisdiction_id: str = "",
    cache_dir: Path = DEFAULT_CACHE,
) -> List[Path]:
    """Resolve explicit paths, or newest analysis JSON under cache."""
    resolved: List[Path] = []
    for p in paths:
        if p.is_file():
            resolved.append(p.resolve())
        elif "*" in str(p):
            resolved.extend(sorted(cache_dir.rglob(str(p.name)), key=lambda x: x.stat().st_mtime))
    if resolved:
        return resolved
    jid = (jurisdiction_id or "municipality_0177256").strip()
    vid = (video_id or "").strip()
    if vid:
        one = resolve_analysis_path(cache_dir, jid, video_id=vid)
        return [one] if one else []
    return iter_analysis_files(cache_dir, jid)


def print_report(path: Path, *, show_people: bool) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    people = {
        p["person_id"]: p.get("full_name")
        for p in (data.get("people") or [])
        if isinstance(p, dict) and p.get("person_id")
    }

    print(f"file: {path.name}\n")
    if show_people:
        print("=== people[] ===")
        for pid, name in people.items():
            print(f"  {pid} -> {name}")
        print()

    items = data.get("uncontested_items") or []
    print(f"=== uncontested_items ({len(items)}) ===")
    has_new_fields = any(
        isinstance(r, dict) and (r.get("presenter_person_ids") or r.get("media_anchor"))
        for r in items
    )
    if not has_new_fields:
        print(
            "(No presenter_person_ids / media_anchor — re-run meeting_transcript_policy.py "
            "after pulling latest prompts)\n"
        )

    for row in items:
        if not isinstance(row, dict):
            continue
        uid = row.get("item_id")
        headline = row.get("headline")
        presenters = row.get("presenter_person_ids") or []
        names = [people.get(pid, pid) for pid in presenters]
        anchor = row.get("media_anchor") or {}
        start = anchor.get("timestamp_start_seconds")
        end = anchor.get("timestamp_end_seconds")
        url = anchor.get("playback_url")
        motion = row.get("motion") or {}
        print(f"\n{uid}: {headline}")
        print(f"  presenters: {', '.join(names) or '(none)'}")
        if start is not None:
            print(f"  time: {start}s - {end}s")
        if url:
            print(f"  watch: {url}")
        if motion.get("moved_by_person_id") or motion.get("seconded_by_person_id"):
            print(f"  motion: {motion}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "analysis_json",
        nargs="*",
        type=Path,
        help="Analysis JSON path(s). If several match a glob, all are printed (newest first).",
    )
    parser.add_argument("--video-id", default="", help="Find newest *video_id*analysis.json")
    parser.add_argument("--jurisdiction-id", default="municipality_0177256")
    parser.add_argument("--latest-only", action="store_true", help="Only print newest match")
    parser.add_argument("--people", action="store_true", help="Show people[] roster")
    args = parser.parse_args()

    paths = resolve_analysis_paths(
        list(args.analysis_json),
        video_id=args.video_id,
        jurisdiction_id=args.jurisdiction_id,
    )
    if not paths:
        raise SystemExit("No analysis JSON found. Pass a file path or --video-id zpaawfaNsQM")

    if args.latest_only:
        paths = paths[:1]

    for path in paths:
        print_report(path, show_people=args.people)
        if len(paths) > 1:
            print("\n" + "-" * 60 + "\n")


if __name__ == "__main__":
    main()
