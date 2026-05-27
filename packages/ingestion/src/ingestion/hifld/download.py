#!/usr/bin/env python3
"""
Download HIFLD datasets from ArcGIS Online as CSVs.

Uses the ArcGIS REST API directly (no arcgis SDK needed).

Usage:
    python download_hifld.py
    python download_hifld.py --item-id 333a74c8e9c64cb6870689d31e8836af
    python download_hifld.py --item-id 333a74c8e9c64cb6870689d31e8836af --output data/law_enforcement.csv
"""
import argparse
import time
from pathlib import Path

import pandas as pd
import requests
from loguru import logger

CACHE_DIR = Path("data/cache/hifld")
ARCGIS_ITEMS_URL = "https://www.arcgis.com/sharing/rest/content/items"
PAGE_SIZE = 2000

DATASETS = {
    "places_of_worship":  "495cc33ef490462ab2d8933247a66a87",
    "hospitals":          "f36521f6e07f4a859e838f0ad7536898",
    "law_enforcement":    "333a74c8e9c64cb6870689d31e8836af",
}


def get_service_url(item_id: str) -> str:
    resp = requests.get(f"{ARCGIS_ITEMS_URL}/{item_id}", params={"f": "json"}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    url = data.get("url")
    if not url:
        raise ValueError(f"No service URL found for item {item_id}. Title: {data.get('title')}")
    return url.rstrip("/")


def download_layer_csv(service_url: str, layer_index: int = 0) -> pd.DataFrame:
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
        resp = requests.get(query_url, params=params, timeout=60)
        resp.raise_for_status()
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
        time.sleep(0.5)

    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks, ignore_index=True)


def download_item(item_id: str, output_path: Path) -> Path:
    if output_path.exists():
        age_days = (time.time() - output_path.stat().st_mtime) / 86400
        if age_days < 7:
            logger.info(f"Using cached file ({age_days:.0f} days old): {output_path}")
            return output_path

    logger.info(f"Fetching service URL for item {item_id}...")
    service_url = get_service_url(item_id)
    logger.info(f"Downloading from {service_url}...")

    df = download_layer_csv(service_url)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.success(f"Saved {len(df):,} records to {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Download HIFLD datasets as CSV")
    parser.add_argument("--item-id", help="ArcGIS item ID (downloads single dataset)")
    parser.add_argument("--output", help="Output CSV path (only used with --item-id)")
    parser.add_argument("--all", action="store_true", help="Download all known datasets")
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if args.item_id:
        output = Path(args.output) if args.output else CACHE_DIR / f"{args.item_id}.csv"
        download_item(args.item_id, output)
    else:
        datasets = DATASETS
        logger.info(f"Downloading {len(datasets)} HIFLD datasets...")
        for name, item_id in datasets.items():
            logger.info(f"\n--- {name} ({item_id}) ---")
            download_item(item_id, CACHE_DIR / f"{name}.csv")
        logger.success("\nAll datasets downloaded.")


if __name__ == "__main__":
    main()
