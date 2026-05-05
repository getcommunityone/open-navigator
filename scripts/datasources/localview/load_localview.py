#!/usr/bin/env python3
"""
Download LocalView Dataset from Harvard Dataverse

This script downloads the LocalView municipal meeting dataset from Harvard Dataverse
and saves the CSV files to data/cache/localview/ for ingestion.

Source: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM
"""
import sys
from pathlib import Path
import asyncio
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.datasources.localview.dataverse_client import DataverseClient
from config import settings


# LocalView dataset DOI
LOCALVIEW_DOI = "doi:10.7910/DVN/NJTBEM"


async def download_localview():
    """Download LocalView dataset from Harvard Dataverse."""
    
    logger.info("=" * 80)
    logger.info("LOCALVIEW DATASET DOWNLOADER")
    logger.info("=" * 80)
    logger.info(f"Dataset DOI: {LOCALVIEW_DOI}")
    logger.info(f"Source: Harvard Dataverse")
    logger.info("")
    
    # Initialize client
    client = DataverseClient()
    
    if not client.api_key:
        logger.error("❌ No Dataverse API key found")
        logger.error("Get your API key at: https://dataverse.harvard.edu/loginpage.xhtml")
        logger.error("Add to .env: DATAVERSE_API_KEY=your_key_here")
        return False
    
    logger.info("✅ Dataverse API key found")
    logger.info("")
    
    # Get dataset metadata
    logger.info("📡 Fetching dataset metadata...")
    try:
        metadata = await client.get_dataset_metadata(LOCALVIEW_DOI)
        logger.success(f"✅ Dataset found: {metadata.get('title', 'LocalView')}")
        logger.info(f"   Version: {metadata.get('version', 'unknown')}")
        logger.info(f"   Files: {len(metadata.get('files', []))}")
        logger.info("")
    except Exception as e:
        logger.error(f"❌ Failed to fetch metadata: {e}")
        logger.error("   The dataset may be private or the DOI may be incorrect")
        return False
    
    # Download dataset
    logger.info("📥 Downloading dataset files...")
    logger.info("   This may take a few minutes...")
    logger.info("")
    
    try:
        result = await client.download_dataset(
            persistent_id=LOCALVIEW_DOI,
            output_dir=Path("data/cache/localview")
        )
        
        logger.info("")
        logger.success("=" * 80)
        logger.success("✅ DOWNLOAD COMPLETE!")
        logger.success("=" * 80)
        logger.success(f"Files downloaded: {result['files_downloaded']}")
        logger.success(f"Location: {result['output_dir']}")
        logger.info("")
        
        # List downloaded files
        cache_dir = Path("data/cache/localview")
        csv_files = list(cache_dir.glob("*.csv")) + list(cache_dir.glob("*.tab"))
        
        if csv_files:
            logger.info("📁 Downloaded files:")
            for f in csv_files:
                size_mb = f.stat().st_size / (1024 * 1024)
                logger.info(f"   ✓ {f.name} ({size_mb:.1f} MB)")
        
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Run ingestion: python scripts/datasources/localview/localview_ingestion.py")
        logger.info("2. Check data: python scripts/localview/check_meeting_data.py --states AL,GA,IN,MA,WA,WI")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Download failed: {e}")
        logger.error("")
        logger.error("Troubleshooting:")
        logger.error("1. Check your internet connection")
        logger.error("2. Verify your API key is valid")
        logger.error("3. Try manual download from:")
        logger.error("   https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM")
        return False


if __name__ == "__main__":
    success = asyncio.run(download_localview())
    sys.exit(0 if success else 1)
