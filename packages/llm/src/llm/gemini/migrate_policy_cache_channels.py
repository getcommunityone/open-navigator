#!/usr/bin/env python3
"""Move policy cache step folders under per-channel subdirectories."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[5]
load_dotenv(_REPO_ROOT / ".env")
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from llm.gemini.transcript_cache_paths import migrate_policy_cache_channels  # noqa: E402

DEFAULT_OUTPUT_DIR = _REPO_ROOT / "data" / "cache" / "gemini_transcript_policy"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--jurisdiction-id", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    stats = migrate_policy_cache_channels(
        Path(args.cache_dir).resolve(),
        dry_run=args.dry_run,
        jurisdiction_id=args.jurisdiction_id.strip(),
    )
    for key, value in sorted(stats.items()):
        logger.info("{}: {}", key, value)
    if args.dry_run:
        logger.info("Dry run — no files moved")


if __name__ == "__main__":
    main()
