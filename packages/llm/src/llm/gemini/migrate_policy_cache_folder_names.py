#!/usr/bin/env python3
"""Rename policy cache folders from ``municipality_{geoid}`` to ``{place_slug}_{geoid}``."""

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

from llm.gemini.transcript_cache_paths import migrate_policy_cache_folder_names  # noqa: E402

DEFAULT_CACHE = _REPO_ROOT / "data" / "cache" / "gemini_transcript_policy"
SCRAPED_ROOT = _REPO_ROOT / "data" / "cache" / "scraped_meetings"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument(
        "--scraped-meetings",
        action="store_true",
        help="Also rename folders under data/cache/scraped_meetings",
    )
    parser.add_argument("--jurisdiction-id", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for label, root in (
        ("policy", Path(args.cache_dir).resolve()),
        *(
            [("scraped_meetings", SCRAPED_ROOT)]
            if args.scraped_meetings and SCRAPED_ROOT.is_dir()
            else []
        ),
    ):
        stats = migrate_policy_cache_folder_names(
            root,
            dry_run=args.dry_run,
            jurisdiction_id=args.jurisdiction_id.strip(),
        )
        for key, value in sorted(stats.items()):
            logger.info("{} {}: {}", label, key, value)

    if args.dry_run:
        logger.info("Dry run — no folders renamed")


if __name__ == "__main__":
    main()
