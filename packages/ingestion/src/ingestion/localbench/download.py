"""Download the three released LocalBench QA files into a local cache.

Pulls the published files straight from the MadCollab/LocalBench GitHub repo
(``data/`` on ``main``) into ``data/cache/localbench/`` (override with
``--dest`` or ``LOCALBENCH_CACHE_DIR``). Idempotent: an already-present file of
the expected size is skipped unless ``--force`` is given. No API key needed.

Usage:
    python -m ingestion.localbench.download
    python -m ingestion.localbench.download --force
    python -m ingestion.localbench.download --dest /tmp/lb
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from pathlib import Path

from loguru import logger

from core_lib.logging import setup_logging

RAW_BASE = "https://raw.githubusercontent.com/MadCollab/LocalBench/main/data"

# filename -> published byte size (sanity check; from the GitHub contents API).
FILES: dict[str, int] = {
    "census_QA.csv": 1_480_613,
    "reddit_QA.parquet": 1_170_600,
    "news_QA.parquet": 1_318_574,
}


def default_cache_dir() -> Path:
    """Resolve the cache dir: ``LOCALBENCH_CACHE_DIR`` or ``data/cache/localbench``.

    The fallback is anchored to the repo root (four parents up from this file:
    ``localbench/`` → ``ingestion/`` → ``src/`` → ``ingestion(pkg)/`` …), but we
    walk up looking for a ``data/`` dir so it works regardless of CWD.
    """
    env = os.getenv("LOCALBENCH_CACHE_DIR")
    if env:
        return Path(env).expanduser()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "data").is_dir() and (parent / "packages").is_dir():
            return parent / "data" / "cache" / "localbench"
    return Path("data/cache/localbench")


def download_file(name: str, dest_dir: Path, *, force: bool = False) -> Path:
    """Download a single LocalBench file into ``dest_dir``; return its path."""
    dest = dest_dir / name
    expected = FILES.get(name)
    if dest.exists() and not force:
        size = dest.stat().st_size
        if expected is None or size == expected:
            logger.info("Skipping {} (already present, {:,} bytes)", name, size)
            return dest
        logger.warning(
            "{} present but size {:,} != expected {:,}; re-downloading",
            name,
            size,
            expected,
        )
    url = f"{RAW_BASE}/{name}"
    logger.info("Downloading {} → {}", url, dest)
    urllib.request.urlretrieve(url, dest)  # noqa: S310 (trusted https URL)
    size = dest.stat().st_size
    if expected is not None and size != expected:
        logger.warning("{}: downloaded {:,} bytes, expected {:,}", name, size, expected)
    logger.success("Saved {} ({:,} bytes)", name, size)
    return dest


def download_all(dest_dir: Path | None = None, *, force: bool = False) -> dict[str, Path]:
    """Download all three LocalBench files; return {filename: path}."""
    dest_dir = dest_dir or default_cache_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    logger.info("LocalBench cache dir: {}", dest_dir)
    return {name: download_file(name, dest_dir, force=force) for name in FILES}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download the three released LocalBench QA files into a cache dir"
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Destination dir (default: $LOCALBENCH_CACHE_DIR or data/cache/localbench)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Re-download even if files already exist"
    )
    return parser


def main() -> int:
    setup_logging()
    args = build_parser().parse_args()
    paths = download_all(args.dest, force=args.force)
    logger.success("Downloaded {} LocalBench files.", len(paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
