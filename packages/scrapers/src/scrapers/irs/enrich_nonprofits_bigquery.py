#!/usr/bin/env python3
"""
Enrich nonprofit data with mission statements and website URLs from Google BigQuery IRS 990 dataset.

Usage:
    python -m scrapers.irs.enrich_nonprofits_bigquery \\
        --input data/gold/nonprofits_tuscaloosa_form990.parquet \\
        --output data/gold/nonprofits_tuscaloosa_bigquery.parquet

Features:
    - Queries public BigQuery IRS 990 dataset (no auth required)
    - Extracts mission statements and website URLs
    - Tries multiple years (2023, 2022, 2021) and form types (990, 990-EZ)
    - Merges results with existing nonprofit data
    - Adds bigquery_mission and bigquery_website fields
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from loguru import logger


def _configure_logging() -> None:
    """Configure loguru sink. Kept out of import so importing this module as a
    library does not mutate global loguru handlers."""
    logger.remove()
    logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


class BigQueryNonprofitEnricher:
    """Enrich nonprofit data using Google BigQuery IRS 990 public dataset."""

    def __init__(self, project: Optional[str] = None, skip_client: bool = False):
        """
        Initialize BigQuery client.

        Args:
            project: Google Cloud project ID (required for queries)
            skip_client: Skip client initialization (for SQL export only)
        """
        if skip_client:
            self.client = None
            return

        from google.auth import exceptions as auth_exceptions
        from google.cloud import bigquery

        try:
            self.client = bigquery.Client(project=project)
            logger.info(f"✅ BigQuery client initialized (project: {project})")
        except (auth_exceptions.DefaultCredentialsError, Exception) as e:
            logger.error(f"❌ Failed to initialize BigQuery client: {e}")
            logger.error("Please set up authentication:")
            logger.error("  gcloud auth application-default login")
            raise
    
    def build_query(self, eins: list[str], years: list[str] = None, include_officers: bool = True) -> str:
        """
        Build SQL query to extract missions, websites, and officer data for given EINs.
        
        Args:
            eins: List of EIN strings to query
            years: List of tax years to query (default: ['2023', '2022', '2021'])
            include_officers: Whether to include officer/board member data from Schedule J
        
        Returns:
            SQL query string
        """
        if years is None:
            years = ['2023', '2022', '2021']
        
        # Format EINs for SQL
        ein_list = ', '.join([f'"{ein}"' for ein in eins])
        
        # Build CTE for each year and form type
        ctes = []
        union_selects = []
        
        for year in years:
            # Full Form 990
            cte_name = f'form_990_{year}'
            ctes.append(f"""
{cte_name} AS (
  SELECT 
    ein,
    activity_or_mission_desc AS mission,
    website_address_txt AS website,
    '{year}' AS tax_year,
    '990' AS form_type
  FROM `bigquery-public-data.irs_990.irs_990_{year}`
  WHERE ein IN ({ein_list})
    AND (activity_or_mission_desc IS NOT NULL OR website_address_txt IS NOT NULL)
)""")
            union_selects.append(f"SELECT * FROM {cte_name}")
            
            # 990-EZ (small organizations)
            cte_ez_name = f'form_990_ez_{year}'
            ctes.append(f"""
{cte_ez_name} AS (
  SELECT 
    ein,
    mission_description AS mission,
    website_address_txt AS website,
    '{year}' AS tax_year,
    '990-EZ' AS form_type
  FROM `bigquery-public-data.irs_990.irs_990_ez_{year}`
  WHERE ein IN ({ein_list})
    AND (mission_description IS NOT NULL OR website_address_txt IS NOT NULL)
)""")
            union_selects.append(f"SELECT * FROM {cte_ez_name}")
        
        # Add officer data CTEs if requested
        if include_officers:
            for year in years:
                officer_cte = f'officers_{year}'
                ctes.append(f"""
{officer_cte} AS (
  SELECT 
    ein,
    person_name,
    title_txt AS title,
    compensation_amount,
    average_hours_per_week,
    '{year}' AS tax_year
  FROM `bigquery-public-data.irs_990.irs_990_schedule_j_{year}`
  WHERE ein IN ({ein_list})
    AND person_name IS NOT NULL
)""")
        
        # Combine all CTEs
        query = "WITH\n" + ",\n".join(ctes) + ",\n\n"
        
        # Union all results and deduplicate (prefer most recent year)
        query += """
-- Combine financial data sources and deduplicate (prefer most recent)
financial_data AS (
  SELECT 
    ein,
    FIRST_VALUE(mission) OVER (PARTITION BY ein ORDER BY tax_year DESC, form_type) AS mission,
    FIRST_VALUE(website) OVER (PARTITION BY ein ORDER BY tax_year DESC, form_type) AS website,
    FIRST_VALUE(tax_year) OVER (PARTITION BY ein ORDER BY tax_year DESC, form_type) AS tax_year,
    FIRST_VALUE(form_type) OVER (PARTITION BY ein ORDER BY tax_year DESC, form_type) AS form_type
  FROM (
    """ + "\n    UNION ALL\n    ".join(union_selects) + """
  )
  QUALIFY ROW_NUMBER() OVER (PARTITION BY ein ORDER BY tax_year DESC, form_type) = 1
)"""
        
        if include_officers:
            # Aggregate officers into JSON array
            query += """,

-- Aggregate officers by EIN (most recent year)
officer_data AS (
  SELECT 
    ein,
    tax_year,
    ARRAY_AGG(
      STRUCT(
        person_name AS name,
        title,
        compensation_amount AS compensation,
        average_hours_per_week AS hours_per_week
      ) 
      ORDER BY compensation_amount DESC NULLS LAST
    ) AS officers
  FROM (
    SELECT *,
      ROW_NUMBER() OVER (PARTITION BY ein ORDER BY tax_year DESC) AS rn
    FROM (
      """ + "\n      UNION ALL\n      ".join([f"SELECT * FROM officers_{year}" for year in years]) + """
    )
  )
  WHERE rn = 1
  GROUP BY ein, tax_year
)

-- Final join
SELECT 
  f.ein,
  f.mission,
  f.website,
  f.tax_year,
  f.form_type,
  o.officers,
  o.tax_year AS officers_tax_year
FROM financial_data f
LEFT JOIN officer_data o USING (ein)
ORDER BY f.ein;
"""
        else:
            query += """
SELECT * FROM financial_data
ORDER BY ein;
"""
        
        return query
    
    def query_bigquery(self, eins: list[str], years: list[str] = None, include_officers: bool = True) -> pd.DataFrame:
        """
        Query BigQuery for mission, website, and officer data.
        
        Args:
            eins: List of EIN strings
            years: List of tax years to query
            include_officers: Whether to include officer/board member data
        
        Returns:
            DataFrame with columns: ein, mission, website, tax_year, form_type, officers (if include_officers=True)
        """
        import pandas as pd

        query = self.build_query(eins, years, include_officers)
        
        logger.info(f"🔍 Querying BigQuery for {len(eins):,} EINs...")
        if include_officers:
            logger.info("   Including officer and board member data")
        logger.debug(f"Query length: {len(query):,} characters")
        
        try:
            # Run query
            query_job = self.client.query(query)
            results = query_job.result()
            
            # Convert to DataFrame
            df = results.to_dataframe()
            
            logger.info(f"✅ BigQuery returned {len(df):,} records")
            logger.info(f"   Missions: {df['mission'].notna().sum():,}")
            logger.info(f"   Websites: {df['website'].notna().sum():,}")
            if include_officers and 'officers' in df.columns:
                orgs_with_officers = df['officers'].apply(lambda x: x is not None and len(x) > 0).sum()
                logger.info(f"   Organizations with officers: {orgs_with_officers:,}")
            
            return df
            
        except Exception as e:
            logger.error(f"❌ BigQuery query failed: {e}")
            # Return empty DataFrame with correct schema
            base_cols = ['ein', 'mission', 'website', 'tax_year', 'form_type']
            if include_officers:
                base_cols.extend(['officers', 'officers_tax_year'])
            return pd.DataFrame(columns=base_cols)
    
    def enrich_dataframe(
        self, 
        df: pd.DataFrame, 
        ein_column: str = 'ein',
        years: list[str] = None,
        include_officers: bool = True
    ) -> pd.DataFrame:
        """
        Enrich a DataFrame with BigQuery mission, website, and officer data.
        
        Args:
            df: Input DataFrame with EIN column
            ein_column: Name of the EIN column
            years: Tax years to query
            include_officers: Whether to include officer/board member data
        
        Returns:
            Enriched DataFrame with bigquery_mission, bigquery_website, bigquery_officers, etc.
        """
        import pandas as pd

        logger.info(f"📊 Enriching {len(df):,} organizations from BigQuery")
        if include_officers:
            logger.info("   Including officer and board member data")
        
        # Get unique EINs
        eins = df[ein_column].dropna().unique().tolist()
        logger.info(f"   Unique EINs: {len(eins):,}")
        
        # Batch queries to avoid query size limit (1MB)
        # Each EIN is ~30 chars in the query, limit to ~5000 per batch
        batch_size = 5000
        all_bq_data = []
        
        for i in range(0, len(eins), batch_size):
            batch = eins[i:i+batch_size]
            logger.info(f"🔍 Querying batch {i//batch_size + 1}/{(len(eins)-1)//batch_size + 1} ({len(batch):,} EINs)...")
            bq_data = self.query_bigquery(batch, years, include_officers)
            if len(bq_data) > 0:
                all_bq_data.append(bq_data)
        
        # Combine all batches
        if len(all_bq_data) == 0:
            bq_data = pd.DataFrame()
        else:
            bq_data = pd.concat(all_bq_data, ignore_index=True)
        
        if len(bq_data) == 0:
            logger.warning("⚠️  No data returned from BigQuery")
            # Add empty columns
            df['bigquery_mission'] = None
            df['bigquery_website'] = None
            df['bigquery_tax_year'] = None
            df['bigquery_form_type'] = None
            df['bigquery_updated_date'] = None
            if include_officers:
                df['bigquery_officers'] = None
                df['bigquery_officers_tax_year'] = None
            return df
        
        # Rename columns to avoid conflicts
        rename_map = {
            'mission': 'bigquery_mission',
            'website': 'bigquery_website',
            'tax_year': 'bigquery_tax_year',
            'form_type': 'bigquery_form_type'
        }
        if include_officers and 'officers' in bq_data.columns:
            rename_map['officers'] = 'bigquery_officers'
            rename_map['officers_tax_year'] = 'bigquery_officers_tax_year'
        
        bq_data = bq_data.rename(columns=rename_map)
        
        # Convert officers array to JSON string for storage
        if include_officers and 'bigquery_officers' in bq_data.columns:
            import json
            bq_data['bigquery_officers'] = bq_data['bigquery_officers'].apply(
                lambda x: json.dumps([dict(o) for o in x]) if x and len(x) > 0 else None
            )
        
        # Add timestamp
        from datetime import datetime
        bq_data['bigquery_updated_date'] = datetime.now().strftime('%Y-%m-%d')
        
        # Drop existing BigQuery columns if present
        bigquery_cols = [col for col in df.columns if col.startswith('bigquery_')]
        if bigquery_cols:
            logger.info(f"   Dropping existing BigQuery columns: {', '.join(bigquery_cols)}")
            df = df.drop(columns=bigquery_cols)
        
        # Merge with original data
        enriched = df.merge(bq_data, left_on=ein_column, right_on='ein', how='left', suffixes=('', '_bq'))
        
        # Clean up duplicate ein column if created
        if 'ein_bq' in enriched.columns:
            enriched = enriched.drop(columns=['ein_bq'])
        
        # Statistics
        missions_added = enriched['bigquery_mission'].notna().sum()
        websites_added = enriched['bigquery_website'].notna().sum()
        
        logger.info(f"✅ Enrichment complete:")
        logger.info(f"   Added missions: {missions_added:,} ({100*missions_added/len(enriched):.1f}%)")
        logger.info(f"   Added websites: {websites_added:,} ({100*websites_added/len(enriched):.1f}%)")
        
        if include_officers and 'bigquery_officers' in enriched.columns:
            officers_added = enriched['bigquery_officers'].notna().sum()
            logger.info(f"   Added officers: {officers_added:,} ({100*officers_added/len(enriched):.1f}%)")
        
        return enriched


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser (pure; safe to call without heavy deps)."""
    parser = argparse.ArgumentParser(
        description="Enrich nonprofit data with BigQuery IRS 990 missions and websites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export SQL query for BigQuery web UI (no auth required)
  python -m scrapers.irs.enrich_nonprofits_bigquery \\
      --input data/gold/nonprofits_tuscaloosa_form990.parquet \\
      --export-sql data/cache/bigquery_tuscaloosa_missions.sql

  # Merge BigQuery CSV export into existing file (update in place)
  python -m scrapers.irs.enrich_nonprofits_bigquery \\
      --input data/gold/nonprofits_tuscaloosa_form990.parquet \\
      --from-csv data/cache/bigquery_results.csv \\
      --update-in-place

  # Merge BigQuery CSV export into new file
  python -m scrapers.irs.enrich_nonprofits_bigquery \\
      --input data/gold/nonprofits_tuscaloosa_form990.parquet \\
      --output data/gold/nonprofits_tuscaloosa_bigquery.parquet \\
      --from-csv data/cache/bigquery_results.csv

  # Direct BigQuery query (requires auth)
  python -m scrapers.irs.enrich_nonprofits_bigquery \\
      --input data/gold/nonprofits_organizations.parquet \\
      --output data/gold/nonprofits_bigquery.parquet \\
      --project my-gcp-project \\
      --years 2023 2022
        """
    )

    parser.add_argument('--input', required=True, help='Input parquet file with nonprofit data')
    parser.add_argument('--output', help='Output parquet file for enriched data (required unless --export-sql)')
    parser.add_argument('--ein-column', default='ein', help='Name of EIN column (default: ein)')
    parser.add_argument('--years', nargs='+', default=['2023', '2022', '2021'], 
                        help='Tax years to query (default: 2023 2022 2021)')
    parser.add_argument('--project', help='Google Cloud project ID (required for direct BigQuery access)')
    parser.add_argument('--sample', type=int, help='Sample N organizations for testing')
    parser.add_argument('--from-csv', help='Merge from BigQuery CSV export instead of querying directly')
    parser.add_argument('--export-sql', help='Export SQL query to file instead of running')
    parser.add_argument('--update-in-place', action='store_true', 
                        help='Update input file instead of creating new output file')
    parser.add_argument('--no-officers', action='store_true',
                        help='Skip officer/board member data from Schedule J (use if tables unavailable)')

    return parser


def main():
    import pandas as pd

    _configure_logging()

    parser = build_parser()
    args = parser.parse_args()

    # Validate: --output required unless using --export-sql or --update-in-place
    if not args.export_sql and not args.output and not args.update_in_place:
        parser.error("--output is required unless using --export-sql or --update-in-place")
    
    # If update-in-place, use input as output
    if args.update_in_place:
        if args.output:
            logger.warning("⚠️  Both --update-in-place and --output specified. Using --update-in-place.")
        args.output = args.input
    
    # Validate files
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"❌ Input file not found: {input_path}")
        sys.exit(1)
    
    # Load data
    logger.info(f"📂 Loading: {input_path}")
    df = pd.read_parquet(input_path)
    logger.info(f"   Loaded {len(df):,} organizations")
    
    # Sample if requested
    if args.sample:
        logger.info(f"🎲 Sampling {args.sample:,} organizations for testing")
        df = df.sample(n=min(args.sample, len(df)), random_state=42)
    
    # Check for EIN column
    if args.ein_column not in df.columns:
        logger.error(f"❌ EIN column '{args.ein_column}' not found in data")
        logger.error(f"   Available columns: {', '.join(df.columns)}")
        sys.exit(1)
    
    # MODE 1: Export SQL for web UI
    if args.export_sql:
        logger.info(f"📝 Exporting SQL query to: {args.export_sql}")
        enricher = BigQueryNonprofitEnricher(skip_client=True)  # Don't need real client
        eins = df[args.ein_column].dropna().unique().tolist()
        sql = enricher.build_query(eins, years=args.years)
        
        sql_path = Path(args.export_sql)
        sql_path.parent.mkdir(parents=True, exist_ok=True)
        with open(sql_path, 'w') as f:
            f.write(sql)
        
        logger.info(f"✅ SQL query exported ({len(sql):,} characters)")
        logger.info(f"\n📋 NEXT STEPS:")
        logger.info(f"1. Go to: https://console.cloud.google.com/bigquery")
        logger.info(f"2. Click 'COMPOSE NEW QUERY'")
        logger.info(f"3. Paste contents of: {sql_path}")
        logger.info(f"4. Click 'RUN'")
        logger.info(f"5. Click 'SAVE RESULTS' → 'CSV (local file)'")
        logger.info(f"6. Save as: data/cache/bigquery_results.csv")
        logger.info(f"7. Merge results:")
        logger.info(f"   python -m scrapers.irs.enrich_nonprofits_bigquery \\")
        logger.info(f"       --input {args.input} \\")
        logger.info(f"       --from-csv data/cache/bigquery_results.csv \\")
        logger.info(f"       --update-in-place")
        return
    
    # Setup output path for modes 2 and 3
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # MODE 2: Merge from CSV export
    if args.from_csv:
        logger.info(f"📂 Loading BigQuery results from CSV: {args.from_csv}")
        csv_path = Path(args.from_csv)
        if not csv_path.exists():
            logger.error(f"❌ CSV file not found: {csv_path}")
            sys.exit(1)
        
        bq_data = pd.read_csv(csv_path)
        logger.info(f"   Loaded {len(bq_data):,} records from BigQuery export")
        
        # Rename columns
        column_mapping = {
            'ein': 'ein',
            'mission': 'bigquery_mission',
            'website': 'bigquery_website',
            'tax_year': 'bigquery_tax_year',
            'form_type': 'bigquery_form_type'
        }
        bq_data = bq_data.rename(columns=column_mapping)
        
        # Add timestamp for when BigQuery data was added
        from datetime import datetime
        bq_data['bigquery_updated_date'] = datetime.now().strftime('%Y-%m-%d')
        
        # Merge with original data
        # First, drop any existing BigQuery columns to avoid conflicts
        bigquery_cols = [col for col in df.columns if col.startswith('bigquery_')]
        if bigquery_cols:
            logger.info(f"   Dropping existing BigQuery columns: {', '.join(bigquery_cols)}")
            df = df.drop(columns=bigquery_cols)
        
        enriched = df.merge(bq_data, on='ein', how='left')
        
        missions_added = enriched['bigquery_mission'].notna().sum()
        websites_added = enriched['bigquery_website'].notna().sum()
        logger.info(f"✅ Merged BigQuery data:")
        logger.info(f"   Missions: {missions_added:,} ({100*missions_added/len(enriched):.1f}%)")
        logger.info(f"   Websites: {websites_added:,} ({100*websites_added/len(enriched):.1f}%)")
    
    # MODE 3: Direct BigQuery query (requires auth)
    else:
        if not args.project:
            logger.error("❌ ERROR: --project required for direct BigQuery access")
            logger.error("")
            logger.error("OPTION 1 - Use Web UI (No auth required):")
            logger.error("  1. Run: python -m scrapers.irs.enrich_nonprofits_bigquery \\")
            logger.error("           --input data/gold/nonprofits_tuscaloosa_form990.parquet \\")
            logger.error("           --export-sql data/cache/bigquery_query.sql")
            logger.error("  2. Run SQL in BigQuery web console")
            logger.error("  3. Export CSV")
            logger.error("  4. Run: python -m scrapers.irs.enrich_nonprofits_bigquery \\")
            logger.error("           --input data/gold/nonprofits_tuscaloosa_form990.parquet \\")
            logger.error("           --output data/gold/nonprofits_tuscaloosa_bigquery.parquet \\")
            logger.error("           --from-csv data/cache/bigquery_results.csv")
            logger.error("")
            logger.error("OPTION 2 - Set up authentication:")
            logger.error("  Run: gcloud auth application-default login")
            logger.error("  Then: python -m scrapers.irs.enrich_nonprofits_bigquery \\")
            logger.error("           --input ... --output ... --project YOUR_PROJECT_ID")
            sys.exit(1)
        
        # Enrich
        enricher = BigQueryNonprofitEnricher(project=args.project)
        include_officers = not args.no_officers
        enriched = enricher.enrich_dataframe(
            df, 
            ein_column=args.ein_column, 
            years=args.years,
            include_officers=include_officers
        )
    
    # Save
    logger.info(f"💾 Saving to: {output_path}")
    enriched.to_parquet(output_path, index=False)
    
    file_size = output_path.stat().st_size / 1024
    logger.info(f"✅ Saved {len(enriched):,} records ({file_size:.1f} KB)")
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("📊 ENRICHMENT SUMMARY")
    logger.info("=" * 70)
    
    # Count non-null values
    logger.info(f"\n💰 DATA COVERAGE:")
    logger.info(f"   Organizations: {len(enriched):,}")
    logger.info(f"   BigQuery missions: {enriched['bigquery_mission'].notna().sum():,} "
                f"({100*enriched['bigquery_mission'].notna().sum()/len(enriched):.1f}%)")
    logger.info(f"   BigQuery websites: {enriched['bigquery_website'].notna().sum():,} "
                f"({100*enriched['bigquery_website'].notna().sum()/len(enriched):.1f}%)")
    
    # Show update date
    if 'bigquery_updated_date' in enriched.columns:
        update_date = enriched['bigquery_updated_date'].mode()[0] if enriched['bigquery_updated_date'].notna().any() else 'N/A'
        logger.info(f"   Updated: {update_date}")
    
    # Compare with existing data if available
    if 'form_990_mission' in enriched.columns:
        gt_missions = enriched['form_990_mission'].notna().sum()
        bq_missions = enriched['bigquery_mission'].notna().sum()
        logger.info(f"\n📈 MISSION COMPARISON:")
        logger.info(f"   GivingTuesday: {gt_missions:,} ({100*gt_missions/len(enriched):.1f}%)")
        logger.info(f"   BigQuery: {bq_missions:,} ({100*bq_missions/len(enriched):.1f}%)")
        
        # Check overlap
        both = (enriched['form_990_mission'].notna() & enriched['bigquery_mission'].notna()).sum()
        logger.info(f"   Both sources: {both:,} ({100*both/len(enriched):.1f}%)")
        
        # Combined coverage
        either = (enriched['form_990_mission'].notna() | enriched['bigquery_mission'].notna()).sum()
        logger.info(f"   Combined: {either:,} ({100*either/len(enriched):.1f}%)")
    
    # Website sources
    if 'website' in enriched.columns:
        eobmf_websites = enriched['website'].notna().sum()
        bq_websites = enriched['bigquery_website'].notna().sum()
        logger.info(f"\n🌐 WEBSITE COMPARISON:")
        logger.info(f"   EO-BMF: {eobmf_websites:,} ({100*eobmf_websites/len(enriched):.1f}%)")
        logger.info(f"   BigQuery: {bq_websites:,} ({100*bq_websites/len(enriched):.1f}%)")
        
        # Combined
        either_web = (enriched['website'].notna() | enriched['bigquery_website'].notna()).sum()
        logger.info(f"   Combined: {either_web:,} ({100*either_web/len(enriched):.1f}%)")
    
    logger.info("\n" + "=" * 70)
    logger.info("✅ COMPLETE!")
    logger.info("=" * 70)


if __name__ == '__main__':
    main()
