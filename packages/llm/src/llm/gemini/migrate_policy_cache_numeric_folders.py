#!/usr/bin/env python3
"""
Merge numeric-only policy-cache folders into canonical ``{place_slug}_{geoid}/``.

Legacy YouTube loaders sometimes wrote ``159472`` (geoid ``0159472`` without a leading zero)
instead of ``phenix_city_0159472``. Bronze may already be normalized while stale cache
folders remain.

Usage (repo root)::

    .venv/bin/python -m llm.gemini.migrate_policy_cache_numeric_folders --dry-run
    .venv/bin/python -m llm.gemini.migrate_policy_cache_numeric_folders
    .venv/bin/python -m llm.gemini.migrate_policy_cache_numeric_folders \\
        --jurisdiction-id phenix_city_0159472
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[5]
load_dotenv(_REPO_ROOT / ".env")
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from llm.gemini.transcript_cache_paths import (  # noqa: E402
    build_numeric_policy_folder_mapping,
    list_numeric_policy_geo_dirs,
    load_int_jurisdictions_for_numeric_migration,
    migrate_policy_cache_numeric_folders,
)

DEFAULT_CACHE = _REPO_ROOT / "data" / "cache" / "gemini_transcript_policy"


def _database_url(explicit: str) -> str:
    return (
        explicit
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or ""
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--database-url", default="")
    parser.add_argument("--jurisdiction-id", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir).resolve()
    db_url = _database_url(args.database_url.strip())
    rows = load_int_jurisdictions_for_numeric_migration(db_url)
    if not rows:
        raise SystemExit("Set DATABASE_URL or NEON_DATABASE_URL_DEV (int_jurisdictions required)")

    numeric_dirs = list_numeric_policy_geo_dirs(cache_dir)
    if not numeric_dirs:
        logger.info("No numeric-only policy-cache folders under {}", cache_dir)
        return 0

    mapping = build_numeric_policy_folder_mapping(
        cache_dir,
        rows,
        jurisdiction_id_filter=args.jurisdiction_id.strip(),
    )
    for legacy, canonical in sorted(mapping.items()):
        logger.info("map: {} → {}", legacy, canonical)

    stats = migrate_policy_cache_numeric_folders(
        cache_dir,
        jurisdictions=rows,
        dry_run=args.dry_run,
        jurisdiction_id=args.jurisdiction_id.strip(),
    )
    for key, value in sorted(stats.items()):
        logger.info("{}: {}", key, value)

    if args.dry_run:
        logger.info("Dry run — no folders changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
