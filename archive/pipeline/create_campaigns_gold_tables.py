"""
Create Campaigns Gold Tables from FEC Data

Extract campaign finance and political contribution data from FEC:
- Individual contributions to candidates and committees
- Candidate information (federal races)
- Committee information (PACs, Super PACs, etc.)
- Analysis of nonprofit leadership political giving

Gold Tables Created:
1. campaigns_candidates - Federal candidates (House, Senate, President)
2. campaigns_committees - PACs, party committees, campaign committees
3. campaigns_contributions - Individual contributions (filtered for relevance)
4. campaigns_nonprofit_donors - Nonprofit leadership political giving analysis

Data Sources:
- OpenFEC API (https://api.open.fec.gov/developers/)
- Individual Contributions (Schedule A)
- Candidate Master File
- Committee Master File

Use Cases:
- Track political influence on policy decisions
- Map donor networks in advocacy organizations
- Identify politically active nonprofit leaders
- Analyze campaign finance patterns in healthcare policy

Input:
- nonprofits_organizations.parquet (for employer matching)
- contacts_nonprofit_officers.parquet (for donor name matching)
- contacts_local_officials.parquet (for candidate matching at local level)
- FEC API data

Output:
- data/gold/states/{STATE}/campaigns_*.parquet
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime
from loguru import logger
import sys
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.discovery.fec_integration import OpenFECAPI


class CampaignsGoldTableCreator:
    """Extract FEC campaign finance data and create gold tables"""
    
    def __init__(
        self,
        gold_dir: str = "data/gold",
        state_code: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize campaigns gold table creator
        
        Args:
            gold_dir: Base gold directory path
            state_code: Two-letter state code (e.g., 'MA', 'AL')
            api_key: FEC API key (get from https://api.data.gov/signup/)
        """
        self.state_code = state_code
        
        # Use state-based directory structure if state_code provided
        if state_code:
            self.gold_dir = Path(gold_dir) / "states" / state_code
        else:
            self.gold_dir = Path(gold_dir)
        
        self.gold_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize FEC API client
        self.api_key = api_key or os.getenv('FEC_API_KEY', 'DEMO_KEY')
        self.fec_api = OpenFECAPI(api_key=self.api_key)
        
        logger.info(f"State Code: {state_code or 'ALL (national)'}")
        logger.info(f"Gold Dir: {self.gold_dir}")
        logger.info(f"FEC API Key: {'Custom' if api_key else 'DEMO_KEY'}")
    
    def load_nonprofit_organizations(self) -> Optional[pd.DataFrame]:
        """Load nonprofit organizations for employer matching"""
        org_file = self.gold_dir / "nonprofits_organizations.parquet"
        
        if org_file.exists():
            logger.info(f"Loading nonprofit organizations from {org_file}")
            df = pd.read_parquet(org_file)
            logger.info(f"  Loaded {len(df):,} organizations")
            return df
        else:
            logger.warning(f"Nonprofit organizations file not found: {org_file}")
            return None
    
    def load_nonprofit_officers(self) -> Optional[pd.DataFrame]:
        """Load nonprofit officers for donor name matching"""
        officer_file = self.gold_dir / "contacts_nonprofit_officers.parquet"
        
        if officer_file.exists():
            logger.info(f"Loading nonprofit officers from {officer_file}")
            df = pd.read_parquet(officer_file)
            logger.info(f"  Loaded {len(df):,} officers")
            return df
        else:
            logger.warning(f"Nonprofit officers file not found: {officer_file}")
            return None
    
    def create_campaigns_candidates(self, cycle: int = 2024) -> pd.DataFrame:
        """
        Create campaigns_candidates gold table
        
        Federal candidates running in the state
        
        Args:
            cycle: Election cycle year (e.g., 2024, 2022)
            
        Returns:
            DataFrame with candidate information
        """
        logger.info("=" * 60)
        logger.info(f"Creating campaigns_candidates table (cycle: {cycle})")
        logger.info("=" * 60)
        
        if not self.state_code:
            logger.warning("No state code specified. Skipping state-specific candidates.")
            return pd.DataFrame()
        
        candidate_data = []
        
        # Search for candidates in this state
        logger.info(f"Fetching candidates for {self.state_code} in {cycle}...")
        
        for office in ['H', 'S', 'P']:  # House, Senate, President
            try:
                result = self.fec_api.search_candidates(
                    state=self.state_code if office != 'P' else None,
                    office=office,
                    cycle=cycle,
                    per_page=100
                )
                
                candidates = result.get('results', [])
                logger.info(f"  Found {len(candidates)} {office} candidates")
                
                for candidate in candidates:
                    candidate_data.append({
                        'candidate_id': candidate.get('candidate_id'),
                        'candidate_name': candidate.get('name'),
                        'party': candidate.get('party'),
                        'office': candidate.get('office'),
                        'office_full': candidate.get('office_full'),
                        'state': candidate.get('state'),
                        'district': candidate.get('district'),
                        'election_year': candidate.get('election_years', [None])[0] if candidate.get('election_years') else None,
                        'incumbent_challenge': candidate.get('incumbent_challenge'),
                        'candidate_status': candidate.get('candidate_status'),
                        'cycle': cycle,
                    })
                
            except Exception as e:
                logger.error(f"Error fetching {office} candidates: {e}")
        
        candidate_df = pd.DataFrame(candidate_data)
        
        # Save to parquet
        output_path = self.gold_dir / "campaigns_candidates.parquet"
        candidate_df.to_parquet(output_path, index=False)
        logger.success(f"Created {output_path} with {len(candidate_df):,} records")
        
        return candidate_df
    
    def create_campaigns_committees(self, cycle: int = 2024) -> pd.DataFrame:
        """
        Create campaigns_committees gold table
        
        PACs, Super PACs, and campaign committees in the state
        
        Args:
            cycle: Election cycle year
            
        Returns:
            DataFrame with committee information
        """
        logger.info("=" * 60)
        logger.info(f"Creating campaigns_committees table (cycle: {cycle})")
        logger.info("=" * 60)
        
        if not self.state_code:
            logger.warning("No state code specified. Skipping state-specific committees.")
            return pd.DataFrame()
        
        committee_data = []
        
        # Search for committees in this state
        logger.info(f"Fetching committees for {self.state_code}...")
        
        try:
            result = self.fec_api.search_committees(
                state=self.state_code,
                per_page=100
            )
            
            committees = result.get('results', [])
            logger.info(f"  Found {len(committees)} committees")
            
            for committee in committees:
                committee_data.append({
                    'committee_id': committee.get('committee_id'),
                    'committee_name': committee.get('name'),
                    'committee_type': committee.get('committee_type'),
                    'committee_type_full': committee.get('committee_type_full'),
                    'designation': committee.get('designation'),
                    'designation_full': committee.get('designation_full'),
                    'party': committee.get('party'),
                    'state': committee.get('state'),
                    'treasurer_name': committee.get('treasurer_name'),
                    'organization_type': committee.get('organization_type'),
                    'filing_frequency': committee.get('filing_frequency'),
                })
            
        except Exception as e:
            logger.error(f"Error fetching committees: {e}")
        
        committee_df = pd.DataFrame(committee_data)
        
        # Save to parquet
        output_path = self.gold_dir / "campaigns_committees.parquet"
        committee_df.to_parquet(output_path, index=False)
        logger.success(f"Created {output_path} with {len(committee_df):,} records")
        
        return committee_df
    
    def create_campaigns_contributions(
        self,
        min_amount: float = 200.0,
        max_records: int = 10000,
        cycle: int = 2024
    ) -> pd.DataFrame:
        """
        Create campaigns_contributions gold table
        
        Individual contributions from state residents
        
        Args:
            min_amount: Minimum contribution amount (FEC requires $200+ reporting)
            max_records: Maximum number of records to fetch
            cycle: Election cycle year
            
        Returns:
            DataFrame with contribution records
        """
        logger.info("=" * 60)
        logger.info(f"Creating campaigns_contributions table (cycle: {cycle})")
        logger.info("=" * 60)
        
        if not self.state_code:
            logger.warning("No state code specified. Skipping state-specific contributions.")
            return pd.DataFrame()
        
        contribution_data = []
        
        # Search for contributions from this state
        logger.info(f"Fetching contributions from {self.state_code} (min ${min_amount})...")
        logger.info(f"  NOTE: This may take a while. Max records: {max_records}")
        
        # Calculate date range for cycle
        start_date = f"{cycle - 2}-01-01"
        end_date = f"{cycle}-12-31"
        
        try:
            # Paginate through results
            page = 1
            records_fetched = 0
            
            while records_fetched < max_records:
                result = self.fec_api.search_individual_contributions(
                    contributor_state=self.state_code,
                    min_amount=min_amount,
                    min_date=start_date,
                    max_date=end_date,
                    per_page=100,
                    page=page
                )
                
                contributions = result.get('results', [])
                
                if not contributions:
                    logger.info(f"  No more results at page {page}")
                    break
                
                for contribution in contributions:
                    contribution_data.append({
                        'contribution_id': f"{contribution.get('sub_id')}",
                        'contributor_name': contribution.get('contributor_name'),
                        'contributor_city': contribution.get('contributor_city'),
                        'contributor_state': contribution.get('contributor_state'),
                        'contributor_zip': contribution.get('contributor_zip'),
                        'contributor_employer': contribution.get('contributor_employer'),
                        'contributor_occupation': contribution.get('contributor_occupation'),
                        'contribution_amount': contribution.get('contribution_receipt_amount'),
                        'contribution_date': contribution.get('contribution_receipt_date'),
                        'recipient_committee_id': contribution.get('committee_id'),
                        'recipient_committee_name': contribution.get('committee_name'),
                        'candidate_id': contribution.get('candidate_id'),
                        'candidate_name': contribution.get('candidate_name'),
                        'election_type': contribution.get('election_type'),
                        'entity_type': contribution.get('entity_type'),
                        'memo_text': contribution.get('memo_text'),
                    })
                
                records_fetched += len(contributions)
                logger.info(f"  Page {page}: {len(contributions)} records (total: {records_fetched:,})")
                
                page += 1
                
                # Stop if we've hit max
                if records_fetched >= max_records:
                    logger.info(f"  Reached max records limit ({max_records:,})")
                    break
            
        except Exception as e:
            logger.error(f"Error fetching contributions: {e}")
        
        contribution_df = pd.DataFrame(contribution_data)
        
        # Save to parquet
        output_path = self.gold_dir / "campaigns_contributions.parquet"
        contribution_df.to_parquet(output_path, index=False)
        logger.success(f"Created {output_path} with {len(contribution_df):,} records")
        
        return contribution_df
    
    def create_campaigns_nonprofit_donors(
        self,
        contributions_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Create campaigns_nonprofit_donors analysis table
        
        Analyze political contributions from nonprofit leadership:
        - Officers, directors, trustees
        - Key employees
        - Match by employer name and individual name
        
        Args:
            contributions_df: DataFrame of contributions (if None, loads from file)
            
        Returns:
            DataFrame with nonprofit donor analysis
        """
        logger.info("=" * 60)
        logger.info("Creating campaigns_nonprofit_donors analysis table")
        logger.info("=" * 60)
        
        # Load contributions if not provided
        if contributions_df is None:
            contrib_file = self.gold_dir / "campaigns_contributions.parquet"
            if contrib_file.exists():
                contributions_df = pd.read_parquet(contrib_file)
            else:
                logger.error(f"Contributions file not found: {contrib_file}")
                return pd.DataFrame()
        
        if contributions_df.empty:
            logger.warning("No contributions data available")
            return pd.DataFrame()
        
        # Load nonprofit data
        nonprofit_orgs = self.load_nonprofit_organizations()
        nonprofit_officers = self.load_nonprofit_officers()
        
        donor_analysis = []
        
        # Strategy 1: Match by employer name
        if nonprofit_orgs is not None:
            logger.info("Matching contributions by nonprofit employer name...")
            
            # Create employer lookup (lowercase for matching)
            nonprofit_names = set(
                nonprofit_orgs['organization_name'].str.lower().dropna()
            )
            
            # Find contributions where employer matches nonprofit
            contributions_df['employer_lower'] = contributions_df['contributor_employer'].str.lower()
            
            for idx, contrib in contributions_df.iterrows():
                employer = contrib.get('employer_lower', '')
                
                if not employer or pd.isna(employer):
                    continue
                
                # Check if employer matches any nonprofit
                if employer in nonprofit_names:
                    # Find matching nonprofit(s)
                    matching_orgs = nonprofit_orgs[
                        nonprofit_orgs['organization_name'].str.lower() == employer
                    ]
                    
                    for _, org in matching_orgs.iterrows():
                        donor_analysis.append({
                            'ein': org.get('ein'),
                            'organization_name': org.get('organization_name'),
                            'contributor_name': contrib.get('contributor_name'),
                            'contributor_title': 'Employee',  # Inferred from employer field
                            'contribution_amount': contrib.get('contribution_amount'),
                            'contribution_date': contrib.get('contribution_date'),
                            'recipient_name': contrib.get('recipient_committee_name'),
                            'candidate_name': contrib.get('candidate_name'),
                            'match_method': 'Employer Name',
                        })
        
        # Strategy 2: Match by officer/director name
        if nonprofit_officers is not None:
            logger.info("Matching contributions by officer name...")
            
            # Create name lookup (lowercase for matching)
            officer_lookup = {}
            for _, officer in nonprofit_officers.iterrows():
                name_lower = str(officer.get('officer_name', '')).lower().strip()
                if name_lower:
                    if name_lower not in officer_lookup:
                        officer_lookup[name_lower] = []
                    officer_lookup[name_lower].append({
                        'ein': officer.get('ein'),
                        'organization_name': officer.get('organization_name'),
                        'title': officer.get('title'),
                    })
            
            # Match contributions
            contributions_df['contributor_name_lower'] = contributions_df['contributor_name'].str.lower()
            
            for idx, contrib in contributions_df.iterrows():
                name = contrib.get('contributor_name_lower', '')
                
                if not name or pd.isna(name):
                    continue
                
                # Check if contributor matches any officer
                if name in officer_lookup:
                    for officer_info in officer_lookup[name]:
                        donor_analysis.append({
                            'ein': officer_info['ein'],
                            'organization_name': officer_info['organization_name'],
                            'contributor_name': contrib.get('contributor_name'),
                            'contributor_title': officer_info['title'],
                            'contribution_amount': contrib.get('contribution_amount'),
                            'contribution_date': contrib.get('contribution_date'),
                            'recipient_name': contrib.get('recipient_committee_name'),
                            'candidate_name': contrib.get('candidate_name'),
                            'match_method': 'Officer Name Match',
                        })
        
        donor_df = pd.DataFrame(donor_analysis)
        
        # Remove duplicates (same person matched both ways)
        if not donor_df.empty:
            donor_df = donor_df.drop_duplicates(
                subset=['ein', 'contributor_name', 'contribution_date', 'contribution_amount'],
                keep='first'
            )
        
        # Save to parquet
        output_path = self.gold_dir / "campaigns_nonprofit_donors.parquet"
        donor_df.to_parquet(output_path, index=False)
        logger.success(f"Created {output_path} with {len(donor_df):,} records")
        
        return donor_df
    
    def create_all_campaigns_tables(
        self,
        cycle: int = 2024,
        min_contribution_amount: float = 200.0,
        max_contributions: int = 10000
    ):
        """
        Create all campaigns gold tables
        
        Args:
            cycle: Election cycle year (e.g., 2024, 2022)
            min_contribution_amount: Minimum contribution amount
            max_contributions: Maximum number of contributions to fetch
        """
        logger.info("=" * 60)
        logger.info("CAMPAIGN FINANCE GOLD TABLE CREATION")
        logger.info("=" * 60)
        logger.info(f"State: {self.state_code or 'ALL'}")
        logger.info(f"Cycle: {cycle}")
        logger.info(f"Min Contribution: ${min_contribution_amount}")
        logger.info(f"Max Records: {max_contributions:,}")
        logger.info("=" * 60)
        
        # Create each gold table
        candidates_df = self.create_campaigns_candidates(cycle=cycle)
        committees_df = self.create_campaigns_committees(cycle=cycle)
        contributions_df = self.create_campaigns_contributions(
            min_amount=min_contribution_amount,
            max_records=max_contributions,
            cycle=cycle
        )
        donor_analysis_df = self.create_campaigns_nonprofit_donors(
            contributions_df=contributions_df
        )
        
        logger.success("=" * 60)
        logger.success("ALL CAMPAIGN FINANCE GOLD TABLES CREATED!")
        logger.success("=" * 60)
        
        # Show summary
        gold_files = list(self.gold_dir.glob("campaigns_*.parquet"))
        logger.info(f"\nCreated {len(gold_files)} gold tables:")
        for file in sorted(gold_files):
            df_check = pd.read_parquet(file)
            size_mb = file.stat().st_size / (1024 * 1024)
            logger.info(f"  - {file.name}: {len(df_check):,} records ({size_mb:.2f} MB)")


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Create campaign finance gold tables from FEC data"
    )
    parser.add_argument(
        "--state",
        required=True,
        help="Two-letter state code (e.g., MA, AL, GA)"
    )
    parser.add_argument(
        "--cycle",
        type=int,
        default=2024,
        help="Election cycle year (default: 2024)"
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="FEC API key (or set FEC_API_KEY env var). Get from https://api.data.gov/signup/"
    )
    parser.add_argument(
        "--min-amount",
        type=float,
        default=200.0,
        help="Minimum contribution amount (default: $200)"
    )
    parser.add_argument(
        "--max-contributions",
        type=int,
        default=10000,
        help="Maximum contributions to fetch (default: 10,000)"
    )
    
    args = parser.parse_args()
    
    # Validate state code
    if len(args.state) != 2:
        logger.error("State code must be 2 letters (e.g., MA, AL, GA)")
        return
    
    state_code = args.state.upper()
    
    logger.info(f"Creating campaign finance gold tables for {state_code}")
    
    creator = CampaignsGoldTableCreator(
        state_code=state_code,
        api_key=args.api_key
    )
    
    creator.create_all_campaigns_tables(
        cycle=args.cycle,
        min_contribution_amount=args.min_amount,
        max_contributions=args.max_contributions
    )


if __name__ == "__main__":
    main()
