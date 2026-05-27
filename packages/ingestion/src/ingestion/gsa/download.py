"""GSA .gov domains downloader: fetch the cisagov/dotgov-data CSV into data/cache/gsa/.

Ported from download_gsa_domains.py to core_lib.http.BaseAsyncClient. This module is
download-only — the load step lives in ingestion.gsa.domains (DataSourcePipeline).
This is the reference pattern for porting scripts/datasources/*/download_*.py.

Usage:
    python -m ingestion.gsa.download
    python -m ingestion.gsa.download --force
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from core_lib.http import BaseAsyncClient, HttpClientConfig
from core_lib.logging import setup_logging


CACHE_DIR = Path("data/cache/gsa")
_BASE_URL = "https://raw.githubusercontent.com"
_CSV_PATH = "/cisagov/dotgov-data/main/current-full.csv"
_MAX_CACHE_AGE_S = 86_400  # reuse a cache file younger than 24h


class GsaDomainsClient(BaseAsyncClient):
    """BaseAsyncClient subclass for the cisagov/dotgov-data raw host."""

    def __init__(self) -> None:
        super().__init__(
            HttpClientConfig(
                base_url=_BASE_URL,
                source="gsa_domains",
                timeout_s=60.0,
                rate_limit_per_sec=None,  # single-file fetch; no throttle needed
            )
        )


def _cache_path() -> Path:
    return CACHE_DIR / f"dotgov_domains_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"


def _is_fresh(path: Path) -> bool:
    return path.exists() and (datetime.now().timestamp() - path.stat().st_mtime) < _MAX_CACHE_AGE_S


async def download(*, force: bool = False) -> Path:
    """Fetch current-full.csv into the GSA cache; reuse a <24h cache unless force."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = _cache_path()
    bound = logger.bind(source="gsa_domains")
    if not force and _is_fresh(out):
        bound.info(f"cache_hit {out}")
        return out
    async with GsaDomainsClient() as client:
        resp = await client.get(_CSV_PATH)
    out.write_bytes(resp.content)
    bound.info(f"downloaded {len(resp.content)} bytes -> {out}")
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download the GSA .gov domains CSV into data/cache/gsa/"
    )
    parser.add_argument("--force", action="store_true", help="Re-download even if a fresh cache exists")
    return parser


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    path = asyncio.run(download(force=args.force))
    logger.info(f"cache file: {path}")


if __name__ == "__main__":
    main()
