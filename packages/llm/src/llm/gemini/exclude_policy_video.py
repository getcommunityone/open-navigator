#!/usr/bin/env python3
"""
Flag a YouTube upload as not a municipal meeting and move policy artifacts aside.

Moves matching files from ``01_transcripts`` … ``04_runs`` into::

    ``05_exceptions/<stem>/``

and appends to ``05_exceptions/_excluded_videos.json``. By default also sets bronze
``transcript_source`` to ``excluded:<reason>`` with ``has_transcript=false`` so
``each`` / ``analyze`` / caption backfill skip the video.

Examples::

    python -m llm.gemini.exclude_policy_video \\
        --path data/cache/gemini_transcript_policy/MA/municipality/boston_2507000/UCImopNmmU11qfuWBbiXdowQ/02_analysis/2026-05-21_Haitian_Flag_Raising_2026_-_Promo.json \\
        --reason non_meeting --note "promo, not a council meeting"

    python -m llm.gemini.exclude_policy_video \\
        --path data/cache/gemini_transcript_policy/GA/municipality/dublin_1324376/UCxxc9YlL425MrKGFzaGW27Q/03_reports/2026-05-20_Join_the_Club_at_Premier_Heating_&_Air_Today!.md

    python -m llm.gemini.exclude_policy_video --dry-run \\
        --path path/to/02_analysis/foo.json --path path/to/other.json
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[5]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from llm.gemini.policy_exclusions import (  # noqa: E402
    DEFAULT_REASON,
    exclude_policy_video_at_path,
)


def _database_url(explicit: str) -> str:
    return (
        explicit
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or ""
    )


def main() -> None:
    load_dotenv(_REPO_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--path",
        action="append",
        default=[],
        help="Analysis JSON, report .md, transcript JSON, or run .meta.json",
    )
    ap.add_argument(
        "--reason",
        default=DEFAULT_REASON,
        help="Exclusion reason slug (default: non_meeting)",
    )
    ap.add_argument("--note", default="", help="Optional human note in manifest")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--no-write-bronze",
        action="store_true",
        help="Do not mark bronze.bronze_event_youtube_transcript as excluded",
    )
    ap.add_argument("--database-url", default="")
    args = ap.parse_args()

    paths = [Path(p).expanduser() for p in args.path]
    if not paths:
        ap.error("Pass at least one --path")

    db_url = _database_url(args.database_url)
    if not args.no_write_bronze and not db_url:
        logger.warning("No DATABASE_URL — skipping bronze exclusion rows")

    for path in paths:
        result = exclude_policy_video_at_path(
            path,
            reason=args.reason,
            note=args.note,
            dry_run=args.dry_run,
            write_bronze=not args.no_write_bronze,
            database_url=db_url or None,
        )
        logger.success(
            "{} {} — moved {} file(s) to 05_exceptions/{}/",
            "Would exclude" if args.dry_run else "Excluded",
            result["video_id"],
            len(result["moved"]),
            result["stem"],
        )


if __name__ == "__main__":
    main()
