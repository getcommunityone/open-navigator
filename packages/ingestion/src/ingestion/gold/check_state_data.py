#!/usr/bin/env python3
"""
Compare data completeness between states

Shows what data is missing and what needs to be enriched.
"""

import pandas as pd
from pathlib import Path
from loguru import logger


def analyze_state_data(state_code: str):
    """Analyze data completeness for a state"""
    
    state_dir = Path(f"data/gold/states/{state_code}")
    
    if not state_dir.exists():
        logger.error(f"❌ State directory not found: {state_dir}")
        return
    
    print(f"\n{'='*80}")
    print(f"📊 STATE: {state_code}")
    print(f"{'='*80}\n")
    
    # Check nonprofit organizations file
    org_file = state_dir / "nonprofits_organizations.parquet"
    if org_file.exists():
        df = pd.read_parquet(org_file)
        print(f"🏢 NONPROFITS: {len(df):,} organizations")
        
        # Check for contact fields
        contact_fields = [c for c in df.columns if any(x in c.lower() 
            for x in ['officer', 'phone', 'email', 'contact', 'address', 'street'])]
        
        if contact_fields:
            print(f"   ✅ Contact fields: {len(contact_fields)}")
            for field in contact_fields[:10]:  # Show first 10
                non_null = df[field].notna().sum()
                pct = (non_null / len(df)) * 100
                print(f"      - {field}: {non_null:,} ({pct:.1f}%)")
        else:
            print(f"   ❌ No contact fields found")
            print(f"   💡 Run: scripts/enrich_nonprofits_gt990.py")
        
        # Check for grant/financial fields
        grant_fields = [c for c in df.columns if 'grant' in c.lower()]
        if grant_fields:
            print(f"\n   💰 Grant fields: {len(grant_fields)}")
        else:
            print(f"\n   ❌ No grant fields in organizations file")
    else:
        print(f"❌ Nonprofits file not found: {org_file}")
    
    # Check grant tables
    print(f"\n💸 GRANT TABLES:")
    grant_files = [
        "grants_foundation_giving.parquet",
        "grants_nonprofit_to_nonprofit.parquet",
        "grants_revenue_sources.parquet"
    ]
    
    for filename in grant_files:
        filepath = state_dir / filename
        if filepath.exists():
            df = pd.read_parquet(filepath)
            status = "✅" if len(df) > 0 else "⚠️  EMPTY"
            print(f"   {status} {filename}: {len(df):,} rows")
        else:
            print(f"   ❌ {filename}: NOT FOUND")
    
    # Check other data files
    print(f"\n📋 OTHER DATA:")
    other_files = [
        "nonprofits_financials.parquet",
        "nonprofits_programs.parquet",
        "nonprofits_locations.parquet",
        "contacts_local_officials.parquet",
        "meetings.parquet"
    ]
    
    for filename in other_files:
        filepath = state_dir / filename
        if filepath.exists():
            df = pd.read_parquet(filepath)
            status = "✅" if len(df) > 0 else "⚠️  EMPTY"
            file_size = filepath.stat().st_size / 1024 / 1024  # MB
            print(f"   {status} {filename}: {len(df):,} rows ({file_size:.1f} MB)")
        else:
            print(f"   ❌ {filename}: NOT FOUND")


def compare_states():
    """Compare data across multiple states"""
    
    states = ['MA', 'AL', 'CA', 'NY', 'TX']  # Sample states
    
    print("\n" + "="*80)
    print("🗺️  STATE DATA COMPARISON")
    print("="*80)
    
    for state in states:
        state_dir = Path(f"data/gold/states/{state}")
        if state_dir.exists():
            analyze_state_data(state)
    
    print("\n" + "="*80)
    print("📌 RECOMMENDATIONS")
    print("="*80)
    print("""
1. To add contact information:
   ./enrich_alabama_nonprofits.sh
   
2. To add grant data (requires BigQuery setup):
   source .venv/bin/activate
   export GOOGLE_APPLICATION_CREDENTIALS=~/.gcp/bigquery-credentials.json
   python scripts/enrich_nonprofits_bigquery.py --state AL
   
3. To regenerate from IRS BMF:
   python -c "from scripts.discovery.irs_bmf_ingestion import IRSBMFIngestion; \\
              bmf = IRSBMFIngestion(); \\
              df = bmf.download_state_file('AL'); \\
              df.to_parquet('data/gold/states/AL/nonprofits_organizations.parquet')"
""")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Analyze specific state
        state_code = sys.argv[1].upper()
        analyze_state_data(state_code)
    else:
        # Compare all states
        compare_states()
