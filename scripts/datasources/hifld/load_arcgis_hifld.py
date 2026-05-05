#!/usr/bin/env python3
"""
Download HIFLD Dataset from ArcGIS

This script downloads datasets from the Homeland Infrastructure Foundation-Level Data (HIFLD)
program using the official ArcGIS Python API.

Data Source: https://hifld-geoplatform.opendata.arcgis.com/
Example Dataset: Law Enforcement Locations (Item ID: 333a74c8e9c64cb6870689d31e8836af)

The script:
1. Connects to HIFLD portal (anonymous/public access)
2. Downloads data in CSV, GeoJSON, Shapefile, or KML format
3. Converts to Parquet for efficient processing
4. Caches locally to avoid repeated downloads

Dependencies:
    pip install arcgis pandas geopandas loguru

Usage:
    # Download Law Enforcement dataset (verified Item ID)
    python download_arcgis_dataset.py --item-id 333a74c8e9c64cb6870689d31e8836af
    
    # Download as GeoJSON (includes geometry)
    python download_arcgis_dataset.py --item-id 333a74c8e9c64cb6870689d31e8836af --format GeoJSON
    
    # Download and convert to Parquet
    python download_arcgis_dataset.py --item-id 333a74c8e9c64cb6870689d31e8836af --to-parquet
    
    # Just get metadata
    python download_arcgis_dataset.py --item-id 333a74c8e9c64cb6870689d31e8836af --metadata-only
"""
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import geopandas as gpd
from arcgis.gis import GIS
from loguru import logger


# Cache directory
CACHE_DIR = Path("data/cache/hifld")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ArcGIS Online portal (HIFLD items are accessible through ArcGIS Online)
ARCGIS_ONLINE = "https://www.arcgis.com"


class ArcGISDownloader:
    """Download datasets from ArcGIS using official Python API."""
    
    def __init__(self, item_id: str, portal_url: str = ARCGIS_ONLINE):
        """
        Initialize downloader.
        
        Args:
            item_id: ArcGIS item ID (e.g., "333a74c8e9c64cb6870689d31e8836af")
            portal_url: ArcGIS portal URL (default: ArcGIS Online)
        """
        self.item_id = item_id
        self.portal_url = portal_url
        self.gis = None
        self.item = None
    
    def connect(self):
        """Connect to ArcGIS portal (anonymous access for open data)."""
        if not self.gis:
            logger.info(f"Connecting to {self.portal_url}...")
            self.gis = GIS(self.portal_url)
            logger.success(f"✅ Connected to portal")
    
    def get_item(self):
        """Get ArcGIS item by ID."""
        if not self.gis:
            self.connect()
        
        if not self.item:
            logger.info(f"Fetching item {self.item_id}...")
            self.item = self.gis.content.get(self.item_id)
            
            if not self.item:
                raise ValueError(f"Item {self.item_id} not found. Check the ID is correct.")
            
            logger.info(f"Dataset: {self.item.title}")
            logger.info(f"Type: {self.item.type}")
            logger.info(f"Owner: {self.item.owner}")
            if self.item.snippet:
                logger.info(f"Description: {self.item.snippet[:100]}...")
        
        return self.item
    
    def get_metadata(self) -> dict:
        """
        Get item metadata.
        
        Returns:
            Dictionary with item metadata
        """
        item = self.get_item()
        
        return {
            "id": item.id,
            "title": item.title,
            "type": item.type,
            "description": item.description,
            "snippet": item.snippet,
            "owner": item.owner,
            "created": item.created,
            "modified": item.modified,
            "url": item.url,
            "tags": item.tags
        }
    
    def download(
        self, 
        output_file: Optional[Path] = None,
        file_format: str = "CSV"
    ) -> Path:
        """
        Download dataset using ArcGIS Python API.
        
        Args:
            output_file: Path to save file (defaults to cache directory)
            file_format: Format to download ('CSV', 'Shapefile', 'GeoJSON', 'KML')
        
        Returns:
            Path to downloaded file
        """
        item = self.get_item()
        
        # Generate output filename if not provided
        if not output_file:
            safe_title = "".join(c for c in item.title if c.isalnum() or c in (' ', '-', '_')).replace(' ', '_')
            
            # Determine file extension
            ext_map = {
                'CSV': '.csv',
                'Shapefile': '.zip',
                'GeoJSON': '.geojson',
                'KML': '.kml',
            }
            ext = ext_map.get(file_format, '.zip')
            
            output_file = CACHE_DIR / f"{safe_title}_{self.item_id}{ext}"
        else:
            output_file = Path(output_file)
        
        # Check cache
        if output_file.exists():
            age_days = (datetime.now() - datetime.fromtimestamp(output_file.stat().st_mtime)).days
            if age_days < 7:
                logger.info(f"✅ Using cached file (age: {age_days} days)")
                return output_file
        
        logger.info(f"Downloading dataset as {file_format}...")
        
        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # For feature layers, query and export
            if item.layers:
                logger.info(f"Querying feature layer...")
                layer = item.layers[0]
                
                # Query all features
                feature_set = layer.query(where="1=1", out_fields="*", return_all_records=True)
                
                logger.info(f"Retrieved {len(feature_set.features):,} features")
                
                # Save based on format
                if file_format == "CSV":
                    # Convert to DataFrame (drops geometry)
                    df = feature_set.sdf
                    if 'SHAPE' in df.columns:
                        df = df.drop(columns=['SHAPE'])
                    df.to_csv(output_file, index=False)
                    
                elif file_format == "GeoJSON":
                    # Write GeoJSON
                    geojson_str = feature_set.to_geojson
                    with open(output_file, 'w') as f:
                        f.write(geojson_str)
                
                else:
                    # For other formats, try direct download
                    logger.info(f"Attempting direct download...")
                    item.download(
                        save_path=str(output_file.parent),
                        file_name=output_file.name
                    )
                
                logger.success(f"✅ Downloaded to {output_file}")
                return output_file
            else:
                raise ValueError("Item does not have feature layers to query")
                
        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise
    
    def to_parquet(
        self,
        output_file: Optional[Path] = None,
        include_geometry: bool = True
    ) -> Path:
        """
        Convert dataset to Parquet format.
        
        Args:
            output_file: Path to save Parquet file
            include_geometry: Whether to include geometry column
        
        Returns:
            Path to Parquet file
        """
        item = self.get_item()
        
        if not output_file:
            safe_title = "".join(c for c in item.title if c.isalnum() or c in (' ', '-', '_')).replace(' ', '_')
            output_file = CACHE_DIR / f"{safe_title}_{self.item_id}.parquet"
        
        # Check cache
        if output_file.exists():
            age_days = (datetime.now() - datetime.fromtimestamp(output_file.stat().st_mtime)).days
            if age_days < 7:
                logger.info(f"✅ Using cached Parquet (age: {age_days} days)")
                return output_file
        
        logger.info("Converting to Parquet...")
        
        # Download as GeoJSON first
        geojson_file = self.download(file_format="GeoJSON")
        
        # Load as GeoDataFrame
        gdf = gpd.read_file(geojson_file)
        
        if not include_geometry and 'geometry' in gdf.columns:
            gdf = gdf.drop(columns='geometry')
        
        # Save as Parquet
        gdf.to_parquet(output_file)
        
        logger.success(f"✅ Saved {len(gdf):,} records to {output_file}")
        return output_file


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download HIFLD datasets from ArcGIS using official Python API"
    )
    parser.add_argument(
        '--item-id',
        type=str,
        default='333a74c8e9c64cb6870689d31e8836af',
        help='ArcGIS item ID (default: Law Enforcement Locations)'
    )
    parser.add_argument(
        '--format',
        type=str,
        choices=['CSV', 'GeoJSON', 'Shapefile', 'KML'],
        default='CSV',
        help='Output format (default: CSV)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output file path (optional, defaults to cache directory)'
    )
    parser.add_argument(
        '--to-parquet',
        action='store_true',
        help='Convert to Parquet format after download'
    )
    parser.add_argument(
        '--portal',
        type=str,
        default=ARCGIS_ONLINE,
        help=f'ArcGIS portal URL (default: {ARCGIS_ONLINE})'
    )
    parser.add_argument(
        '--metadata-only',
        action='store_true',
        help='Only fetch and display metadata, do not download'
    )
    
    args = parser.parse_args()
    
    # Initialize downloader
    downloader = ArcGISDownloader(args.item_id, portal_url=args.portal)
    
    # Get metadata
    metadata = downloader.get_metadata()
    
    logger.info("\n" + "=" * 80)
    logger.info("DATASET METADATA")
    logger.info("=" * 80)
    logger.info(f"Title: {metadata['title']}")
    logger.info(f"Type: {metadata['type']}")
    logger.info(f"Owner: {metadata['owner']}")
    logger.info(f"Created: {metadata['created']}")
    logger.info(f"Modified: {metadata['modified']}")
    if metadata['snippet']:
        logger.info(f"Description: {metadata['snippet']}")
    logger.info(f"URL: https://www.arcgis.com/home/item.html?id={args.item_id}")
    
    if args.metadata_only:
        logger.info("\n✅ Metadata fetch complete (use without --metadata-only to download)")
        return
    
    # Download in requested format
    output_path = Path(args.output) if args.output else None
    
    if args.to_parquet:
        result = downloader.to_parquet(output_path)
    else:
        result = downloader.download(output_path, file_format=args.format)
    
    logger.info("\n" + "=" * 80)
    logger.info("DOWNLOAD COMPLETE")
    logger.info("=" * 80)
    logger.info(f"File: {result}")
    logger.info(f"Dataset: {metadata['title']}")
    logger.info(f"Source: https://www.arcgis.com/home/item.html?id={args.item_id}")


if __name__ == "__main__":
    main()
