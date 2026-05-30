"""
Create Grants Gold Tables from IRS Form 990 Data

Extract grant transaction data from IRS Form 990 filings:
- Schedule I: Grants and assistance to organizations/individuals
- Schedule H (hospitals): Community benefits and charity care
- Schedule J: Officer compensation (already handled separately)

Gold Tables Created:
1. grants_nonprofit_to_nonprofit - Grants paid by nonprofits (Schedule I Part II)
2. grants_nonprofit_to_individual - Grants/assistance to individuals (Schedule I Part III)
3. grants_foundation_giving - Private foundation grants (990-PF)
4. grants_revenue_sources - Breakdown of grant revenue received by nonprofits
5. provider_relationships - Nonprofit partnerships and collaborations

Data Sources:
- IRS Form 990 Schedule I (BigQuery: irs_990.irs_990_YYYY)
- IRS Form 990-PF Schedule (BigQuery: irs_990.irs_990_pf_YYYY)
- ProPublica Nonprofit Explorer API
- GivingTuesday GT990 API

Input:
- nonprofits_organizations.parquet (EIN list)
- BigQuery IRS 990 data
Output:
- data/gold/states/{STATE}/grants_*.parquet
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class GrantsGoldTableCreator:
    """Extract grant transaction data from Form 990 filings"""
    
    def __init__(
        self,
        gold_dir: str = "data/gold",
        state_code: Optional[str] = None
    ):
        self.state_code = state_code
        
        # Use state-based directory structure if state_code provided
        if state_code:
            self.gold_dir = Path(gold_dir) / "states" / state_code
        else:
            self.gold_dir = Path(gold_dir)
        
        self.gold_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"State Code: {state_code or 'ALL (national)'}")
        logger.info(f"Gold Dir: {self.gold_dir}")
    
    def create_grants_revenue_sources(self, nonprofits_df: pd.DataFrame) -> pd.DataFrame:
        """
        Create revenue source breakdown table from nonprofit financials
        
        Shows where nonprofits get their funding from:
        - Government grants (federal, state, local)
        - Foundation grants  
        - Corporate donations
        - Individual donations
        - Program service revenue (earned income)
        - Investment income
        
        This data comes from Form 990 Part VIII (Revenue)
        
        Args:
            nonprofits_df: DataFrame with nonprofit organizations
            
        Returns:
            DataFrame with revenue sources by organization
        """
        logger.info("=" * 60)
        logger.info("Creating grants revenue sources table")
        logger.info("=" * 60)
        
        # Placeholder structure - will be populated when we have BigQuery data
        revenue_df = pd.DataFrame({
            'ein': [],
            'organization_name': [],
            'tax_year': [],
            'total_revenue': [],
            'government_grants': [],
            'foundation_grants': [],
            'corporate_donations': [],
            'individual_donations': [],
            'membership_dues': [],
            'special_events_revenue': [],
            'program_service_revenue': [],
            'investment_income': [],
            'rental_income': [],
            'other_revenue': [],
            'state': [],
            'source': [],
            'last_updated': []
        })
        
        output_path = self.gold_dir / "grants_revenue_sources.parquet"
        revenue_df.to_parquet(output_path, index=False)
        logger.info(f"Created {output_path} (placeholder - needs BigQuery enrichment)")
        
        return revenue_df
    
    def create_grants_nonprofit_to_nonprofit(self, nonprofits_df: pd.DataFrame) -> pd.DataFrame:
        """
        Create grants paid table from Schedule I Part II
        
        IRS Form 990 Schedule I Part II shows grants and assistance paid to 
        other organizations, governments, and individuals outside the U.S.
        
        This is the GOLD STANDARD for tracking foundation giving patterns!
        
        Args:
            nonprofits_df: DataFrame with nonprofit organizations
            
        Returns:
            DataFrame with grant transactions
        """
        logger.info("=" * 60)
        logger.info("Creating grants nonprofit-to-nonprofit table (Schedule I)")
        logger.info("=" * 60)
        
        # Placeholder structure - populated from BigQuery Schedule I data
        grants_df = pd.DataFrame({
            'grant_id': [],
            'funder_ein': [],
            'funder_name': [],
            'funder_type': [],  # 'public_charity', 'private_foundation', etc.
            'recipient_ein': [],
            'recipient_name': [],
            'recipient_type': [],  # 'nonprofit', 'government', 'international'
            'recipient_address': [],
            'recipient_city': [],
            'recipient_state': [],
            'recipient_zip': [],
            'recipient_country': [],
            'grant_amount': [],
            'grant_purpose': [],
            'cash_grant': [],
            'noncash_grant': [],
            'noncash_description': [],
            'tax_year': [],
            'filing_date': [],
            'source': [],  # 'irs_990_schedule_i', 'bigquery', etc.
            'extracted_date': []
        })
        
        output_path = self.gold_dir / "grants_nonprofit_to_nonprofit.parquet"
        grants_df.to_parquet(output_path, index=False)
        logger.info(f"Created {output_path} (placeholder - needs BigQuery Schedule I data)")
        logger.info("💡 To populate: Use BigQuery irs_990.irs_990_schedule_i_YYYY tables")
        
        return grants_df
    
    def create_grants_foundation_giving(self, nonprofits_df: pd.DataFrame) -> pd.DataFrame:
        """
        Create foundation giving table from Form 990-PF
        
        Private foundations file Form 990-PF which includes detailed grant
        information in Part XV (Grants and Contributions Paid).
        
        This shows WHERE foundation money goes!
        
        Args:
            nonprofits_df: DataFrame with nonprofit organizations
            
        Returns:
            DataFrame with foundation grants
        """
        logger.info("=" * 60)
        logger.info("Creating foundation giving table (990-PF)")
        logger.info("=" * 60)
        
        # Filter for private foundations (foundation_code 10-13)
        if 'foundation' in nonprofits_df.columns:
            foundations = nonprofits_df[
                nonprofits_df['foundation'].isin(['10', '11', '12', '13'])
            ].copy()
            logger.info(f"Found {len(foundations)} private foundations in data")
        else:
            foundations = pd.DataFrame()
            logger.warning("No foundation_code column - cannot filter for private foundations")
        
        # Placeholder structure - populated from BigQuery 990-PF data
        pf_grants_df = pd.DataFrame({
            'grant_id': [],
            'foundation_ein': [],
            'foundation_name': [],
            'foundation_assets': [],
            'foundation_type': [],  # 'operating', 'non-operating'
            'recipient_name': [],
            'recipient_ein': [],
            'recipient_type': [],  # 'public_charity', 'individual', 'government'
            'recipient_purpose': [],
            'grant_amount': [],
            'relationship_to_foundation': [],  # e.g., 'board_member', 'employee', 'none'
            'tax_year': [],
            'fiscal_year_end': [],
            'source': [],
            'extracted_date': []
        })
        
        output_path = self.gold_dir / "grants_foundation_giving.parquet"
        pf_grants_df.to_parquet(output_path, index=False)
        logger.info(f"Created {output_path} (placeholder - needs BigQuery 990-PF data)")
        logger.info("💡 To populate: Use BigQuery irs_990.irs_990_pf_YYYY tables")
        
        return pf_grants_df
    
    def create_provider_relationships(self, nonprofits_df: pd.DataFrame) -> pd.DataFrame:
        """
        Create nonprofit relationship table
        
        Tracks partnerships, collaborations, and service referrals between nonprofits.
        Data sources:
        - Findhelp.org provider network
        - 211 referral data
        - United Way partnerships
        - Grant co-applicants (from Schedule I)
        - Shared board members (from officer data)
        
        Args:
            nonprofits_df: DataFrame with nonprofit organizations
            
        Returns:
            DataFrame with nonprofit relationships
        """
        logger.info("=" * 60)
        logger.info("Creating provider relationships table")
        logger.info("=" * 60)
        
        # Placeholder structure
        relationships_df = pd.DataFrame({
            'relationship_id': [],
            'organization_ein': [],
            'organization_name': [],
            'partner_ein': [],
            'partner_name': [],
            'relationship_type': [],  # 'referral', 'collaboration', 'grant', 'shared_board'
            'relationship_strength': [],  # 'weak', 'moderate', 'strong'
            'service_overlap': [],  # Services both organizations provide
            'geographic_overlap': [],  # Counties both serve
            'funding_overlap': [],  # Shared funders
            'first_observed': [],
            'last_observed': [],
            'is_active': [],
            'source': [],
            'created_date': []
        })
        
        output_path = self.gold_dir / "provider_relationships.parquet"
        relationships_df.to_parquet(output_path, index=False)
        logger.info(f"Created {output_path} (placeholder - needs Findhelp/211 data)")
        
        return relationships_df
    
    def create_all_grant_tables(self, nonprofits_df: pd.DataFrame):
        """
        Create all grant-related gold tables
        
        Args:
            nonprofits_df: DataFrame with nonprofit organizations
        """
        logger.info("=" * 60)
        logger.info("CREATING ALL GRANT TABLES")
        logger.info("=" * 60)
        
        # Create each table
        self.create_grants_revenue_sources(nonprofits_df)
        self.create_grants_nonprofit_to_nonprofit(nonprofits_df)
        self.create_grants_foundation_giving(nonprofits_df)
        self.create_provider_relationships(nonprofits_df)
        
        logger.success("=" * 60)
        logger.success("ALL GRANT TABLES CREATED (placeholders)!")
        logger.success("=" * 60)
        
        # Show summary
        grant_files = list(self.gold_dir.glob("grants_*.parquet")) + \
                      list(self.gold_dir.glob("provider_*.parquet"))
        
        if grant_files:
            logger.info(f"\nCreated {len(grant_files)} grant tables:")
            for file in sorted(grant_files):
                df = pd.read_parquet(file)
                logger.info(f"  ✅ {file.name:<45} {len(df):>5} rows")
        
        logger.warning("\n⚠️  NEXT STEPS TO POPULATE DATA:")
        logger.warning("1. Run BigQuery enrichment for Schedule I data")
        logger.warning("2. Extract 990-PF foundation grants")
        logger.warning("3. Integrate Findhelp.org provider network")
        logger.warning("4. Add grant revenue sources from Form 990 Part VIII")


def main():
    """Example usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Create grant gold tables")
    parser.add_argument('--state', help='State code (e.g., MA, AL)', required=True)
    parser.add_argument('--gold-dir', default='data/gold', help='Gold directory')
    
    args = parser.parse_args()
    
    # Load nonprofit organizations for the state
    orgs_file = Path(args.gold_dir) / "states" / args.state / "nonprofits_organizations.parquet"
    
    if not orgs_file.exists():
        logger.error(f"Nonprofits file not found: {orgs_file}")
        logger.error("Run create_nonprofits_gold_tables.py first!")
        return
    
    nonprofits_df = pd.read_parquet(orgs_file)
    logger.info(f"Loaded {len(nonprofits_df):,} nonprofits from {args.state}")
    
    # Create grant tables
    creator = GrantsGoldTableCreator(
        gold_dir=args.gold_dir,
        state_code=args.state
    )
    
    creator.create_all_grant_tables(nonprofits_df)


if __name__ == "__main__":
    main()
