#!/usr/bin/env python3
"""
FEC Campaign Finance Integration Demo

Demonstrates how to use the FEC (Federal Election Commission) API integration
to track political contributions and campaign finance data.

Use Cases:
1. Track political donations from nonprofit leadership
2. Identify politically active individuals in advocacy organizations
3. Analyze campaign finance patterns in policy-related sectors
4. Map donor networks in healthcare and social services

Prerequisites:
1. Get a free FEC API key: https://api.data.gov/signup/
2. Set environment variable: export FEC_API_KEY="your_key_here"
3. Or use DEMO_KEY (limited to 30 requests/hour)

Usage:
    # Using DEMO_KEY (limited):
    python examples/demo_fec_integration.py --state MA
    
    # With your own API key:
    export FEC_API_KEY="your_key_here"
    python examples/demo_fec_integration.py --state MA --cycle 2024
    
    # Search for specific nonprofit donors:
    python examples/demo_fec_integration.py --state MA --employer "Community Health"
    
    # Create full gold tables:
    python examples/demo_fec_integration.py --state MA --create-gold-tables

API Documentation: https://api.open.fec.gov/developers/
"""

import sys
from pathlib import Path
import argparse
import os

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.discovery.fec_integration import OpenFECAPI
from pipeline.create_campaigns_gold_tables import CampaignsGoldTableCreator
from loguru import logger


def demo_search_candidates(api: OpenFECAPI, state: str, cycle: int = 2024):
    """Demo: Search for candidates in a state"""
    logger.info("=" * 60)
    logger.info(f"DEMO: Searching for {state} candidates in {cycle}")
    logger.info("=" * 60)
    
    for office, office_name in [('H', 'House'), ('S', 'Senate')]:
        logger.info(f"\n{office_name} Candidates:")
        
        result = api.search_candidates(
            state=state,
            office=office,
            cycle=cycle,
            per_page=10
        )
        
        candidates = result.get('results', [])
        
        for candidate in candidates:
            logger.info(f"  • {candidate.get('name')} ({candidate.get('party')})")
            logger.info(f"    District: {candidate.get('district') or 'N/A'}")
            logger.info(f"    ID: {candidate.get('candidate_id')}")


def demo_search_contributions(
    api: OpenFECAPI,
    state: str,
    employer: str = None,
    min_amount: float = 1000.0
):
    """Demo: Search for individual contributions"""
    logger.info("=" * 60)
    logger.info(f"DEMO: Searching for contributions from {state}")
    if employer:
        logger.info(f"  Employer filter: {employer}")
    logger.info(f"  Min amount: ${min_amount}")
    logger.info("=" * 60)
    
    result = api.search_individual_contributions(
        contributor_state=state,
        contributor_employer=employer,
        min_amount=min_amount,
        per_page=10
    )
    
    contributions = result.get('results', [])
    pagination = result.get('pagination', {})
    
    logger.info(f"\nFound {pagination.get('count', 0):,} total contributions")
    logger.info(f"Showing first {len(contributions)} records:\n")
    
    for contrib in contributions:
        logger.info(f"  • {contrib.get('contributor_name')}")
        logger.info(f"    Employer: {contrib.get('contributor_employer')}")
        logger.info(f"    Occupation: {contrib.get('contributor_occupation')}")
        logger.info(f"    Amount: ${contrib.get('contribution_receipt_amount'):,.2f}")
        logger.info(f"    Date: {contrib.get('contribution_receipt_date')}")
        logger.info(f"    Recipient: {contrib.get('committee_name')}")
        logger.info("")


def demo_search_committees(api: OpenFECAPI, state: str):
    """Demo: Search for PACs and committees"""
    logger.info("=" * 60)
    logger.info(f"DEMO: Searching for committees in {state}")
    logger.info("=" * 60)
    
    result = api.search_committees(
        state=state,
        per_page=10
    )
    
    committees = result.get('results', [])
    
    logger.info(f"\nFound {len(committees)} committees:\n")
    
    for committee in committees:
        logger.info(f"  • {committee.get('name')}")
        logger.info(f"    Type: {committee.get('committee_type_full')}")
        logger.info(f"    Party: {committee.get('party') or 'N/A'}")
        logger.info(f"    ID: {committee.get('committee_id')}")
        logger.info("")


def demo_nonprofit_donor_tracking(api: OpenFECAPI, state: str):
    """
    Demo: Track political contributions from nonprofit sector
    
    This is the KEY use case for civic engagement platform:
    - Identify nonprofit leaders who are politically active
    - Track donor networks in advocacy organizations
    - Analyze political influence on grant decisions
    """
    logger.info("=" * 60)
    logger.info(f"DEMO: Tracking nonprofit leadership donations in {state}")
    logger.info("=" * 60)
    
    # Common nonprofit employer keywords
    nonprofit_keywords = [
        "Foundation",
        "Community Health",
        "Association",
        "Council",
        "Alliance",
        "Institute",
    ]
    
    logger.info("\nSearching for contributions from nonprofit employees...\n")
    
    all_contributions = []
    
    for keyword in nonprofit_keywords[:3]:  # Limit for demo
        logger.info(f"Searching employer: {keyword}")
        
        try:
            result = api.search_individual_contributions(
                contributor_state=state,
                contributor_employer=keyword,
                min_amount=200.0,  # FEC reporting threshold
                per_page=5
            )
            
            contributions = result.get('results', [])
            all_contributions.extend(contributions)
            
            logger.info(f"  Found {len(contributions)} contributions")
            
        except Exception as e:
            logger.warning(f"  Error: {e}")
    
    if all_contributions:
        logger.info(f"\n📊 SUMMARY:")
        logger.info(f"Total contributions found: {len(all_contributions)}")
        
        # Calculate totals
        total_amount = sum(
            contrib.get('contribution_receipt_amount', 0)
            for contrib in all_contributions
        )
        
        logger.info(f"Total amount: ${total_amount:,.2f}")
        logger.info(f"\nTop donors:")
        
        for contrib in all_contributions[:5]:
            logger.info(f"  • {contrib.get('contributor_name')}")
            logger.info(f"    {contrib.get('contributor_employer')}")
            logger.info(f"    ${contrib.get('contribution_receipt_amount'):,.2f} → {contrib.get('committee_name')}")
            logger.info("")


def demo_create_gold_tables(state: str, cycle: int = 2024):
    """Demo: Create full campaign finance gold tables"""
    logger.info("=" * 60)
    logger.info(f"DEMO: Creating campaign finance gold tables for {state}")
    logger.info("=" * 60)
    
    creator = CampaignsGoldTableCreator(
        state_code=state,
        api_key=os.getenv('FEC_API_KEY')
    )
    
    creator.create_all_campaigns_tables(
        cycle=cycle,
        min_contribution_amount=200.0,
        max_contributions=1000  # Limit for demo
    )


def main():
    """Main demo function"""
    parser = argparse.ArgumentParser(
        description="FEC Campaign Finance Integration Demo"
    )
    parser.add_argument(
        "--state",
        default="MA",
        help="Two-letter state code (default: MA)"
    )
    parser.add_argument(
        "--cycle",
        type=int,
        default=2024,
        help="Election cycle year (default: 2024)"
    )
    parser.add_argument(
        "--employer",
        help="Search for contributions from specific employer"
    )
    parser.add_argument(
        "--create-gold-tables",
        action="store_true",
        help="Create full campaign finance gold tables"
    )
    
    args = parser.parse_args()
    
    # Validate state
    state = args.state.upper()
    if len(state) != 2:
        logger.error("State must be 2-letter code (e.g., MA, AL, GA)")
        return
    
    # Initialize FEC API
    api_key = os.getenv('FEC_API_KEY', 'DEMO_KEY')
    
    if api_key == 'DEMO_KEY':
        logger.warning("Using DEMO_KEY (limited to 30 requests/hour)")
        logger.warning("Get your free API key: https://api.data.gov/signup/")
        logger.warning("Then: export FEC_API_KEY='your_key_here'\n")
    
    api = OpenFECAPI(api_key=api_key)
    
    # Run demos
    if args.create_gold_tables:
        demo_create_gold_tables(state, args.cycle)
    else:
        # Run quick API demos
        demo_search_candidates(api, state, args.cycle)
        
        print("\n" + "=" * 60 + "\n")
        
        demo_search_committees(api, state)
        
        print("\n" + "=" * 60 + "\n")
        
        if args.employer:
            demo_search_contributions(api, state, employer=args.employer)
        else:
            demo_nonprofit_donor_tracking(api, state)
    
    logger.success("\n✅ Demo complete!")
    logger.info("\nNext steps:")
    logger.info("  1. Get FEC API key: https://api.data.gov/signup/")
    logger.info("  2. Create gold tables: python examples/demo_fec_integration.py --state MA --create-gold-tables")
    logger.info("  3. Run pipeline: python pipeline/create_campaigns_gold_tables.py --state MA")


if __name__ == "__main__":
    main()
