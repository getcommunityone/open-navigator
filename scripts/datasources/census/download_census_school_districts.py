#!/usr/bin/env python3
"""
Download Census Bureau School District Shapefiles

Downloads cartographic boundary (cb_) shapefiles for all three school district types:
- Unified school districts (single K-12 authority)
- Elementary school districts
- Secondary school districts

CB files are available from 2023 onward under GENZ{year}/shp/.
They are simplified (1:500k scale) and suitable for mapping and spatial joins.

Source: https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html

Usage:
    python scripts/datasources/census/download_census_school_districts.py --year 2025
    python scripts/datasources/census/download_census_school_districts.py --year 2025 --types unified elementary
    python scripts/datasources/census/download_census_school_districts.py --year 2025 --extract
"""
import sys
from pathlib import Path
import argparse
import zipfile
import requests
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


# Cartographic boundary shapefiles — available from 2023 onward under GENZ{year}/shp/
SCHOOL_DISTRICT_URLS = {
    "unified": "https://www2.census.gov/geo/tiger/GENZ{year}/shp/cb_{year}_us_unsd_500k.zip",
    "elementary": "https://www2.census.gov/geo/tiger/GENZ{year}/shp/cb_{year}_us_elsd_500k.zip",
    "secondary": "https://www2.census.gov/geo/tiger/GENZ{year}/shp/cb_{year}_us_scsd_500k.zip",
}

SCHOOL_DISTRICT_DESCRIPTIONS = {
    "unified": "Unified school districts (K-12, single administrative authority)",
    "elementary": "Elementary school districts (grades K-8 or subset)",
    "secondary": "Secondary school districts (grades 9-12 or subset)",
}


def download_school_district_shapefile(district_type: str, year: int = 2025, extract: bool = False) -> Path:
    """
    Download a Census Bureau school district shapefile.

    Args:
        district_type: One of 'unified', 'elementary', 'secondary'
        year: Census vintage year (2019-2023 recommended)
        extract: Whether to extract the ZIP file after downloading

    Returns:
        Path to the downloaded ZIP file
    """
    if district_type not in SCHOOL_DISTRICT_URLS:
        raise ValueError(
            f"Invalid district type: {district_type}. Must be one of {list(SCHOOL_DISTRICT_URLS.keys())}"
        )

    cache_dir = Path("data/cache/census/school_districts") / str(year)
    cache_dir.mkdir(parents=True, exist_ok=True)

    url = SCHOOL_DISTRICT_URLS[district_type].format(year=year)
    filename = url.split("/")[-1]
    output_path = cache_dir / filename

    if output_path.exists():
        logger.info(f"Already downloaded: {output_path.name}")
        logger.info(f"   Size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")

        if extract:
            extract_dir = cache_dir / output_path.stem
            if extract_dir.exists():
                logger.info(f"Already extracted: {extract_dir}")
            else:
                _extract(output_path, extract_dir)

        return output_path

    logger.info(f"Downloading {district_type.upper()} school districts ({year})...")
    logger.info(f"   {SCHOOL_DISTRICT_DESCRIPTIONS[district_type]}")
    logger.info(f"   URL: {url}")
    logger.info(f"   Destination: {output_path}")

    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        logger.info(f"   File size: {total_size / 1024 / 1024:.2f} MB")

        downloaded = 0
        chunk_size = 1024 * 1024  # 1 MB chunks

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        logger.info(f"   Progress: {percent:.1f}% ({downloaded / 1024 / 1024:.2f} MB)")

        logger.success(f"Downloaded: {output_path.name}")

        if extract:
            extract_dir = cache_dir / output_path.stem
            _extract(output_path, extract_dir)

        return output_path

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download {district_type}: {e}")
        raise


def _extract(zip_path: Path, extract_dir: Path) -> None:
    logger.info(f"Extracting {zip_path.name} to {extract_dir}...")
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)
        files = list(extract_dir.iterdir())
        logger.success(f"Extracted {len(files)} files")
        for f in sorted(files):
            logger.info(f"   - {f.name}")


def download_all(year: int = 2025, types: list = None, extract: bool = False) -> dict:
    """
    Download all (or specified) school district shapefiles.

    Args:
        year: Census vintage year
        types: List of district types to download (default: all)
        extract: Whether to extract ZIP files after downloading

    Returns:
        Dictionary mapping district type to downloaded file path
    """
    if types is None:
        types = list(SCHOOL_DISTRICT_URLS.keys())

    logger.info("=" * 80)
    logger.info("CENSUS SCHOOL DISTRICT SHAPEFILE DOWNLOADER")
    logger.info("=" * 80)
    logger.info(f"Year:    {year}")
    logger.info(f"Types:   {', '.join(types)}")
    logger.info(f"Extract: {extract}")
    logger.info(
        "Using cartographic boundary (cb_) files — 1:500k scale, available from 2023 onward"
    )
    logger.info("")

    results = {}

    for district_type in types:
        logger.info("-" * 80)
        try:
            output_path = download_school_district_shapefile(district_type, year=year, extract=extract)
            results[district_type] = output_path
            logger.info("")
        except Exception as e:
            logger.error(f"Failed to download {district_type}: {e}")
            logger.info("")

    logger.info("=" * 80)
    logger.success(f"Downloaded {len(results)}/{len(types)} shapefiles")
    logger.info("=" * 80)
    for district_type, path in results.items():
        logger.info(f"  {district_type}: {path}")
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Load into GeoPandas: geopandas.read_file(path)")
    logger.info("  2. Key fields: GEOID (7-digit), NAME, STATEFP, LOGRADE, HIGRADE, ALAND, AWATER")
    logger.info("  3. LOGRADE/HIGRADE indicate the grade range served by the district")
    logger.info("")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Download Census Bureau school district shapefiles (TIGER/Line)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Download all school district types for 2023:
    python scripts/datasources/census/download_census_school_districts.py --year 2023

  Download unified districts only:
    python scripts/datasources/census/download_census_school_districts.py --year 2023 --types unified

  Download and extract:
    python scripts/datasources/census/download_census_school_districts.py --year 2023 --extract

Available types:
  unified    - Unified school districts (K-12 under one authority)
  elementary - Elementary school districts
  secondary  - Secondary / high school districts
        """,
    )

    parser.add_argument(
        "--year",
        type=int,
        default=2023,
        help="Census vintage year (2023+ for CB files, default: 2025)",
    )

    parser.add_argument(
        "--types",
        nargs="+",
        choices=list(SCHOOL_DISTRICT_URLS.keys()),
        help="District types to download (default: all)",
    )

    parser.add_argument(
        "--extract",
        action="store_true",
        help="Extract ZIP files after downloading",
    )

    args = parser.parse_args()

    download_all(year=args.year, types=args.types, extract=args.extract)


if __name__ == "__main__":
    main()
