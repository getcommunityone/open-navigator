#!/usr/bin/env python3
"""
Download Census Bureau Geographic Relationship Files

Downloads relationship files that map between different geographic levels:
1. ZCTA (ZIP Code) to County - for ZIP to county lookups
2. ZCTA (ZIP Code) to Place (City/Town) - for ZIP to city lookups

Data Source: Census Bureau 2020 Geographic Relationship Files
https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.html

Usage:
    python packages/scrapers/src/scrapers/census/download_census_relationships.py
    python packages/scrapers/src/scrapers/census/download_census_relationships.py --types zcta_county zcta_place
"""
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
import httpx
from loguru import logger
import argparse


# Census 2020 Geographic Relationship Files
# These show how geographic areas overlap (e.g., which counties a ZIP code spans)
CENSUS_RELATIONSHIP_URLS = {
    # ZCTA (ZIP Code Tabulation Area) to County
    # Shows which counties each ZIP code overlaps, with area measurements
    "zcta_county": "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt",
    
    # ZCTA (ZIP Code Tabulation Area) to Place (City/Town)
    # Shows which cities/towns each ZIP code overlaps, with area measurements
    "zcta_place": "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_place20_natl.txt",
    
    # Optional: County Subdivision (Township) relationships
    # "zcta_cousub": "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_cousub20_natl.txt",
}


async def download_relationship_file(
    name: str, 
    url: str, 
    cache_dir: Path,
    force: bool = False
) -> Optional[Path]:
    """
    Download a Census relationship file.
    
    Args:
        name: Name identifier for the file (e.g., 'zcta_county')
        url: URL to download from
        cache_dir: Directory to save the file
        force: Force re-download even if file exists
        
    Returns:
        Path to downloaded file, or None if download failed
    """
    output_file = cache_dir / f"{name}.txt"
    
    # Check if already downloaded
    if output_file.exists() and not force:
        file_size_mb = output_file.stat().st_size / 1024 / 1024
        logger.info(f"✅ {name} already downloaded ({file_size_mb:.1f} MB)")
        return output_file
    
    logger.info(f"📥 Downloading {name}...")
    logger.info(f"   URL: {url}")
    
    try:
        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # Save file
            output_file.write_bytes(response.content)
            
            file_size_mb = len(response.content) / 1024 / 1024
            logger.success(f"✅ Downloaded {name} ({file_size_mb:.1f} MB)")
            
            # Show file info
            lines = response.content.decode('latin-1').count('\n')
            logger.info(f"   Rows: ~{lines:,}")
            
            return output_file
            
    except httpx.TimeoutError:
        logger.error(f"❌ Timeout downloading {name} after 5 minutes")
        logger.error(f"   Census server may be slow. Try again later.")
        return None
    except httpx.HTTPError as e:
        logger.error(f"❌ HTTP error downloading {name}: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to download {name}: {e}")
        return None


async def download_all_relationships(
    types: Optional[List[str]] = None,
    force: bool = False
) -> Dict[str, Path]:
    """
    Download all (or specified) Census relationship files.
    
    Args:
        types: List of relationship types to download (default: all)
        force: Force re-download even if files exist
        
    Returns:
        Dictionary mapping relationship type to file path
    """
    # Create cache directory
    cache_dir = Path("data/cache/census_relationships")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 80)
    logger.info("📥 CENSUS GEOGRAPHIC RELATIONSHIP FILES DOWNLOAD")
    logger.info("=" * 80)
    logger.info(f"Cache directory: {cache_dir}")
    logger.info("")
    
    # Determine which files to download
    if types is None:
        types_to_download = list(CENSUS_RELATIONSHIP_URLS.keys())
    else:
        types_to_download = types
        
        # Validate types
        invalid = [t for t in types_to_download if t not in CENSUS_RELATIONSHIP_URLS]
        if invalid:
            logger.error(f"❌ Invalid relationship types: {invalid}")
            logger.info(f"   Valid types: {list(CENSUS_RELATIONSHIP_URLS.keys())}")
            return {}
    
    logger.info(f"Files to download: {', '.join(types_to_download)}")
    logger.info("")
    
    # Download files
    results = {}
    
    for rel_type in types_to_download:
        url = CENSUS_RELATIONSHIP_URLS[rel_type]
        logger.info("-" * 80)
        
        output_path = await download_relationship_file(
            name=rel_type,
            url=url,
            cache_dir=cache_dir,
            force=force
        )
        
        if output_path:
            results[rel_type] = output_path
        
        logger.info("")
    
    # Summary
    logger.info("=" * 80)
    logger.info("📊 DOWNLOAD SUMMARY")
    logger.info("=" * 80)
    
    if results:
        logger.success(f"✅ Downloaded {len(results)} relationship files:")
        for rel_type, path in results.items():
            file_size_mb = path.stat().st_size / 1024 / 1024
            logger.info(f"  • {rel_type}: {path.name} ({file_size_mb:.1f} MB)")
    else:
        logger.warning("⚠️  No files were downloaded")
    
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Run: python packages/scrapers/src/scrapers/census/load_census_relationships.py")
    logger.info("  2. This will load the data into bronze database tables")
    logger.info("")
    
    return results


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download Census Bureau Geographic Relationship Files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available relationship types:
  zcta_county  - ZIP Code to County mappings (6.5 MB, ~60K relationships)
  zcta_place   - ZIP Code to City/Place mappings (13 MB, ~270K relationships)

Examples:
  Download all relationship files:
    python packages/scrapers/src/scrapers/census/download_census_relationships.py
  
  Download only ZCTA to county:
    python packages/scrapers/src/scrapers/census/download_census_relationships.py --types zcta_county
  
  Force re-download all files:
    python packages/scrapers/src/scrapers/census/download_census_relationships.py --force

Notes:
  - Files are cached in data/cache/census_relationships/
  - ZIP codes are approximate (Census uses ZCTAs - ZIP Code Tabulation Areas)
  - Relationship files show area overlap, not exact boundaries
  - One ZIP code can span multiple counties or cities
        """
    )
    
    parser.add_argument(
        '--types',
        nargs='+',
        choices=list(CENSUS_RELATIONSHIP_URLS.keys()),
        help='Relationship types to download (default: all)'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-download even if files exist'
    )
    
    args = parser.parse_args()
    
    await download_all_relationships(
        types=args.types,
        force=args.force
    )


if __name__ == "__main__":
    asyncio.run(main())
