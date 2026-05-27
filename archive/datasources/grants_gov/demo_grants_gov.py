#!/usr/bin/env python3
"""
Example: Fetch oral health grants and match to Massachusetts nonprofits

This demonstrates the value of Grants.gov API integration by:
1. Fetching current federal oral health grant opportunities
2. Matching them to nonprofits in your database
3. Showing what new data you gain

Run:
    python examples/demo_grants_gov.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.discovery.grants_gov_integration import GrantsGovAPI, GrantMatcher
import pandas as pd
from loguru import logger


def demo_basic_search():
    """Demo 1: Basic search for oral health grants"""
    print("\n" + "="*80)
    print("DEMO 1: Search for Oral Health Grant Opportunities")
    print("="*80 + "\n")
    
    api = GrantsGovAPI()
    
    # Search for oral health grants
    results = api.search_opportunities(
        keyword="oral health",
        funding_categories="HL",  # Health
        agencies="HHS",           # Health & Human Services
        opp_statuses="forecasted|posted",
        rows=10
    )
    
    if results.get("errorcode") == 0:
        data = results.get("data", {})
        opportunities = data.get("oppHits", [])
        hit_count = data.get("hitCount", 0)
        
        print(f"✅ Found {hit_count:,} total oral health opportunities")
        print(f"📊 Showing first {len(opportunities)} results:\n")
        
        for i, opp in enumerate(opportunities, 1):
            print(f"{i}. {opp.get('opportunityTitle', 'N/A')}")
            print(f"   Agency: {opp.get('agencyName', 'N/A')}")
            print(f"   Status: {opp.get('opportunityStatus', 'N/A')}")
            print(f"   Number: {opp.get('opportunityNumber', 'N/A')}")
            print(f"   Posted: {opp.get('openDate', 'N/A')}")
            print()
    else:
        print(f"❌ API Error: {results.get('msg')}")
        
    return results


def demo_comprehensive_search():
    """Demo 2: Comprehensive oral health grant search"""
    print("\n" + "="*80)
    print("DEMO 2: Comprehensive Oral Health Grant Search")
    print("="*80 + "\n")
    
    api = GrantsGovAPI()
    matcher = GrantMatcher(api)
    
    # Find all oral health related grants
    print("🔍 Searching for grants matching:")
    print("   - oral health")
    print("   - dental")
    print("   - fluoridation")
    print("   - tooth decay")
    print("   - dental care")
    print("   - dental hygiene")
    print("   - dentistry")
    print()
    
    grants_df = matcher.find_oral_health_grants()
    
    if not grants_df.empty:
        print(f"\n✅ Found {len(grants_df):,} unique oral health grants\n")
        
        # Show breakdown by agency
        if 'agencyCode' in grants_df.columns:
            print("📊 Breakdown by Agency:")
            agency_counts = grants_df['agencyCode'].value_counts()
            for agency, count in agency_counts.items():
                print(f"   {agency}: {count:,} opportunities")
            print()
        
        # Show breakdown by status
        if 'opportunityStatus' in grants_df.columns:
            print("📊 Breakdown by Status:")
            status_counts = grants_df['opportunityStatus'].value_counts()
            for status, count in status_counts.items():
                print(f"   {status}: {count:,} opportunities")
            print()
        
        # Save results
        output_dir = Path("data/gold/grants")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "oral_health_opportunities.parquet"
        grants_df.to_parquet(output_file, index=False)
        print(f"💾 Saved to: {output_file}")
        
        return grants_df
    else:
        print("❌ No grants found")
        return pd.DataFrame()


def demo_match_to_state():
    """Demo 3: Match grants to Massachusetts nonprofits"""
    print("\n" + "="*80)
    print("DEMO 3: Match Grants to Massachusetts Nonprofits")
    print("="*80 + "\n")
    
    # Check if we have MA nonprofit data
    ma_nonprofits_file = Path("data/gold/states/MA/nonprofits_organizations.parquet")
    
    if not ma_nonprofits_file.exists():
        print(f"⚠️  Massachusetts nonprofit data not found at: {ma_nonprofits_file}")
        print("   Run this first to generate MA data:")
        print("   python -c \"from scripts.discovery.irs_bmf_ingestion import IRSBMFIngestion; bmf = IRSBMFIngestion(); ma_df = bmf.download_state_file('MA'); ma_df.to_parquet('data/gold/states/MA/nonprofits_organizations.parquet')\"")
        return
    
    # Load MA nonprofits
    nonprofits_df = pd.read_parquet(ma_nonprofits_file)
    print(f"📊 Loaded {len(nonprofits_df):,} Massachusetts nonprofits")
    
    # Filter to health-related orgs (NTEE code starting with E = Health)
    if 'NTEE_CD' in nonprofits_df.columns:
        health_orgs = nonprofits_df[nonprofits_df['NTEE_CD'].str.startswith('E', na=False)]
        print(f"   {len(health_orgs):,} are health-related organizations (NTEE code E*)")
    else:
        health_orgs = nonprofits_df
    
    # Get oral health grants
    grants_file = Path("data/gold/grants/oral_health_opportunities.parquet")
    
    if grants_file.exists():
        grants_df = pd.read_parquet(grants_file)
        print(f"\n📊 Loaded {len(grants_df):,} oral health grant opportunities")
    else:
        print("\n🔍 Fetching fresh grant data...")
        api = GrantsGovAPI()
        matcher = GrantMatcher(api)
        grants_df = matcher.find_oral_health_grants()
        
        if grants_df.empty:
            print("❌ No grants found")
            return
    
    # Match grants to state
    print(f"\n🔗 Matching {len(grants_df):,} grants to {len(health_orgs):,} MA health organizations...")
    
    api = GrantsGovAPI()
    matcher = GrantMatcher(api)
    matches = matcher.match_grants_to_state(
        state_code="MA",
        grants_df=grants_df,
        nonprofits_df=health_orgs
    )
    
    if not matches.empty:
        print(f"\n✅ Generated {len(matches):,} grant opportunity matches")
        
        # Save results
        output_file = Path("data/gold/states/MA/available_grants.parquet")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        matches.to_parquet(output_file, index=False)
        print(f"💾 Saved to: {output_file}")
        
        # Show sample matches
        print("\n📋 Sample Matches (first 5):")
        for i, row in matches.head(5).iterrows():
            print(f"\n{i+1}. {row.get('opportunity_title', 'N/A')}")
            print(f"   Agency: {row.get('agency_name', 'N/A')}")
            print(f"   Status: {row.get('status', 'N/A')}")
            print(f"   Eligible MA Health Orgs: {row.get('eligible_nonprofit_count', 0):,}")
            print(f"   Close Date: {row.get('close_date', 'N/A')}")


def compare_data_sources():
    """Demo 4: Compare Grants.gov vs your existing IRS 990 data"""
    print("\n" + "="*80)
    print("DEMO 4: What's NEW? Grants.gov vs Your Existing Data")
    print("="*80 + "\n")
    
    print("📊 YOUR CURRENT DATA (IRS Form 990):")
    print("   ✅ PAST: Grants that nonprofits RECEIVED")
    print("      - Government grants (total amount)")
    print("      - Foundation grants (total amount)")
    print("      - Corporate donations")
    print("      - Revenue sources")
    print("   ✅ WHO: Which nonprofits got funding")
    print("   ✅ HOW MUCH: Dollar amounts received")
    print("   ❌ WHICH GRANTS: Specific program names (limited)")
    print("   ❌ OPPORTUNITIES: What grants are AVAILABLE (none)")
    print()
    
    print("🆕 NEW DATA FROM GRANTS.GOV:")
    print("   ✅ FUTURE: Grant opportunities AVAILABLE NOW")
    print("      - Specific program names and numbers")
    print("      - Detailed descriptions and purposes")
    print("      - Eligibility requirements")
    print("      - Application deadlines")
    print("      - Award amounts and ceilings")
    print("   ✅ WHICH GRANTS: Exact program details")
    print("   ✅ WHEN: Posting dates and deadlines")
    print("   ✅ WHO CAN APPLY: Eligibility criteria")
    print("   ✅ HOW MUCH: Award ranges and limits")
    print()
    
    print("💡 COMBINED VALUE:")
    print("   1. Alert nonprofits BEFORE deadlines")
    print("   2. Track: Opportunity → Application → Award → IRS 990 Report")
    print("   3. Analyze: Which MA orgs successfully get federal grants?")
    print("   4. Identify: Funding gaps and underutilized opportunities")
    print("   5. Dashboard: 'Available Grants for Your Organization'")
    print()
    
    # Show example
    print("📋 EXAMPLE USE CASE:")
    print()
    print("   Scenario: MA dental clinic wants federal funding")
    print()
    print("   FROM GRANTS.GOV (this integration):")
    print("   → 'HRSA Oral Health Workforce Grant'")
    print("   → Deadline: Dec 31, 2024")
    print("   → Award: $500k-$2M")
    print("   → Eligibility: Community health centers")
    print()
    print("   FROM YOUR IRS 990 DATA:")
    print("   → Similar MA clinics received avg $800k in government grants")
    print("   → 15 MA dental clinics got federal funding last year")
    print("   → Success rate: ~60% of applicants")
    print()
    print("   COMBINED INSIGHT:")
    print("   ✅ Send alert to eligible MA clinics")
    print("   ✅ Show them: 'Organizations like yours received $800k'")
    print("   ✅ Track application and award for future analysis")
    print()


def main():
    """Run all demos"""
    logger.remove()  # Remove default logger
    logger.add(sys.stderr, level="INFO")
    
    try:
        # Demo 1: Basic search
        demo_basic_search()
        
        # Demo 2: Comprehensive search
        demo_comprehensive_search()
        
        # Demo 3: Match to MA nonprofits
        demo_match_to_state()
        
        # Demo 4: Compare data sources
        compare_data_sources()
        
        print("\n" + "="*80)
        print("✅ DEMO COMPLETE!")
        print("="*80)
        print("\nNext Steps:")
        print("1. Review generated files in data/gold/grants/")
        print("2. Check data/gold/states/MA/available_grants.parquet")
        print("3. Integrate into your dashboard")
        print("4. Set up automated daily grant fetching")
        print("5. Build email alert system for nonprofits")
        print()
        
    except Exception as e:
        logger.exception(f"Demo failed: {e}")
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("- Check internet connection")
        print("- Verify Grants.gov API is accessible")
        print("- Check if you have MA nonprofit data")


if __name__ == "__main__":
    main()
