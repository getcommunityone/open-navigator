#!/usr/bin/env python3
"""Rename caption-cache transcripts to audio-aligned basenames (``YYYY-MM-DD_<title>.json``)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.gemini.transcript_cache_paths import migrate_transcript_cache_names  # noqa: E402

DEFAULT_OUTPUT_DIR = _REPO_ROOT / "data" / "cache" / "gemini_transcript_policy"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jurisdiction-id", default="municipality_0177256")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    folder = Path(args.cache_dir).resolve() / args.jurisdiction_id.strip()
    if not folder.is_dir():
        raise SystemExit(f"Not found: {folder}")

    renamed, skipped, warnings = migrate_transcript_cache_names(folder, dry_run=args.dry_run)
    for w in warnings:
        logger.info(w)
    logger.info("Renamed {} file(s), skipped {}", renamed, skipped)
    if args.dry_run:
        logger.info("Dry run — no files changed")


if __name__ == "__main__":
    main()
