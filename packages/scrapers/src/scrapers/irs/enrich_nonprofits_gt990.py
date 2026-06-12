#!/usr/bin/env python3
"""
Enrich nonprofit data with IRS Form 990 XML from GivingTuesday Data Lake

This script uses the GivingTuesday 990 Data Infrastructure (https://990data.givingtuesday.org/)
to download and parse Form 990 XMLs for detailed financial data.

Data Lake:
- Bucket: gt990datalake-rawdata (AWS S3, us-east-1, public access)
- Index: Indices/990xmls/index_all_years_efiledata_xmls_created_on_2023-10-29.csv
- XMLs: EfileData/XmlFiles/[OBJECT_ID]_public.xml

Data enriched:
- Website URLs (WebsiteAddressTxt)
- Mission statements and program descriptions (ActivityOrMissionDesc)
- Total revenue, expenses, net income
- Assets, liabilities, net assets
- Program expenses, administrative, fundraising
- Contributions, grants, investment income
- Officer compensation and leadership (Part VII)

Usage:
    # Install dependencies first
    pip install boto3 xmltodict pandas pyarrow

    # Download index (one-time setup)
    python -m scrapers.irs.enrich_nonprofits_gt990 --download-index

    # Enrich all Tuscaloosa nonprofits
    python -m scrapers.irs.enrich_nonprofits_gt990 \\
        --input data/gold/nonprofits_tuscaloosa.parquet \\
        --output data/gold/nonprofits_tuscaloosa_form990.parquet \\
        --concurrent 20

    # Enrich specific states
    python -m scrapers.irs.enrich_nonprofits_gt990 \\
        --input data/gold/nonprofits_organizations.parquet \\
        --output data/gold/nonprofits_990_enriched.parquet \\
        --states AL MI \\
        --concurrent 50

Attribution:
- GivingTuesday 990 Data Infrastructure: https://990data.givingtuesday.org/
- Open Navigator: https://github.com/getcommunityone/open-navigator
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from loguru import logger

# Repo root: packages/scrapers/src/scrapers/irs/<this file> -> parents[5]
_REPO_ROOT = Path(__file__).resolve().parents[5]


def _configure_logging() -> None:
    """Configure loguru to cooperate with tqdm progress bars.

    Kept out of module import so importing this module as a library does not
    mutate global loguru handlers.
    """
    from tqdm import tqdm

    logger.remove()
    logger.add(
        lambda msg: tqdm.write(msg, end=""),
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )


class GivingTuesday990Enricher:
    """
    Enrich nonprofit data with Form 990 XMLs from GivingTuesday Data Lake
    
    This class handles:
    1. Downloading the index of all available 990s
    2. Looking up OBJECT_IDs for EINs
    3. Downloading and parsing XMLs
    4. Extracting financial data
    """
    
    def __init__(
        self,
        index_path: str = "data/cache/form990_gt_index.parquet",
        cache_dir: str = "data/cache/form_990_xml",
        max_concurrent: int = 20,
        use_local_xmls: bool = False,
        local_index_path: str = "data/cache/form990/local_index_dev_states.parquet"
    ):
        """Initialize the enricher
        
        Args:
            index_path: Path to GivingTuesday index
            cache_dir: Directory to cache downloaded XMLs
            max_concurrent: Max concurrent S3 requests
            use_local_xmls: If True, use locally extracted XMLs instead of downloading
            local_index_path: Path to local XML index (created by build_990_local_index.py)
        """
        import boto3
        import pandas as pd
        from botocore import UNSIGNED
        from botocore.config import Config

        self.index_path = Path(index_path)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.use_local_xmls = use_local_xmls
        self.local_index_path = Path(local_index_path)

        # S3 client for GivingTuesday Data Lake (no credentials needed)
        self.s3 = boto3.client(
            's3',
            region_name='us-east-1',
            config=Config(signature_version=UNSIGNED)
        )
        
        self.bucket = 'gt990datalake-rawdata'
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # Load appropriate index
        self.index_df = None
        if use_local_xmls:
            if self.local_index_path.exists():
                logger.info(f"📚 Loading local XML index from {self.local_index_path}")
                self.index_df = pd.read_parquet(self.local_index_path)
                logger.info(f"   Local index contains {len(self.index_df):,} Form 990 XMLs")
            else:
                logger.warning(f"⚠️  Local index not found: {self.local_index_path}")
                logger.warning(f"   Run: python scripts/build_990_local_index.py")
        else:
            if self.index_path.exists():
                logger.info(f"📚 Loading GivingTuesday index from {self.index_path}")
                self.index_df = pd.read_parquet(self.index_path)
                logger.info(f"   Index contains {len(self.index_df):,} Form 990 filings")
        
        logger.info(f"🚀 GivingTuesday 990 enricher initialized")
        if use_local_xmls:
            logger.info(f"   Mode: LOCAL XMLs")
            logger.info(f"   Local index: {self.local_index_path}")
        else:
            logger.info(f"   Mode: DOWNLOAD from S3")
            logger.info(f"   Data Lake: s3://{self.bucket}")
            logger.info(f"   Max concurrent requests: {max_concurrent}")
            logger.info(f"   Cache directory: {self.cache_dir}")
    
    def download_index(self, index_key: str = "Indices/990xmls/index_all_years_efiledata_xmls_created_on_2023-10-29.csv"):
        """
        Download the GivingTuesday Data Lake index
        
        The index is a CSV file listing all available Form 990s with columns:
        - EIN
        - OBJECT_ID (used to construct S3 key)
        - TAX_PERIOD
        - FILING_TYPE (990, 990EZ, 990PF)
        - and more...
        """
        import pandas as pd

        logger.info("=" * 60)
        logger.info("DOWNLOADING GIVINGTUESDAY DATA LAKE INDEX")
        logger.info("=" * 60)
        logger.info(f"Bucket: s3://{self.bucket}")
        logger.info(f"Key: {index_key}")

        try:
            # Download index
            response = self.s3.get_object(Bucket=self.bucket, Key=index_key)
            index_csv = response['Body'].read()
            
            # Parse CSV
            import io
            df = pd.read_csv(io.BytesIO(index_csv))
            
            logger.success(f"✅ Downloaded index with {len(df):,} records")
            logger.info(f"   Columns: {df.columns.tolist()}")
            
            # Convert EIN to string with leading zeros
            if 'EIN' in df.columns:
                df['EIN'] = df['EIN'].astype(str).str.zfill(9)
            
            # Save as parquet for faster loading
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(self.index_path, index=False)
            logger.success(f"💾 Saved index to {self.index_path}")
            
            self.index_df = df
            
            # Show stats
            logger.info("")
            logger.info("📊 Index Statistics:")
            if 'TaxPeriod' in df.columns:
                # TaxPeriod format is YYYYMM, extract year
                years = df['TaxPeriod'].astype(str).str[:4].value_counts().sort_index(ascending=False)
                for year, count in years.head(5).items():
                    logger.info(f"   {year}: {count:,} filings")
            
            if 'FormType' in df.columns:
                types = df['FormType'].value_counts()
                for ftype, count in types.items():
                    logger.info(f"   {ftype}: {count:,} filings")
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Failed to download index: {e}")
            raise
    
    def find_filing(self, ein: str, prefer_recent: bool = True) -> Optional[Dict]:
        """
        Find the most recent Form 990 filing for an EIN
        
        Returns dict with OBJECT_ID/file_path and other metadata, or None if not found
        """
        if self.index_df is None:
            logger.warning("⚠️  Index not loaded.")
            return None
        
        # Ensure EIN is 9 digits with leading zeros
        ein = str(ein).zfill(9)
        
        # For local XMLs, use 'ein' column; for GT index, use 'EIN'
        ein_col = 'ein' if self.use_local_xmls else 'EIN'
        
        # Find all filings for this EIN
        filings = self.index_df[self.index_df[ein_col] == ein]
        
        if len(filings) == 0:
            return None
        
        # Prefer most recent if multiple filings
        if prefer_recent:
            if self.use_local_xmls and 'tax_year' in filings.columns:
                filings = filings.sort_values('tax_year', ascending=False)
            elif 'TaxPeriod' in filings.columns:
                filings = filings.sort_values('TaxPeriod', ascending=False)
        
        # Return first (most recent) filing as dict
        return filings.iloc[0].to_dict()
    
    async def fetch_and_parse_990(self, ein: str, filing_info: Optional[Dict] = None) -> Dict:
        """
        Fetch and parse a Form 990 XML (from S3 or local file)
        
        Args:
            ein: 9-digit EIN
            filing_info: Optional dict from find_filing() with OBJECT_ID or file_path
        
        Returns:
            Dict with extracted fields or {'form_990_status': 'not_found'}
        """
        async with self.semaphore:
            ein = str(ein).zfill(9)
            
            # Check cache first
            cache_file = self.cache_dir / f"{ein}.json"
            if cache_file.exists():
                try:
                    with open(cache_file) as f:
                        return json.load(f)
                except:
                    pass
            
            # Find filing if not provided
            if filing_info is None:
                filing_info = self.find_filing(ein)
            
            if filing_info is None:
                result = {
                    'form_990_status': 'not_found',
                    'form_990_last_updated': datetime.now().isoformat(),
                }
                # Cache negative result
                with open(cache_file, 'w') as f:
                    json.dump(result, f)
                return result
            
            # Use local XML if available
            if self.use_local_xmls and 'file_path' in filing_info:
                try:
                    # file_path in the local index is repo-root-relative.
                    xml_path = _REPO_ROOT / filing_info['file_path']
                    
                    with open(xml_path, 'rb') as f:
                        xml_content = f.read()
                    
                    # Parse XML
                    result = self.parse_990_xml(xml_content, filing_info)
                    
                    # Cache result
                    with open(cache_file, 'w') as f:
                        json.dump(result, f)
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"Error reading local XML for EIN {ein}: {e}")
                    result = {'form_990_status': 'error', 'form_990_error': str(e), 'form_990_last_updated': datetime.now().isoformat()}
                    return result
            
            # Otherwise download from S3
            # Construct S3 key using ObjectId (or use direct URL if available)
            # GivingTuesday index columns: ObjectId, URL, TaxPeriod, FormType
            direct_url = filing_info.get('URL')
            object_id = filing_info.get('ObjectId') or filing_info.get('OBJECT_ID') or filing_info.get('object_id')
            
            if not object_id:
                logger.warning(f"No ObjectId found for EIN {ein}")
                result = {'form_990_status': 'not_found', 'form_990_last_updated': datetime.now().isoformat()}
                with open(cache_file, 'w') as f:
                    json.dump(result, f)
                return result
            
            xml_key = f"EfileData/XmlFiles/{object_id}_public.xml"
            
            try:
                # Download XML from S3
                loop = asyncio.get_event_loop()
                xml_obj = await loop.run_in_executor(
                    None,
                    lambda: self.s3.get_object(Bucket=self.bucket, Key=xml_key)
                )
                xml_content = xml_obj['Body'].read()
                
                # Parse XML
                result = self.parse_990_xml(xml_content, filing_info)
                
                # Cache result
                with open(cache_file, 'w') as f:
                    json.dump(result, f)
                
                return result
                
            except self.s3.exceptions.NoSuchKey:
                result = {
                    'form_990_status': 'not_found',
                    'form_990_last_updated': datetime.now().isoformat(),
                }
                with open(cache_file, 'w') as f:
                    json.dump(result, f)
                return result
            except Exception as e:
                logger.debug(f"Error fetching {ein}: {e}")
                result = {
                    'form_990_status': 'error',
                    'form_990_last_updated': datetime.now().isoformat(),
                }
                with open(cache_file, 'w') as f:
                    json.dump(result, f)
                return result
    
    def parse_990_xml(self, xml_content: bytes, filing_info: Dict) -> Dict:
        """
        Parse Form 990 XML and extract key fields
        
        Uses simplified xmltodict parsing (not full Giving Tuesday parser)
        """
        import xmltodict

        try:
            doc = xmltodict.parse(xml_content)
            
            # Navigate to Return -> ReturnData -> IRS990
            root = doc.get('Return', {})
            return_data = root.get('ReturnData', {})
            
            # Try 990, 990EZ, or 990PF
            form_990 = (
                return_data.get('IRS990', {}) or
                return_data.get('IRS990EZ', {}) or
                return_data.get('IRS990PF', {})
            )
            
            if not form_990:
                return {'form_990_status': 'parse_error'}
            
            # Helper to safely get numeric value
            def get_num(obj, *keys):
                for key in keys:
                    if isinstance(obj, dict):
                        obj = obj.get(key)
                    else:
                        return None
                if obj is None:
                    return None
                try:
                    return float(obj)
                except:
                    return None
            
            # Helper to safely get text
            def get_text(obj, *keys):
                for key in keys:
                    if isinstance(obj, dict):
                        obj = obj.get(key)
                    else:
                        return None
                return str(obj) if obj is not None else None
            
            # Extract officers/directors from Part VII
            officers = []
            
            # Form 990 Part VII Section A - Officers, Directors, Trustees, Key Employees
            part_vii = form_990.get('Form990PartVIISectionAGrp', [])
            
            # Ensure it's a list (xmltodict returns single item as dict)
            if isinstance(part_vii, dict):
                part_vii = [part_vii]
            
            for officer in part_vii:
                if not isinstance(officer, dict):
                    continue
                    
                name = (
                    get_text(officer, 'PersonNm') or
                    get_text(officer, 'NamePerson', 'BusinessNameLine1Txt') or
                    get_text(officer, 'NamePerson', 'BusinessNameLine1')
                )
                
                title = get_text(officer, 'TitleTxt') or get_text(officer, 'Title')
                
                hours = (
                    get_num(officer, 'AverageHoursPerWeekRt') or
                    get_num(officer, 'AverageHoursPerWeekRltdOrgRt') or
                    get_num(officer, 'AverageHours')
                )
                
                # Compensation from this org
                comp_org = (
                    get_num(officer, 'ReportableCompFromOrgAmt') or
                    get_num(officer, 'CompensationAmt') or
                    0
                )
                
                # Compensation from related orgs
                comp_related = (
                    get_num(officer, 'ReportableCompFromRltdOrgAmt') or
                    0
                )
                
                # Other compensation (benefits, deferred comp, etc)
                comp_other = (
                    get_num(officer, 'OtherCompensationAmt') or
                    0
                )
                
                # Total compensation
                total_comp = comp_org + comp_related + comp_other
                
                if name:  # Only add if we have a name
                    officers.append({
                        'name': name,
                        'title': title,
                        'hours_per_week': hours,
                        'compensation': total_comp,
                        'compensation_org': comp_org,
                        'compensation_related': comp_related,
                        'compensation_other': comp_other,
                    })
            
            # Convert officers list to JSON string for storage
            import json
            officers_json = json.dumps(officers) if officers else None
            
            # Extract fields
            result = {
                'form_990_status': 'found',
                'form_990_tax_year': filing_info.get('TaxPeriod') or filing_info.get('TAX_PERIOD'),
                'form_990_filing_type': filing_info.get('FormType') or filing_info.get('FILING_TYPE'),
                
                # Revenue
                'form_990_total_revenue': get_num(form_990, 'TotalRevenueAmt') or get_num(form_990, 'TotalRevenueCurrentYear'),
                'form_990_contributions': get_num(form_990, 'ContributionsGrantsAmt') or get_num(form_990, 'ContributionsGiftsGrantsEtc'),
                'form_990_program_revenue': get_num(form_990, 'ProgramServiceRevenueAmt') or get_num(form_990, 'ProgramServiceRevenue'),
                'form_990_investment_income': get_num(form_990, 'InvestmentIncomeAmt') or get_num(form_990, 'InvestmentIncome'),
                
                # Expenses
                'form_990_total_expenses': get_num(form_990, 'TotalExpensesAmt') or get_num(form_990, 'TotalExpensesCurrentYear'),
                'form_990_program_expenses': get_num(form_990, 'ProgramServicesAmt') or get_num(form_990, 'TotalProgramServiceExpenses'),
                'form_990_admin_expenses': get_num(form_990, 'ManagementAndGeneralAmt') or get_num(form_990, 'TotalMgmtAndGeneralExpenses'),
                'form_990_fundraising_expenses': get_num(form_990, 'FundraisingAmt') or get_num(form_990, 'TotalFundraisingExpenses'),
                
                # Assets & Net Income
                'form_990_total_assets': get_num(form_990, 'TotalAssetsEOYAmt') or get_num(form_990, 'TotalAssets'),
                'form_990_total_liabilities': get_num(form_990, 'TotalLiabilitiesEOYAmt') or get_num(form_990, 'TotalLiabilities'),
                'form_990_net_assets': get_num(form_990, 'NetAssetsOrFundBalancesEOYAmt') or get_num(form_990, 'NetAssetsOrFundBalances'),
                
                # Grants
                'form_990_grants_paid': get_num(form_990, 'GrantsAndSimilarAmountsPaidAmt') or get_num(form_990, 'GrantsAndAllocations'),
                
                # Website (Part I Line 1)
                'form_990_website': get_text(form_990, 'WebsiteAddressTxt') or get_text(form_990, 'WebsiteAddress'),
                
                # Mission (Part I Line 1 or Part III)
                'form_990_mission': (
                    get_text(form_990, 'ActivityOrMissionDesc') or 
                    get_text(form_990, 'MissionDesc') or
                    get_text(root, 'ReturnHeader', 'Filer', 'BusinessName', 'BusinessNameLine1Txt')
                ),
                
                # Officers and Directors (Part VII)
                'form_990_officers': officers_json,
                
                'form_990_last_updated': datetime.now().isoformat(),
            }
            
            # Calculate net income if revenue and expenses available
            if result['form_990_total_revenue'] and result['form_990_total_expenses']:
                result['form_990_net_income'] = result['form_990_total_revenue'] - result['form_990_total_expenses']
            
            return result
            
        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return {
                'form_990_status': 'parse_error',
                'form_990_last_updated': datetime.now().isoformat(),
            }
    
    async def enrich_dataframe(
        self,
        df: pd.DataFrame,
        ein_column: str = 'ein',
        batch_size: int = 1000,
        skip_enriched: bool = False,
        max_age_days: int = 365
    ) -> pd.DataFrame:
        """
        Enrich a DataFrame with Form 990 data
        
        Args:
            df: DataFrame with nonprofit data
            ein_column: Name of column containing EINs
            batch_size: Process in batches of this size
            skip_enriched: If True, skip records that already have recent form_990_last_updated
            max_age_days: Maximum age in days before re-enriching (used with skip_enriched)
        
        Returns:
            DataFrame with added form_990_* columns
        """
        import pandas as pd
        from tqdm import tqdm

        logger.info("=" * 60)
        logger.info("FORM 990 ENRICHMENT (GIVINGTUESDAY DATA LAKE)")
        logger.info("=" * 60)
        logger.info(f"Total records: {len(df):,}")
        logger.info(f"Max concurrent: {self.max_concurrent}")
        logger.info(f"Batch size: {batch_size:,}")
        if skip_enriched:
            logger.info(f"Incremental mode: Skipping records enriched within {max_age_days} days")
        logger.info("=" * 60)
        
        if self.index_df is None:
            logger.error("❌ Index not loaded. Run --download-index first.")
            raise ValueError("Index not loaded")
        
        # Pre-compute filing lookup for all EINs
        logger.info("🔍 Looking up filings in index...")
        ein_to_filing = {}
        for ein in tqdm(df[ein_column].unique(), desc="Looking up EINs"):
            ein_str = str(ein).zfill(9)
            filing = self.find_filing(ein_str)
            if filing:
                ein_to_filing[ein_str] = filing
        
        logger.info(f"   Found {len(ein_to_filing):,} / {len(df[ein_column].unique()):,} EINs in index")
        
        # Filter for incremental processing if requested
        if skip_enriched and 'form_990_last_updated' in df.columns:
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            
            # Find records that need enrichment
            needs_enrichment = df['form_990_last_updated'].isna()
            
            # Also re-enrich if too old
            if df['form_990_last_updated'].notna().any():
                try:
                    last_updated = pd.to_datetime(df['form_990_last_updated'], errors='coerce')
                    needs_enrichment |= (last_updated < cutoff_date)
                except:
                    pass
            
            # Filter to only records that need enrichment
            df_to_enrich = df[needs_enrichment].copy()
            df_skip = df[~needs_enrichment].copy()
            
            logger.info(f"📊 Incremental processing:")
            logger.info(f"   Skipping: {len(df_skip):,} (already enriched)")
            logger.info(f"   Enriching: {len(df_to_enrich):,} (missing or outdated)")
            
            # If nothing needs enrichment, return original
            if len(df_to_enrich) == 0:
                logger.success("✅ All records already enriched!")
                return df
            
            # Continue with df_to_enrich
            df_working = df_to_enrich
        else:
            df_working = df
            df_skip = None
        
        # Process in batches
        results = []
        num_batches = (len(df_working) + batch_size - 1) // batch_size
        
        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(df_working))
            batch_df = df_working.iloc[start_idx:end_idx]
            
            logger.info(f"\nBatch {batch_idx + 1}/{num_batches}: {len(batch_df)} records")
            
            # Fetch 990s for this batch
            tasks = []
            for _, row in batch_df.iterrows():
                ein_str = str(row[ein_column]).zfill(9)
                filing = ein_to_filing.get(ein_str)
                tasks.append(self.fetch_and_parse_990(ein_str, filing))
            
            # Run async tasks
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
        
        # Add results to DataFrame
        logger.info("\n📊 Merging results...")
        
        # Drop existing form_990_* columns from records we enriched
        form_990_cols = [col for col in df_working.columns if col.startswith('form_990_')]
        if form_990_cols:
            logger.info(f"   Dropping {len(form_990_cols)} existing form_990_* columns from enriched records")
            df_working_clean = df_working.drop(columns=form_990_cols)
        else:
            df_working_clean = df_working
        
        # Merge enriched data with results
        enriched_batch = pd.concat([df_working_clean.reset_index(drop=True), pd.DataFrame(results)], axis=1)
        
        # If we skipped records (incremental mode), combine them back
        if df_skip is not None and len(df_skip) > 0:
            logger.info(f"   Combining {len(enriched_batch):,} newly enriched + {len(df_skip):,} skipped records")
            enriched_df = pd.concat([enriched_batch, df_skip], ignore_index=True)
            # Sort to restore original order (approximately)
            enriched_df = enriched_df.sort_values(ein_column).reset_index(drop=True)
        else:
            enriched_df = enriched_batch
        
        # Stats
        found = sum(1 for r in results if r.get('form_990_status') == 'found')
        not_found = sum(1 for r in results if r.get('form_990_status') == 'not_found')
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("ENRICHMENT COMPLETE")
        logger.info("=" * 60)
        logger.info(f"✅ Processed: {len(df):,} nonprofits")
        logger.info(f"✅ Found 990s: {found:,} ({100*found/len(df):.1f}%)")
        logger.info(f"⚠️  Not found: {not_found:,}")
        logger.info("=" * 60)
        
        return enriched_df


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser (pure; safe to call without heavy deps)."""
    parser = argparse.ArgumentParser(
        description="Enrich nonprofit data with Form 990 XML from GivingTuesday Data Lake",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download index (one-time setup)
  python -m scrapers.irs.enrich_nonprofits_gt990 --download-index

  # Enrich Tuscaloosa nonprofits
  python -m scrapers.irs.enrich_nonprofits_gt990 \\
      --input data/gold/nonprofits_tuscaloosa.parquet \\
      --output data/gold/nonprofits_tuscaloosa_form990.parquet

  # Enrich Alabama + Michigan nonprofits
  python -m scrapers.irs.enrich_nonprofits_gt990 \\
      --input data/gold/nonprofits_organizations.parquet \\
      --output data/gold/nonprofits_990_enriched.parquet \\
      --states AL MI \\
      --concurrent 50

Data Lake: https://990data.givingtuesday.org/
        """
    )

    parser.add_argument('--download-index', action='store_true',
                        help='Download GivingTuesday Data Lake index (one-time setup)')
    parser.add_argument('--input', type=str,
                        help='Input parquet file with nonprofit data')
    parser.add_argument('--output', type=str,
                        help='Output parquet file with enriched data')
    parser.add_argument('--states', nargs='+',
                        help='Filter to specific states (e.g., AL MI)')
    parser.add_argument('--ntee', type=str,
                        help='Filter to NTEE code prefix (e.g., E for health)')
    parser.add_argument('--sample', type=int,
                        help='Sample N records for testing')
    parser.add_argument('--concurrent', type=int, default=20,
                        help='Max concurrent requests (default: 20)')
    parser.add_argument('--skip-enriched', action='store_true',
                        help='Skip records already enriched (incremental mode)')
    parser.add_argument('--max-age-days', type=int, default=365,
                        help='Re-enrich if older than N days (default: 365, used with --skip-enriched)')
    parser.add_argument('--index-key', type=str,
                        default='Indices/990xmls/index_all_years_efiledata_xmls_created_on_2023-10-29.csv',
                        help='S3 key for index file')
    parser.add_argument('--use-local', action='store_true',
                        help='Use locally extracted XMLs instead of downloading from S3')
    parser.add_argument('--local-index', type=str,
                        default='data/cache/form990/local_index_dev_states.parquet',
                        help='Path to local XML index (default: data/cache/form990/local_index_dev_states.parquet)')

    return parser


async def main():
    import pandas as pd

    _configure_logging()

    parser = build_parser()
    args = parser.parse_args()

    # Initialize enricher
    enricher = GivingTuesday990Enricher(
        max_concurrent=args.concurrent,
        use_local_xmls=args.use_local,
        local_index_path=args.local_index
    )
    
    # Download index if requested
    if args.download_index:
        enricher.download_index(index_key=args.index_key)
        logger.success("✅ Index download complete!")
        return
    
    # Validate arguments for enrichment
    if not args.input or not args.output:
        parser.error("--input and --output are required for enrichment")
    
    # Load input data
    logger.info(f"📂 Loading {args.input}")
    df = pd.read_parquet(args.input)
    logger.info(f"   Loaded {len(df):,} nonprofits")
    
    # Apply filters
    if args.states:
        df = df[df['state'].isin(args.states)]
        logger.info(f"   Filtered to states {args.states}: {len(df):,} records")
    
    if args.ntee:
        df = df[df['ntee_code'].str.startswith(args.ntee, na=False)]
        logger.info(f"   Filtered to NTEE {args.ntee}: {len(df):,} records")
    
    if args.sample:
        df = df.sample(n=min(args.sample, len(df)), random_state=42)
        logger.info(f"   Sampled {len(df):,} nonprofits")
    
    # Enrich the dataset
    logger.info(f"\n🔄 Enriching {len(df):,} nonprofits...")
    enriched_df = await enricher.enrich_dataframe(
        df, 
        skip_enriched=args.skip_enriched,
        max_age_days=args.max_age_days
    )
    
    # Save
    enriched_df.to_parquet(args.output, index=False)
    logger.success(f"💾 Saved to: {args.output}")
    logger.success(f"   ✅ Enriched {len(enriched_df):,} organizations")
    
    # Show sample
    logger.info("\n📊 Sample enriched records:")
    sample_cols = ['organization_name', 'form_990_status', 'form_990_total_revenue', 'form_990_total_expenses', 'form_990_officers']
    available_cols = [c for c in sample_cols if c in enriched_df.columns]
    if available_cols:
        print(enriched_df[available_cols].head(10).to_string())
    
    logger.success("\n🎉 Enrichment complete!")


if __name__ == '__main__':
    asyncio.run(main())
