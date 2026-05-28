"""
FEC (Federal Election Commission) Data Integration

Track political contributions and their relationship to:
- Nonprofit leadership (board members, executives)
- Policy decisions and grant awards
- Oral health advocacy funding

Data Sources:
1. FEC Bulk Data: Individual contributions, committee finances
2. FEC API: Real-time contribution tracking
3. OpenFEC: RESTful API for contribution searches

Use Cases:
- Map donor networks in oral health advocacy
- Track political influence on grant awards
- Identify politically active nonprofit leaders
- Analyze campaign finance in healthcare policy

API Documentation: https://api.open.fec.gov/developers/
Bulk Data: https://www.fec.gov/data/browse-data/?tab=bulk-data
"""

import requests
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
from loguru import logger
import time
import zipfile
import io


class OpenFECAPI:
    """Client for OpenFEC API (easier than parsing bulk files)"""
    
    BASE_URL = "https://api.open.fec.gov/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenFEC API client
        
        Args:
            api_key: FEC API key (get from https://api.data.gov/signup/)
                    If None, uses 'DEMO_KEY' with lower rate limits
        
        Note:
            Get your free API key at: https://api.data.gov/signup/
            DEMO_KEY has strict rate limits (30 requests/hour)
        """
        self.api_key = api_key or "DEMO_KEY"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CommunityOne/1.0 (Civic Engagement Platform)'
        })
        
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make API request with rate limiting"""
        if params is None:
            params = {}
            
        params['api_key'] = self.api_key
        
        url = f"{self.BASE_URL}/{endpoint}"
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        # Rate limiting
        time.sleep(0.2)  # 5 requests/second max
        
        return response.json()
    
    def search_individual_contributions(
        self,
        contributor_name: Optional[str] = None,
        contributor_city: Optional[str] = None,
        contributor_state: Optional[str] = None,
        contributor_employer: Optional[str] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
        per_page: int = 100,
        page: int = 1
    ) -> Dict:
        """
        Search individual contributions
        
        Args:
            contributor_name: Contributor name (partial match)
            contributor_city: City
            contributor_state: Two-letter state code
            contributor_employer: Employer name (partial match)
            min_amount: Minimum contribution amount
            max_amount: Maximum contribution amount
            min_date: Start date (YYYY-MM-DD)
            max_date: End date (YYYY-MM-DD)
            per_page: Results per page (max 100)
            page: Page number
            
        Returns:
            API response with contribution records
            
        Example:
            >>> api = OpenFECAPI(api_key="your_key")
            >>> # Find contributions from nonprofit executives
            >>> results = api.search_individual_contributions(
            ...     contributor_employer="Community Health Center",
            ...     contributor_state="MA",
            ...     min_amount=1000
            ... )
        """
        params = {
            'per_page': per_page,
            'page': page
        }
        
        if contributor_name:
            params['contributor_name'] = contributor_name
        if contributor_city:
            params['contributor_city'] = contributor_city
        if contributor_state:
            params['contributor_state'] = contributor_state
        if contributor_employer:
            params['contributor_employer'] = contributor_employer
        if min_amount:
            params['min_amount'] = min_amount
        if max_amount:
            params['max_amount'] = max_amount
        if min_date:
            params['min_date'] = min_date
        if max_date:
            params['max_date'] = max_date
            
        logger.info(f"Searching FEC contributions: {params}")
        
        return self._make_request('schedules/schedule_a/', params)
    
    def get_candidate_info(self, candidate_id: str) -> Dict:
        """Get information about a specific candidate"""
        return self._make_request(f'candidate/{candidate_id}/')
    
    def search_candidates(
        self,
        name: Optional[str] = None,
        office: Optional[str] = None,  # 'H' (House), 'S' (Senate), 'P' (President)
        state: Optional[str] = None,
        district: Optional[str] = None,
        party: Optional[str] = None,  # 'DEM', 'REP', etc.
        cycle: Optional[int] = None,
        per_page: int = 100
    ) -> Dict:
        """
        Search for candidates
        
        Args:
            name: Candidate name (partial match)
            office: Office type (H, S, P)
            state: Two-letter state code
            district: Congressional district (for House)
            party: Party code (DEM, REP, etc.)
            cycle: Election cycle year
            per_page: Results per page
            
        Returns:
            API response with candidate records
        """
        params = {'per_page': per_page}
        
        if name:
            params['name'] = name
        if office:
            params['office'] = office
        if state:
            params['state'] = state
        if district:
            params['district'] = district
        if party:
            params['party'] = party
        if cycle:
            params['cycle'] = cycle
            
        return self._make_request('candidates/', params)
    
    def search_committees(
        self,
        name: Optional[str] = None,
        committee_type: Optional[str] = None,
        designation: Optional[str] = None,
        state: Optional[str] = None,
        per_page: int = 100
    ) -> Dict:
        """
        Search for committees
        
        Args:
            name: Committee name (partial match)
            committee_type: Type (P=Presidential, H=House, S=Senate, etc.)
            designation: Designation code
            state: Two-letter state code
            per_page: Results per page
            
        Returns:
            API response with committee records
        """
        params = {'per_page': per_page}
        
        if name:
            params['name'] = name
        if committee_type:
            params['committee_type'] = committee_type
        if designation:
            params['designation'] = designation
        if state:
            params['state'] = state
            
        return self._make_request('committees/', params)


class FECBulkDataLoader:
    """Load FEC bulk data files (for comprehensive historical analysis)"""
    
    BULK_DATA_URL = "https://www.fec.gov/files/bulk-downloads"
    
    def __init__(self, cache_dir: Path = Path("data/cache/fec")):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def download_individual_contributions(
        self,
        cycle: str = "2024",
        force: bool = False
    ) -> Path:
        """
        Download bulk individual contributions file
        
        Args:
            cycle: Election cycle (e.g., "2024", "2022")
            force: Force re-download even if cached
            
        Returns:
            Path to downloaded file
            
        Note:
            These files are LARGE (several GB). Consider using the API
            for smaller queries or state-specific data.
        """
        filename = f"indiv{cycle[-2:]}.zip"  # e.g., indiv24.zip
        cache_file = self.cache_dir / filename
        
        if cache_file.exists() and not force:
            logger.info(f"Using cached file: {cache_file}")
            return cache_file
            
        url = f"{self.BULK_DATA_URL}/{cycle}/{filename}"
        
        logger.info(f"Downloading {url} (this may take a while...)")
        logger.warning(f"File size is typically 1-5 GB!")
        
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with open(cache_file, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0 and downloaded % (10 * 1024 * 1024) == 0:  # Every 10MB
                    logger.info(f"Downloaded: {downloaded / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB")
        
        logger.info(f"Download complete: {cache_file}")
        return cache_file
    
    def parse_individual_contributions(
        self,
        zip_path: Path,
        state_filter: Optional[str] = None,
        employer_filter: Optional[str] = None,
        min_amount: Optional[float] = None
    ) -> pd.DataFrame:
        """
        Parse individual contributions from bulk file
        
        Args:
            zip_path: Path to bulk ZIP file
            state_filter: Filter to specific state (e.g., "MA")
            employer_filter: Filter by employer name (partial match)
            min_amount: Minimum contribution amount
            
        Returns:
            DataFrame with contribution records
            
        Note:
            This can be memory-intensive for full files. Consider filters.
        """
        logger.info(f"Parsing {zip_path}")
        
        with zipfile.ZipFile(zip_path, 'r') as z:
            # Find the main data file (usually .txt)
            txt_files = [f for f in z.namelist() if f.endswith('.txt')]
            
            if not txt_files:
                raise ValueError(f"No .txt file found in {zip_path}")
                
            data_file = txt_files[0]
            logger.info(f"Reading {data_file}")
            
            # FEC bulk files are pipe-delimited
            with z.open(data_file) as f:
                # Read in chunks to handle large files
                chunks = []
                
                for chunk in pd.read_csv(
                    f,
                    delimiter='|',
                    dtype=str,  # Read as strings first
                    chunksize=100000,
                    low_memory=False
                ):
                    # Apply filters during read to reduce memory
                    if state_filter:
                        chunk = chunk[chunk['STATE'] == state_filter]
                    
                    if employer_filter and 'EMPLOYER' in chunk.columns:
                        mask = chunk['EMPLOYER'].str.contains(
                            employer_filter,
                            case=False,
                            na=False
                        )
                        chunk = chunk[mask]
                    
                    if min_amount and 'TRANSACTION_AMT' in chunk.columns:
                        chunk['TRANSACTION_AMT'] = pd.to_numeric(
                            chunk['TRANSACTION_AMT'],
                            errors='coerce'
                        )
                        chunk = chunk[chunk['TRANSACTION_AMT'] >= min_amount]
                    
                    if len(chunk) > 0:
                        chunks.append(chunk)
                
                if chunks:
                    df = pd.concat(chunks, ignore_index=True)
                    logger.info(f"Parsed {len(df):,} records")
                    return df
                else:
                    logger.warning("No records matched filters")
                    return pd.DataFrame()


class PoliticalContributionMatcher:
    """Match FEC contributions to nonprofit leadership"""
    
    def __init__(self, fec_api: OpenFECAPI):
        self.api = fec_api
        
    def find_nonprofit_leadership_contributions(
        self,
        officers_df: pd.DataFrame,
        state_code: str,
        min_amount: float = 200.0,
        election_cycle: str = "2024"
    ) -> pd.DataFrame:
        """
        Find political contributions from nonprofit officers
        
        Args:
            officers_df: DataFrame with nonprofit officers (from IRS 990)
            state_code: State to search (e.g., "MA")
            min_amount: Minimum contribution to track
            election_cycle: Election cycle year
            
        Returns:
            DataFrame matching officers to their political contributions
        """
        logger.info(f"Searching for political contributions from {len(officers_df):,} officers")
        
        all_contributions = []
        
        # Group by person name to avoid duplicates
        if 'person_name' in officers_df.columns:
            unique_names = officers_df['person_name'].dropna().unique()
        else:
            logger.warning("No 'person_name' column found")
            return pd.DataFrame()
        
        for name in unique_names[:100]:  # Limit for demo - API rate limits
            logger.info(f"Searching: {name}")
            
            try:
                results = self.api.search_individual_contributions(
                    contributor_name=name,
                    contributor_state=state_code,
                    min_amount=min_amount,
                    min_date=f"{election_cycle}-01-01"
                )
                
                if results.get('results'):
                    for contrib in results['results']:
                        # Enrich with nonprofit context
                        officer_match = officers_df[
                            officers_df['person_name'] == name
                        ].iloc[0]
                        
                        all_contributions.append({
                            'contributor_name': contrib.get('contributor_name'),
                            'contributor_city': contrib.get('contributor_city'),
                            'contributor_state': contrib.get('contributor_state'),
                            'contributor_employer': contrib.get('contributor_employer'),
                            'contribution_amount': contrib.get('contribution_receipt_amount'),
                            'contribution_date': contrib.get('contribution_receipt_date'),
                            'committee_name': contrib.get('committee', {}).get('name'),
                            'candidate_name': contrib.get('candidate_name'),
                            # Nonprofit context
                            'nonprofit_ein': officer_match.get('ein'),
                            'nonprofit_name': officer_match.get('organization_name'),
                            'officer_title': officer_match.get('title'),
                            'officer_compensation': officer_match.get('compensation')
                        })
                        
            except Exception as e:
                logger.warning(f"Error searching {name}: {e}")
                continue
                
            time.sleep(1)  # Rate limiting
        
        if all_contributions:
            df = pd.DataFrame(all_contributions)
            logger.info(f"Found {len(df):,} contributions from nonprofit leadership")
            return df
        else:
            return pd.DataFrame()
    
    def analyze_political_influence(
        self,
        contributions_df: pd.DataFrame,
        grants_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Analyze potential political influence on grant awards
        
        Compare:
        - Which nonprofit leaders donated to campaigns
        - Which nonprofits received federal grants
        - Timeline: donation → grant award
        
        Args:
            contributions_df: Political contributions by nonprofit leaders
            grants_df: Federal grants received by nonprofits
            
        Returns:
            DataFrame with influence analysis
        """
        logger.info("Analyzing political influence patterns")
        
        # Merge contributions with grants by EIN
        merged = contributions_df.merge(
            grants_df,
            left_on='nonprofit_ein',
            right_on='ein',
            how='inner'
        )
        
        if merged.empty:
            logger.warning("No matches between contributions and grants")
            return pd.DataFrame()
        
        # Calculate time between donation and grant
        if 'contribution_date' in merged.columns and 'grant_date' in merged.columns:
            merged['contribution_date'] = pd.to_datetime(merged['contribution_date'])
            merged['grant_date'] = pd.to_datetime(merged['grant_date'])
            merged['days_donation_to_grant'] = (
                merged['grant_date'] - merged['contribution_date']
            ).dt.days
        
        # Aggregate by nonprofit
        summary = merged.groupby('nonprofit_ein').agg({
            'contribution_amount': 'sum',
            'grant_amount': 'sum',
            'contributor_name': 'count'
        }).reset_index()
        
        summary.columns = [
            'ein',
            'total_political_donations',
            'total_grants_received',
            'number_of_donors'
        ]
        
        logger.info(f"Analyzed {len(summary):,} nonprofits with both donations and grants")
        
        return summary


def main():
    """Example usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Query FEC political contribution data")
    parser.add_argument("--api-key", help="FEC API key (get from https://api.data.gov/signup/)")
    parser.add_argument("--contributor", help="Contributor name to search")
    parser.add_argument("--employer", help="Employer name to search")
    parser.add_argument("--state", help="State code (e.g., MA)")
    parser.add_argument("--min-amount", type=float, default=200, help="Minimum contribution amount")
    parser.add_argument("--output", type=Path, default=Path("data/gold/fec"), help="Output directory")
    
    args = parser.parse_args()
    
    # Initialize API
    api = OpenFECAPI(api_key=args.api_key)
    
    # Search contributions
    results = api.search_individual_contributions(
        contributor_name=args.contributor,
        contributor_employer=args.employer,
        contributor_state=args.state,
        min_amount=args.min_amount
    )
    
    if results.get('results'):
        df = pd.DataFrame(results['results'])
        
        print(f"\nFound {len(df):,} contributions")
        print(f"\nTotal amount: ${df['contribution_receipt_amount'].sum():,.2f}")
        
        # Save results
        args.output.mkdir(parents=True, exist_ok=True)
        output_file = args.output / "political_contributions.parquet"
        df.to_parquet(output_file, index=False)
        print(f"\nSaved to: {output_file}")
    else:
        print("No contributions found")


if __name__ == "__main__":
    main()
