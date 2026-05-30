#!/usr/bin/env python3
"""
Fix policy transcript cache filenames and remove duplicate caption sidecars.

1. Rename ``unknown-date_*`` → ``YYYY-MM-DD_*`` using title / JSON metadata.
2. Delete ``*.caption_raw_data.json`` when the main ``*.json`` already embeds captions.
3. Delete legacy ``*.caption_formatted.json`` duplicates.

Usage (repo root)::

    .venv/bin/python -m llm.gemini.cleanup_policy_transcript_cache --dry-run
    .venv/bin/python -m llm.gemini.cleanup_policy_transcript_cache

    # One channel folder:
    .venv/bin/python -m llm.gemini.cleanup_policy_transcript_cache \\
        --channel-root data/cache/gemini_transcript_policy/IN/county/adams_18001/UChLPCfjJNqdeaJmFc61OoOw
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger

_REPO = Path(__file__).resolve().parents[5]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from llm.gemini.transcript_cache_paths import (  # noqa: E402
    cleanup_policy_transcript_cache_tree,
    fix_policy_cache_dates_from_title,
    remove_redundant_transcript_files,
)

DEFAULT_CACHE = _REPO / "data" / "cache" / "gemini_transcript_policy"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE,
        help="Policy cache root (default: data/cache/gemini_transcript_policy)",
    )
    parser.add_argument(
        "--channel-root",
        type=Path,
        default=None,
        help="Only clean this …/{channel_id}/ folder (must contain 01_transcripts/)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.channel_root is not None:
        root = args.channel_root.resolve()
        if not (root / "01_transcripts").is_dir():
            logger.error("No 01_transcripts/ under {}", root)
            return 2
        date_stats = fix_policy_cache_dates_from_title(root, dry_run=args.dry_run)
        sidecar_stats = remove_redundant_transcript_files(root, dry_run=args.dry_run)
        for key, value in sorted({**date_stats, **sidecar_stats}.items()):
            logger.info("{}: {}", key, value)
    else:
        totals = cleanup_policy_transcript_cache_tree(
            args.cache_dir.resolve(), dry_run=args.dry_run
        )
        for key, value in sorted(totals.items()):
            logger.info("{}: {}", key, value)

    if args.dry_run:
        logger.info("Dry run — no files changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
