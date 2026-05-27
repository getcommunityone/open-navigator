#!/usr/bin/env python3
"""Download HIFLD datasets from ArcGIS Online as CSVs into the cache.

Uses the ArcGIS REST API directly (no arcgis SDK needed) via the core_lib
async HTTP client (retries + rate limiting + structured logs).

This is download-only: it fetches source CSV(s) into ``data/cache/hifld/``.
Loading into the database lives separately in ``ingestion.hifld.locations``.

Usage:
    python -m ingestion.hifld.download
    python -m ingestion.hifld.download --item-id 333a74c8e9c64cb6870689d31e8836af
    python -m ingestion.hifld.download --item-id 333a74c8e9c64cb6870689d31e8836af \\
        --output data/law_enforcement.csv
    python -m ingestion.hifld.download --all --force
"""
from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

import pandas as pd
from loguru import logger

from core_lib.http import BaseAsyncClient, HttpClientConfig
from core_lib.logging import setup_logging


CACHE_DIR = Path("data/cache/hifld")
ARCGIS_BASE_URL = "https://www.arcgis.com"
ARCGIS_ITEMS_PATH = "/sharing/rest/content/items"
PAGE_SIZE = 2000
CACHE_MAX_AGE_DAYS = 7

DATASETS = {
    "places_of_worship":  "495cc33ef490462ab2d8933247a66a87",
    "hospitals":          "f36521f6e07f4a859e838f0ad7536898",
    "law_enforcement":    "333a74c8e9c64cb6870689d31e8836af",
}


class HifldClient(BaseAsyncClient):
    """ArcGIS Online client for HIFLD datasets.

    ``base_url`` is arcgis.com (for item-metadata lookups); the per-dataset
    service URL is discovered dynamically and passed to ``get`` as an absolute
    URL. A modest rate limit is applied since layer queries are paginated and
    may loop over many pages.
    """

    def __init__(self) -> None:
        super().__init__(
            HttpClientConfig(
                base_url=ARCGIS_BASE_URL,
                source="hifld",
                timeout_s=60.0,
                rate_limit_per_sec=2.0,
            )
        )


def _is_cache_fresh(path: Path, max_age_days: float = CACHE_MAX_AGE_DAYS) -> bool:
    """Return True if ``path`` exists and is newer than ``max_age_days``."""
    if not path.exists():
        return False
    age_days = (time.time() - path.stat().st_mtime) / 86400
    return age_days < max_age_days


async def _get_service_url(client: HifldClient, item_id: str) -> str:
    resp = await client.get(f"{ARCGIS_ITEMS_PATH}/{item_id}", params={"f": "json"})
    data = resp.json()
    url = data.get("url")
    if not url:
        raise ValueError(
            f"No service URL found for item {item_id}. Title: {data.get('title')}"
        )
    return url.rstrip("/")


async def _download_layer_csv(
    client: HifldClient, service_url: str, layer_index: int = 0
) -> pd.DataFrame:
    query_url = f"{service_url}/{layer_index}/query"
    chunks = []
    offset = 0

    while True:
        params = {
            "where": "1=1",
            "outFields": "*",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
            "returnGeometry": "false",
        }
        resp = await client.get(query_url, params=params)
        data = resp.json()

        if "error" in data:
            raise RuntimeError(f"ArcGIS error: {data['error']}")

        features = data.get("features", [])
        if not features:
            break

        rows = [f["attributes"] for f in features]
        chunks.append(pd.DataFrame(rows))
        logger.info(f"  Retrieved {offset + len(rows):,} records...")

        if not data.get("exceededTransferLimit", False):
            break

        offset += PAGE_SIZE

    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks, ignore_index=True)


async def _download_item(
    client: HifldClient, item_id: str, output_path: Path, *, force: bool = False
) -> Path:
    if not force and _is_cache_fresh(output_path):
        logger.info(f"Using cached file: {output_path}")
        return output_path

    logger.info(f"Fetching service URL for item {item_id}...")
    service_url = await _get_service_url(client, item_id)
    logger.info(f"Downloading from {service_url}...")

    df = await _download_layer_csv(client, service_url)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.success(f"Saved {len(df):,} records to {output_path}")
    return output_path


async def download(
    *,
    force: bool = False,
    item_id: str | None = None,
    output: str | Path | None = None,
) -> Path | list[Path]:
    """Download HIFLD dataset CSV(s) into ``CACHE_DIR``.

    With ``item_id``, downloads a single dataset (to ``output`` or
    ``CACHE_DIR/<item_id>.csv``) and returns its :class:`Path`. Otherwise
    downloads every known dataset in :data:`DATASETS` and returns a list of
    paths. Fresh cached files are reused unless ``force`` is set.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    async with HifldClient() as client:
        if item_id:
            out = Path(output) if output else CACHE_DIR / f"{item_id}.csv"
            return await _download_item(client, item_id, out, force=force)

        logger.info(f"Downloading {len(DATASETS)} HIFLD datasets...")
        paths: list[Path] = []
        for name, ds_item_id in DATASETS.items():
            logger.info(f"--- {name} ({ds_item_id}) ---")
            paths.append(
                await _download_item(
                    client, ds_item_id, CACHE_DIR / f"{name}.csv", force=force
                )
            )
        logger.success("All datasets downloaded.")
        return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download HIFLD datasets as CSV")
    parser.add_argument("--item-id", help="ArcGIS item ID (downloads single dataset)")
    parser.add_argument("--output", help="Output CSV path (only used with --item-id)")
    parser.add_argument("--all", action="store_true", help="Download all known datasets")
    parser.add_argument(
        "--force", action="store_true", help="Re-download even if cached file is fresh"
    )
    return parser


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(
        download(force=args.force, item_id=args.item_id, output=args.output)
    )


if __name__ == "__main__":
    main()
