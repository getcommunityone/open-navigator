#!/usr/bin/env python3
"""Organize flat gemini_transcript_policy files into dated step subfolders."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.gemini.transcript_cache_paths import (  # noqa: E402
    find_jurisdiction_root,
    migrate_policy_cache_layout,
)

DEFAULT_OUTPUT_DIR = _REPO_ROOT / "data" / "cache" / "gemini_transcript_policy"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jurisdiction-id", default="municipality_0177256")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir).resolve()
    jid = args.jurisdiction_id.strip()
    folder = find_jurisdiction_root(cache_dir, jid)
    if not folder.is_dir():
        raise SystemExit(f"Not found: {folder}")

    stats = migrate_policy_cache_layout(folder, dry_run=args.dry_run)
    for key, value in sorted(stats.items()):
        logger.info("{}: {}", key, value)
    if args.dry_run:
        logger.info("Dry run — no files changed")


if __name__ == "__main__":
    main()
