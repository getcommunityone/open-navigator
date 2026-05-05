#!/usr/bin/env python3
"""
Download Census Bureau TIGER/Line Shapefiles

This script downloads U.S. Census Bureau TIGER/Line shapefiles for:
- States (cb_<year>_us_state_500k.zip)
- Counties (cb_<year>_us_county_500k.zip)  
- ZIP Code Tabulation Areas / ZCTAs (cb_<year>_us_zcta520_500k.zip)

Source: https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html

Cartographic Boundary Files (cb_) are simplified versions optimized for mapping.
Use these for visualization - they're smaller and faster to render than the full TIGER files.

Usage:
    python scripts/datasources/census/download_shapefiles.py --year 2023
    python scripts/datasources/census/download_shapefiles.py --year 2023 --types states counties
    python scripts/datasources/census/download_shapefiles.py --year 2023 --extract
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

from config import settings


# Census Bureau Cartographic Boundary Shapefile URLs
# Using 1:500k scale (simplified for mapping performance)
SHAPEFILE_URLS = {
    "states": "https://www2.census.gov/geo/tiger/GENZ{year}/shp/cb_{year}_us_state_500k.zip",
    "counties": "https://www2.census.gov/geo/tiger/GENZ{year}/shp/cb_{year}_us_county_500k.zip",
    "zcta": "https://www2.census.gov/geo/tiger/GENZ{year}/shp/cb_{year}_us_zcta520_500k.zip",  # ZIP Code Tabulation Areas
}

# Alternative: Full TIGER/Line files (higher detail, larger files)
# TIGER_URLS = {
#     "states": "https://www2.census.gov/geo/tiger/TIGER{year}/STATE/tl_{year}_us_state.zip",
#     "counties": "https://www2.census.gov/geo/tiger/TIGER{year}/COUNTY/tl_{year}_us_county.zip",
#     "zcta": "https://www2.census.gov/geo/tiger/TIGER{year}/ZCTA520/tl_{year}_us_zcta520.zip",
# }


def download_shapefile(shapefile_type: str, year: int = 2023, extract: bool = False) -> Path:
    """
    Download a Census Bureau shapefile.
    
    Args:
        shapefile_type: One of 'states', 'counties', 'zcta'
        year: Census vintage year (2020-2023 recommended)
        extract: Whether to extract the ZIP file after downloading
        
    Returns:
        Path to the downloaded ZIP file
    """
    if shapefile_type not in SHAPEFILE_URLS:
        raise ValueError(f"Invalid shapefile type: {shapefile_type}. Must be one of {list(SHAPEFILE_URLS.keys())}")
    
    # Create cache directory
    cache_dir = Path("data/cache/census/shapefiles") / str(year)
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Get URL and output path
    url = SHAPEFILE_URLS[shapefile_type].format(year=year)
    filename = url.split("/")[-1]
    output_path = cache_dir / filename
    
    # Check if already downloaded
    if output_path.exists():
        logger.info(f"✅ Already downloaded: {output_path.name}")
        logger.info(f"   Size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
        
        if extract:
            extract_dir = cache_dir / output_path.stem
            if extract_dir.exists():
                logger.info(f"✅ Already extracted: {extract_dir}")
            else:
                extract_shapefile(output_path, extract_dir)
        
        return output_path
    
    # Download the file
    logger.info(f"📥 Downloading {shapefile_type.upper()} shapefile ({year})...")
    logger.info(f"   URL: {url}")
    logger.info(f"   Destination: {output_path}")
    
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Get file size for progress
        total_size = int(response.headers.get('content-length', 0))
        logger.info(f"   File size: {total_size / 1024 / 1024:.2f} MB")
        
        # Download with progress
        downloaded = 0
        chunk_size = 1024 * 1024  # 1 MB chunks
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        logger.info(f"   Progress: {percent:.1f}% ({downloaded / 1024 / 1024:.2f} MB)")
        
        logger.success(f"✅ Downloaded: {output_path.name}")
        
        # Extract if requested
        if extract:
            extract_dir = cache_dir / output_path.stem
            extract_shapefile(output_path, extract_dir)
        
        return output_path
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Failed to download {shapefile_type}: {e}")
        raise


def extract_shapefile(zip_path: Path, extract_dir: Path) -> None:
    """
    Extract a shapefile ZIP to a directory.
    
    Args:
        zip_path: Path to the ZIP file
        extract_dir: Directory to extract to
    """
    logger.info(f"📦 Extracting {zip_path.name}...")
    logger.info(f"   To: {extract_dir}")
    
    extract_dir.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
        
        # List extracted files
        files = list(extract_dir.iterdir())
        logger.success(f"✅ Extracted {len(files)} files:")
        for file in sorted(files):
            logger.info(f"   - {file.name}")


def download_all_shapefiles(year: int = 2023, types: list = None, extract: bool = False) -> dict:
    """
    Download all (or specified) Census shapefiles.
    
    Args:
        year: Census vintage year
        types: List of shapefile types to download (default: all)
        extract: Whether to extract ZIP files after downloading
        
    Returns:
        Dictionary mapping shapefile type to downloaded file path
    """
    if types is None:
        types = list(SHAPEFILE_URLS.keys())
    
    logger.info("=" * 80)
    logger.info("CENSUS BUREAU SHAPEFILE DOWNLOADER")
    logger.info("=" * 80)
    logger.info(f"Year: {year}")
    logger.info(f"Types: {', '.join(types)}")
    logger.info(f"Extract: {extract}")
    logger.info("")
    
    results = {}
    
    for shapefile_type in types:
        logger.info("-" * 80)
        try:
            output_path = download_shapefile(shapefile_type, year=year, extract=extract)
            results[shapefile_type] = output_path
            logger.info("")
        except Exception as e:
            logger.error(f"Failed to download {shapefile_type}: {e}")
            logger.info("")
    
    logger.info("=" * 80)
    logger.success("DOWNLOAD COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Downloaded {len(results)} shapefiles:")
    for shapefile_type, path in results.items():
        logger.info(f"  ✅ {shapefile_type}: {path}")
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Load shapefiles into GeoPandas: geopandas.read_file(path)")
    logger.info("  2. Convert to GeoJSON: gdf.to_file('output.geojson', driver='GeoJSON')")
    logger.info("  3. Convert to GeoParquet: gdf.to_parquet('output.parquet')")
    logger.info("")
    
    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download Census Bureau TIGER/Line Shapefiles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Download all shapefiles for 2023:
    python scripts/datasources/census/download_shapefiles.py --year 2023
  
  Download only states and counties:
    python scripts/datasources/census/download_shapefiles.py --year 2023 --types states counties
  
  Download and extract:
    python scripts/datasources/census/download_shapefiles.py --year 2023 --extract
  
  Download ZCTA (ZIP codes) only:
    python scripts/datasources/census/download_shapefiles.py --year 2023 --types zcta

Available types:
  states   - U.S. States and territories
  counties - U.S. Counties and county equivalents
  zcta     - ZIP Code Tabulation Areas (postal codes)
        """
    )
    
    parser.add_argument(
        "--year",
        type=int,
        default=2023,
        help="Census vintage year (2020-2023 recommended, default: 2023)"
    )
    
    parser.add_argument(
        "--types",
        nargs="+",
        choices=list(SHAPEFILE_URLS.keys()),
        help="Shapefile types to download (default: all)"
    )
    
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Extract ZIP files after downloading"
    )
    
    args = parser.parse_args()
    
    download_all_shapefiles(
        year=args.year,
        types=args.types,
        extract=args.extract
    )


if __name__ == "__main__":
    main()
