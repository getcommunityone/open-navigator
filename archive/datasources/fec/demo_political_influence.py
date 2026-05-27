#!/usr/bin/env python3
"""
Example: Political Influence Analysis

Demonstrates how FEC, Grants.gov, IRS 990, and Voter data combine to
reveal political connections in civic engagement and grant funding.

This shows the COMPLETE PICTURE:
1. Nonprofit leadership (IRS 990)
2. Political donations (FEC)
3. Grant opportunities & awards (Grants.gov + IRS 990)
4. Political context (Voter data, legislators)

Run:
    python examples/demo_political_influence.py --api-key YOUR_FEC_KEY
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.discovery.fec_integration import OpenFECAPI, PoliticalContributionMatcher
from scripts.discovery.voter_data_integration import PoliticalContextEnricher
from scripts.discovery.grants_gov_integration import GrantsGovAPI, GrantMatcher
import pandas as pd
from loguru import logger


def demo_fec_search(api_key: str):
    """Demo 1: Search FEC for political contributions"""
    print("\n" + "="*80)
    print("DEMO 1: Search FEC Political Contributions")
    print("="*80 + "\n")
    
    api = OpenFECAPI(api_key=api_key)
    
    # Search for health sector contributions in Massachusetts
    print("🔍 Searching for contributions from health sector in Massachusetts...")
    print("   Employer: health|dental|clinic")
    print("   State: MA")
    print("   Min Amount: $500")
    print()
    
    results = api.search_individual_contributions(
        contributor_employer="health",
        contributor_state="MA",
        min_amount=500,
        per_page=20
    )
    
    if results.get('results'):
        contributions = results['results']
        
        print(f"✅ Found {len(contributions)} contributions (showing first 10):\n")
        
        for i, contrib in enumerate(contributions[:10], 1):
            name = contrib.get('contributor_name', 'N/A')
            employer = contrib.get('contributor_employer', 'N/A')
            amount = contrib.get('contribution_receipt_amount', 0)
            committee = contrib.get('committee', {}).get('name', 'N/A')
            date = contrib.get('contribution_receipt_date', 'N/A')
            
            print(f"{i}. {name}")
            print(f"   Employer: {employer}")
            print(f"   Amount: ${amount:,.2f}")
            print(f"   To: {committee}")
            print(f"   Date: {date}")
            print()
        
        # Summary
        total_amount = sum(
            c.get('contribution_receipt_amount', 0) 
            for c in contributions
        )
        print(f"📊 Total from this sample: ${total_amount:,.2f}")
        
        return contributions
    else:
        print("❌ No contributions found")
        print("   (Try different search parameters or check API key)")
        return []


def demo_nonprofit_political_activity(api_key: str):
    """Demo 2: Match nonprofit officers to political contributions"""
    print("\n" + "="*80)
    print("DEMO 2: Nonprofit Leadership Political Activity")
    print("="*80 + "\n")
    
    # Check if we have officer data
    officers_file = Path("data/gold/states/MA/nonprofits_officers.parquet")
    
    if not officers_file.exists():
        print(f"⚠️  Nonprofit officer data not found: {officers_file}")
        print("   This would show which nonprofit executives/board members make political donations")
        print()
        print("Example output:")
        print("   Dr. Jane Smith, Executive Director, MA Dental Health Clinic")
        print("   → Donated $2,500 to Senator Warren (2024-03-15)")
        print("   → Donated $1,000 to Rep. Kennedy (2024-06-01)")
        print()
        print("   Total: $3,500 in political contributions")
        print("   Organization received: $500,000 federal grant (2024-09-01)")
        return
    
    officers_df = pd.read_parquet(officers_file)
    print(f"📊 Loaded {len(officers_df):,} nonprofit officers from Massachusetts")
    
    # Sample a few officers for demo
    sample_officers = officers_df.head(10)
    
    api = OpenFECAPI(api_key=api_key)
    matcher = PoliticalContributionMatcher(api)
    
    print("🔍 Searching for political contributions from these officers...")
    print("   (This may take a moment due to API rate limits)")
    print()
    
    # Find contributions
    contributions = matcher.find_nonprofit_leadership_contributions(
        officers_df=sample_officers,
        state_code="MA",
        min_amount=200,
        election_cycle="2024"
    )
    
    if not contributions.empty:
        print(f"✅ Found {len(contributions):,} political contributions\n")
        
        # Group by nonprofit
        by_org = contributions.groupby('nonprofit_name').agg({
            'contribution_amount': 'sum',
            'contributor_name': 'count'
        }).sort_values('contribution_amount', ascending=False)
        
        print("📊 Political Activity by Nonprofit:")
        for org_name, row in by_org.head(5).iterrows():
            total = row['contribution_amount']
            count = row['contributor_name']
            print(f"   {org_name}")
            print(f"   → {count} donations totaling ${total:,.2f}")
            print()
    else:
        print("❌ No matches found in this sample")
        print("   (Try with more officers or different search parameters)")


def demo_complete_influence_picture():
    """Demo 3: Complete political influence analysis"""
    print("\n" + "="*80)
    print("DEMO 3: Complete Political Influence Picture")
    print("="*80 + "\n")
    
    print("📊 DATA SOURCES INTEGRATED:\n")
    
    print("1️⃣  IRS FORM 990 (Your existing data)")
    print("   ✅ Nonprofit organizations")
    print("   ✅ Officer names, titles, compensation")
    print("   ✅ Revenue sources (government grants, foundations, donations)")
    print("   ✅ Program expenditures")
    print()
    
    print("2️⃣  FEC POLITICAL CONTRIBUTIONS (NEW)")
    print("   ✅ Individual donations to campaigns")
    print("   ✅ Contributor employer (links to nonprofits!)")
    print("   ✅ Donation amounts and dates")
    print("   ✅ Recipient candidates and committees")
    print()
    
    print("3️⃣  GRANTS.GOV API (NEW)")
    print("   ✅ Available federal grant opportunities")
    print("   ✅ Application deadlines")
    print("   ✅ Award amounts and eligibility")
    print("   ✅ Agency and program details")
    print()
    
    print("4️⃣  VOTER DATA (NEW)")
    print("   ✅ Jurisdiction party affiliation")
    print("   ✅ Elected official party membership")
    print("   ✅ Voter turnout patterns")
    print("   ✅ Political demographics")
    print()
    
    print("\n" + "="*80)
    print("💡 ANALYSIS YOU CAN DO:")
    print("="*80 + "\n")
    
    print("❓ Political Influence on Grant Awards")
    print("   Timeline: Nonprofit officer → Political donation → Federal grant")
    print()
    print("   Example:")
    print("   • 2024-03-15: Dr. Smith (Executive Director) donates $2,500 to Sen. Warren")
    print("   • 2024-06-01: Sen. Warren introduces oral health bill")
    print("   • 2024-09-01: Dr. Smith's nonprofit receives $500k HRSA grant")
    print()
    print("   Analysis: Correlation or causation? Context matters!")
    print()
    
    print("❓ Partisan Patterns in Oral Health Funding")
    print("   Compare: Democratic vs Republican jurisdictions")
    print()
    print("   Questions:")
    print("   • Do blue states get more federal oral health grants?")
    print("   • Does party affiliation affect fluoridation votes?")
    print("   • Political polarization of dental public health?")
    print()
    
    print("❓ Advocacy Network Mapping")
    print("   Track: Who donates to whom in health policy circles")
    print()
    print("   Network:")
    print("   • Oral health nonprofits → Common political donors")
    print("   • Dental PACs → Candidate recipients")
    print("   • Lobbying expenditures → Policy outcomes")
    print()
    
    print("❓ Transparency & Accountability")
    print("   Public disclosure of political-financial connections")
    print()
    print("   Dashboard features:")
    print("   • 'Political Connections' badge on nonprofit profiles")
    print("   • Grant award timeline visualization")
    print("   • Donor network graph")
    print("   • Jurisdiction political context")
    print()


def demo_data_availability():
    """Demo 4: Show what data is available"""
    print("\n" + "="*80)
    print("DEMO 4: Current Data Availability")
    print("="*80 + "\n")
    
    # Check what data exists
    print("📂 Checking your current data files...\n")
    
    data_checks = [
        ("IRS 990 Organizations", "data/gold/states/MA/nonprofits_organizations.parquet"),
        ("IRS 990 Officers", "data/gold/states/MA/nonprofits_officers.parquet"),
        ("Grant Revenue Sources", "data/gold/states/MA/grants_revenue_sources.parquet"),
        ("Federal Grant Opportunities", "data/gold/grants/oral_health_opportunities.parquet"),
        ("FEC Contributions", "data/gold/fec/political_contributions.parquet"),
    ]
    
    available = []
    missing = []
    
    for name, path in data_checks:
        file_path = Path(path)
        if file_path.exists():
            df = pd.read_parquet(file_path)
            size_mb = file_path.stat().st_size / (1024 * 1024)
            available.append((name, len(df), size_mb))
            print(f"✅ {name:<30} {len(df):>8,} rows ({size_mb:>6.1f} MB)")
        else:
            missing.append((name, path))
            print(f"⚠️  {name:<30} Not found")
    
    print()
    
    if available:
        print("📊 AVAILABLE DATA:")
        total_rows = sum(count for _, count, _ in available)
        total_mb = sum(size for _, _, size in available)
        print(f"   Total records: {total_rows:,}")
        print(f"   Total size: {total_mb:.1f} MB")
        print()
    
    if missing:
        print("❓ TO GENERATE MISSING DATA:")
        for name, path in missing:
            if "officers" in path:
                print(f"\n   {name}:")
                print(f"   python scripts/enrich_nonprofits_gt990.py \\")
                print(f"     --input data/gold/states/MA/nonprofits_organizations.parquet \\")
                print(f"     --output {path}")
            elif "grant_revenue" in path:
                print(f"\n   {name}:")
                print(f"   python pipeline/create_grants_gold_tables.py --state MA")
            elif "oral_health_opportunities" in path:
                print(f"\n   {name}:")
                print(f"   python examples/demo_grants_gov.py")
            elif "political_contributions" in path:
                print(f"\n   {name}:")
                print(f"   python examples/demo_political_influence.py --api-key YOUR_FEC_KEY")
        print()


def main():
    """Run all demos"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Demo: Political influence analysis with FEC data"
    )
    parser.add_argument(
        "--api-key",
        help="FEC API key (get free at https://api.data.gov/signup/). "
             "Use 'DEMO_KEY' for testing (limited to 30 requests/hour)"
    )
    
    args = parser.parse_args()
    
    logger.remove()  # Remove default logger
    logger.add(sys.stderr, level="WARNING")  # Only show warnings
    
    try:
        # Demo 1: Basic FEC search
        if args.api_key:
            demo_fec_search(args.api_key)
            demo_nonprofit_political_activity(args.api_key)
        else:
            print("\n" + "="*80)
            print("⚠️  FEC API KEY REQUIRED")
            print("="*80)
            print("\nGet your free API key:")
            print("1. Visit: https://api.data.gov/signup/")
            print("2. Enter your email")
            print("3. Receive key instantly")
            print("4. Run: python examples/demo_political_influence.py --api-key YOUR_KEY")
            print("\nOr use DEMO_KEY for testing:")
            print("   python examples/demo_political_influence.py --api-key DEMO_KEY")
            print("   (Limited to 30 requests/hour)")
            print()
        
        # Demo 3: Complete picture (doesn't require API key)
        demo_complete_influence_picture()
        
        # Demo 4: Data availability
        demo_data_availability()
        
        print("\n" + "="*80)
        print("✅ DEMO COMPLETE!")
        print("="*80)
        print("\nNext Steps:")
        print("1. Get FEC API key: https://api.data.gov/signup/")
        print("2. Generate missing data (see commands above)")
        print("3. Run full analysis with all data sources")
        print("4. Build 'Political Connections' dashboard feature")
        print("5. Set up transparency reporting")
        print()
        
    except Exception as e:
        logger.exception(f"Demo failed: {e}")
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
