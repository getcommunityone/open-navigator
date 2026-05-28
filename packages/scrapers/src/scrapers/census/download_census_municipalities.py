#!/usr/bin/env python3
"""
Download Census Gazetteer municipalities (cities/towns) to local cache

Downloads the Census Gazetteer place file which contains all incorporated places,
CDPs (Census Designated Places), and other municipalities, and saves it as a
tab-to-CSV-converted file in the local cache.

**Source**: US Census Bureau Gazetteer Files
**URL**: https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html
**Cache**: data/cache/census/municipalities_YYYYMMDD.csv

Usage:
    python packages/scrapers/src/scrapers/census/download_census_municipalities.py
    python packages/scrapers/src/scrapers/census/download_census_municipalities.py --force
"""
import argparse
import io
import zipfile
from pathlib import Path
from datetime import datetime
import requests
from loguru import logger


GAZETTEER_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_place_national.zip"
CACHE_DIR = Path("data/cache/census")


def download_gazetteer_file(force: bool = False) -> Path:
    """
    Download Census Gazetteer place file and save as CSV to cache.

    Args:
        force: If True, re-download even if cached file exists

    Returns:
        Path to extracted CSV file
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cache_file = CACHE_DIR / f"municipalities_{datetime.now().strftime('%Y%m%d')}.csv"

    if cache_file.exists() and not force:
        logger.info(f"Using cached file: {cache_file}")
        return cache_file

    logger.info(f"Downloading Census Gazetteer from: {GAZETTEER_URL}")
    logger.info("This may take 1-2 minutes for a ~2MB file...")

    response = requests.get(GAZETTEER_URL, timeout=120)
    response.raise_for_status()

    logger.success(f"Downloaded {len(response.content):,} bytes")

    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
        txt_files = [f for f in zip_ref.namelist() if f.endswith('.txt')]
        if not txt_files:
            raise FileNotFoundError("No .txt file found in ZIP")

        txt_file = txt_files[0]
        logger.info(f"Extracting: {txt_file}")

        with zip_ref.open(txt_file) as f:
            content = f.read().decode('latin-1')

    lines = content.split('\n')
    csv_lines = [','.join(line.split('\t')) for line in lines if line.strip()]
    cache_file.write_text('\n'.join(csv_lines))

    logger.success(f"Saved to: {cache_file}")
    return cache_file


def main():
    parser = argparse.ArgumentParser(description="Download Census Gazetteer municipalities to cache")
    parser.add_argument("--force", action="store_true", help="Force re-download even if cached")
    args = parser.parse_args()

    csv_file = download_gazetteer_file(force=args.force)
    logger.success(f"Done: {csv_file}")


if __name__ == "__main__":
    main()
