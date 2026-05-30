#!/usr/bin/env python3
"""
Rename policy-cache files to audio-aligned basenames (``YYYY-MM-DD_<title>.*``).

By default, only legacy ``{video_id}_transcript.json`` files are renamed. Use
``--fix-dates-from-title`` to correct upload-date prefixes (e.g. ``2025-04-04_…``
→ ``2024-09-23_…`` when the title says ``9/23/2024``).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[5]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from llm.gemini.transcript_cache_paths import (  # noqa: E402
    ensure_jurisdiction_layout,
    fix_policy_cache_dates_from_title,
    migrate_transcript_cache_names,
)

DEFAULT_OUTPUT_DIR = _REPO_ROOT / "data" / "cache" / "gemini_transcript_policy"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jurisdiction-id", default="municipality_0177256")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--fix-dates-from-title",
        action="store_true",
        help="Rename all step folders using meeting date from title; patch JSON event_date",
    )
    args = parser.parse_args()

    folder = Path(args.cache_dir).resolve() / args.jurisdiction_id.strip()
    if not folder.is_dir():
        raise SystemExit(f"Not found: {folder}")

    ensure_jurisdiction_layout(folder)
    if args.fix_dates_from_title:
        stats = fix_policy_cache_dates_from_title(folder, dry_run=args.dry_run)
        for key, value in sorted(stats.items()):
            logger.info("{}: {}", key, value)
    else:
        renamed, skipped, warnings = migrate_transcript_cache_names(
            folder, dry_run=args.dry_run
        )
        for w in warnings:
            logger.info(w)
        logger.info("Renamed {} file(s), skipped {}", renamed, skipped)
    if args.dry_run:
        logger.info("Dry run — no files changed")


if __name__ == "__main__":
    main()
