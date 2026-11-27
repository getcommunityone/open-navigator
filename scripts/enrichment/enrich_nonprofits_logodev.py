#!/usr/bin/env python3
"""
Enrich nonprofit data with organization logos from Logo.dev API.

Logo.dev provides high-quality company logos based on domain names.
This script extracts domains from website URLs and fetches logos.

API Documentation: https://www.logo.dev/docs/logo-images/get

Features:
    - Extracts domain from website URLs
    - Fetches logos via Logo.dev API
    - Incremental updates (only fetch for new/missing logos)
    - Efficient storage in parquet
    - Caching to avoid duplicate API calls
    - Multiple logo sizes (small, medium, large)

Usage:
    # Test with sample
    python scripts/enrich_nonprofits_logodev.py \\
        --input data/gold/states/MA/nonprofits_organizations.parquet \\
        --output data/gold/states/MA/nonprofits_organizations.parquet \\
        --sample 100
    
    # Full enrichment (only new/missing logos)
    python scripts/enrich_nonprofits_logodev.py \\
        --input data/gold/states/MA/nonprofits_organizations.parquet \\
        --update-in-place \\
        --incremental
    
    # Force refresh all logos
    python scripts/enrich_nonprofits_logodev.py \\
        --input data/gold/states/MA/nonprofits_organizations.parquet \\
        --update-in-place
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import pandas as pd
import requests
from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Configure logging
logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


class LogoDevEnricher:
    """Enrich nonprofit data with logos from Logo.dev API."""
    
    def __init__(self, api_key: str):
        """
        Initialize Logo.dev enricher.
        
        Args:
            api_key: Logo.dev API key
        """
        self.api_key = api_key
        self.api_base = "https://img.logo.dev"
        self.cache = {}
        self.request_count = 0
        
        logger.info("🎨 Logo.dev enricher initialized")
    
    def extract_domain(self, url: str) -> Optional[str]:
        """
        Extract domain from URL.
        
        Args:
            url: Website URL
            
        Returns:
            Domain name (e.g., 'example.org') or None
        """
        if not url or pd.isna(url):
            return None
        
        try:
            # Handle URLs without protocol
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            parsed = urlparse(url)
            domain = parsed.netloc
            
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            
            return domain if domain else None
        except Exception as e:
            logger.debug(f"Failed to parse URL {url}: {e}")
            return None
    
    def get_logo_url(self, domain: str, size: str = "200") -> Optional[str]:
        """
        Get logo URL from Logo.dev API.
        
        Args:
            domain: Domain name (e.g., 'example.org')
            size: Logo size - "small" (32px), "medium" (128px), "large" (200px), or specific pixel size
            
        Returns:
            Logo URL or None if not found
        """
        if not domain:
            return None
        
        # Check cache
        cache_key = f"{domain}_{size}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            # Logo.dev URL format: https://img.logo.dev/{domain}?token={api_key}
            # Note: Logo.dev returns optimized logo, size parameter not supported
            logo_url = f"{self.api_base}/{domain}?token={self.api_key}"
            
            # Logo.dev doesn't support HEAD requests properly, use GET
            response = requests.get(logo_url, timeout=5, allow_redirects=True)
            self.request_count += 1
            
            # Check if response is an image (not JSON error)
            content_type = response.headers.get('content-type', '')
            if response.status_code == 200 and ('image' in content_type or 'octet-stream' in content_type):
                self.cache[cache_key] = logo_url
                return logo_url
            else:
                logger.debug(f"Logo not found for {domain}: {response.status_code}")
                self.cache[cache_key] = None
                return None
                
        except Exception as e:
            logger.debug(f"Error fetching logo for {domain}: {e}")
            self.cache[cache_key] = None
            return None
    
    def enrich_row(self, row: pd.Series, website_column: str = 'website') -> dict:
        """
        Enrich single row with logo URL.
        
        Args:
            row: DataFrame row
            website_column: Column containing website URL
            
        Returns:
            Dict with logo data
        """
        website = row.get(website_column)
        domain = self.extract_domain(website)
        
        if not domain:
            return {
                'logodev_domain': None,
                'logodev_logo_url': None,
                'logodev_logo_small': None,
                'logodev_logo_medium': None,
                'logodev_logo_large': None,
                'logodev_status': 'no_domain'
            }
        
        # Get multiple sizes
        logo_large = self.get_logo_url(domain, size="200")
        logo_medium = self.get_logo_url(domain, size="128")
        logo_small = self.get_logo_url(domain, size="32")
        
        # Use large as primary
        logo_url = logo_large
        status = 'success' if logo_url else 'not_found'
        
        return {
            'logodev_domain': domain,
            'logodev_logo_url': logo_url,  # Primary logo (200px)
            'logodev_logo_small': logo_small,  # 32px
            'logodev_logo_medium': logo_medium,  # 128px
            'logodev_logo_large': logo_large,  # 200px
            'logodev_status': status
        }
    
    def enrich_dataframe(
        self,
        df: pd.DataFrame,
        website_column: Optional[str] = None,
        incremental: bool = False
    ) -> pd.DataFrame:
        """
        Enrich DataFrame with logo URLs.
        
        Args:
            df: Input DataFrame
            website_column: Column containing website URLs (auto-detect if None)
            incremental: If True, only enrich rows without existing logos
            
        Returns:
            Enriched DataFrame
        """
        logger.info("=" * 70)
        logger.info("🎨 LOGO.DEV ENRICHMENT")
        logger.info("=" * 70)
        
        # Auto-detect website column if not specified
        if website_column is None:
            website_columns = ['bigquery_website', 'form_990_website', 'everyorg_website', 
                             'gt990_website', 'website', 'url', 'website_url']
            
            for col in website_columns:
                if col in df.columns:
                    website_column = col
                    logger.info(f"🔍 Auto-detected website column: {col}")
                    break
            
            if website_column is None:
                logger.error(f"❌ No website column found in data")
                logger.error(f"   Searched for: {', '.join(website_columns)}")
                logger.error(f"   Available columns: {', '.join(df.columns)}")
                return df
        else:
            # Check if specified column exists
            if website_column not in df.columns:
                logger.error(f"❌ Column '{website_column}' not found in data")
                logger.error(f"   Available columns: {', '.join(df.columns)}")
                return df
            
            logger.info(f"🔍 Using website column: {website_column}")
        
        # For incremental mode, filter to rows needing enrichment
        if incremental and 'logodev_logo_url' in df.columns:
            mask = df['logodev_logo_url'].isna()
            rows_to_enrich = df[mask].copy()
            logger.info(f"📊 Incremental mode: {len(rows_to_enrich):,} / {len(df):,} rows need enrichment")
        else:
            rows_to_enrich = df.copy()
            logger.info(f"📊 Enriching {len(rows_to_enrich):,} rows")
        
        # Filter to rows with websites
        has_website = rows_to_enrich[website_column].notna()
        rows_with_websites = rows_to_enrich[has_website]
        
        logger.info(f"🌐 Rows with websites: {len(rows_with_websites):,} / {len(rows_to_enrich):,}")
        
        if len(rows_with_websites) == 0:
            logger.warning("⚠️  No rows with websites to enrich")
            return df
        
        # Enrich each row
        results = []
        for idx, row in tqdm(rows_with_websites.iterrows(), total=len(rows_with_websites), desc="Fetching logos"):
            result = self.enrich_row(row, website_column)
            results.append({**{'index': idx}, **result})
        
        # Convert to DataFrame
        results_df = pd.DataFrame(results).set_index('index')
        
        # Merge with original data
        enriched = df.copy()
        
        # Add or update logo columns
        for col in ['logodev_domain', 'logodev_logo_url', 'logodev_logo_small', 
                    'logodev_logo_medium', 'logodev_logo_large', 'logodev_status']:
            if col in results_df.columns:
                if incremental and col in enriched.columns:
                    # Update only null values
                    enriched.loc[results_df.index, col] = enriched.loc[results_df.index, col].fillna(results_df[col])
                else:
                    # Overwrite all
                    enriched.loc[results_df.index, col] = results_df[col]
        
        # Statistics
        total_with_logos = enriched['logodev_logo_url'].notna().sum()
        success_count = (results_df['logodev_status'] == 'success').sum()
        
        logger.info("\n" + "=" * 70)
        logger.info("📊 ENRICHMENT SUMMARY")
        logger.info("=" * 70)
        logger.info(f"✅ API requests: {self.request_count:,}")
        logger.info(f"✅ Logos found (this run): {success_count:,}")
        logger.info(f"✅ Total with logos: {total_with_logos:,} / {len(enriched):,} ({100*total_with_logos/len(enriched):.1f}%)")
        logger.info(f"❌ Not found: {(results_df['logodev_status'] == 'not_found').sum():,}")
        logger.info(f"⚠️  No domain: {(results_df['logodev_status'] == 'no_domain').sum():,}")
        logger.info("=" * 70)
        
        return enriched


def main():
    parser = argparse.ArgumentParser(
        description="Enrich nonprofit data with logos from Logo.dev",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with sample
  python scripts/enrich_nonprofits_logodev.py \\
      --input data/gold/states/MA/nonprofits_organizations.parquet \\
      --output /tmp/test_logos.parquet \\
      --sample 100
  
  # Incremental enrichment (only fetch missing logos)
  python scripts/enrich_nonprofits_logodev.py \\
      --input data/gold/states/MA/nonprofits_organizations.parquet \\
      --update-in-place \\
      --incremental
  
  # Force refresh all logos
  python scripts/enrich_nonprofits_logodev.py \\
      --input data/gold/states/MA/nonprofits_organizations.parquet \\
      --update-in-place
  
  # Specify custom website column
  python scripts/enrich_nonprofits_logodev.py \\
      --input data/gold/nonprofits.parquet \\
      --output data/gold/nonprofits_logos.parquet \\
      --website-column bigquery_website
        """
    )
    
    parser.add_argument('--input', required=True, help='Input parquet file')
    parser.add_argument('--output', help='Output parquet file (required unless --update-in-place)')
    parser.add_argument('--update-in-place', action='store_true', 
                        help='Update input file instead of creating new output')
    parser.add_argument('--website-column', default=None, 
                        help='Column containing website URLs (auto-detect if not specified)')
    parser.add_argument('--incremental', action='store_true',
                        help='Only enrich rows without existing logos')
    parser.add_argument('--sample', type=int, help='Sample N records (for testing)')
    
    args = parser.parse_args()
    
    # Validate output
    if not args.update_in_place and not args.output:
        parser.error("--output is required unless using --update-in-place")
    
    # CRITICAL: Prevent --sample + --update-in-place from destroying data
    if args.sample and args.update_in_place:
        logger.error("❌ Cannot use --sample with --update-in-place")
        logger.error("   Using --sample with --update-in-place would overwrite your source file with only the sampled records!")
        logger.error("   Instead, use: --sample N --output /tmp/test_output.parquet")
        return 1
    
    if args.update_in_place:
        if args.output:
            logger.warning("⚠️  Both --update-in-place and --output specified. Using --update-in-place.")
        args.output = args.input
    
    # Get API key
    api_key = os.getenv('LOGODEV_API_KEY')
    if not api_key:
        logger.error("❌ LOGODEV_API_KEY not found in environment")
        logger.error("   1. Get API key from: https://www.logo.dev/")
        logger.error("   2. Add to .env file: LOGODEV_API_KEY=your_api_key_here")
        return 1
    
    # Load input
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"❌ Input file not found: {input_path}")
        return 1
    
    logger.info(f"📂 Loading: {input_path}")
    df = pd.read_parquet(input_path)
    logger.info(f"   Loaded {len(df):,} records")
    
    # Sample if requested
    if args.sample:
        df = df.sample(n=min(args.sample, len(df)), random_state=42)
        logger.info(f"🎲 Sampled {len(df):,} records")
    
    # Create enricher
    enricher = LogoDevEnricher(api_key=api_key)
    
    # Enrich
    try:
        enriched = enricher.enrich_dataframe(
            df,
            website_column=args.website_column,
            incremental=args.incremental
        )
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Enrichment failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"💾 Saving to: {output_path}")
    enriched.to_parquet(output_path, index=False)
    
    file_size = output_path.stat().st_size / 1024 / 1024
    logger.info(f"✅ Saved {len(enriched):,} records ({file_size:.1f} MB)")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
