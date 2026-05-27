#!/usr/bin/env python3
"""
Migrate jurisdictions_details.parquet to use state_code + state naming convention

This script:
1. Reads the existing jurisdictions_details.parquet
2. Renames 'state' column to 'state_code' (2-letter code)
3. Adds 'state' column with full state name
4. Saves the updated parquet file
"""
import pandas as pd
from pathlib import Path

# State code to full name mapping
STATE_NAMES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
    'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
    'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
    'DC': 'District of Columbia', 'PR': 'Puerto Rico'
}

def migrate_jurisdictions_details():
    """Migrate jurisdictions_details.parquet to new naming convention."""
    
    file_path = Path('data/gold/jurisdictions_details.parquet')
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False
    
    print(f"📖 Reading {file_path}...")
    df = pd.read_parquet(file_path)
    print(f"   Rows: {len(df):,}")
    print(f"   Columns: {df.columns.tolist()}")
    
    # Check if already migrated
    if 'state_code' in df.columns and 'state' in df.columns:
        # Verify state has full names
        sample_state = df['state'].iloc[0]
        if len(str(sample_state)) > 2:
            print("✅ Already migrated - state_code and state columns exist with correct format")
            return True
    
    # Backup original file
    backup_path = file_path.parent / f"{file_path.stem}_backup{file_path.suffix}"
    print(f"💾 Creating backup: {backup_path.name}")
    df.to_parquet(backup_path)
    
    # Rename 'state' to 'state_code'
    if 'state' in df.columns and 'state_code' not in df.columns:
        print("🔄 Renaming 'state' → 'state_code'...")
        df = df.rename(columns={'state': 'state_code'})
    
    # Add 'state' column with full name
    if 'state' not in df.columns:
        print("➕ Adding 'state' column with full state names...")
        df['state'] = df['state_code'].map(STATE_NAMES)
        
        # Check for any unmapped states
        unmapped = df[df['state'].isna()]['state_code'].unique()
        if len(unmapped) > 0:
            print(f"   ⚠️  Warning: Unmapped state codes: {unmapped.tolist()}")
    
    # Reorder columns to have state_code and state together
    cols = df.columns.tolist()
    # Remove state_code and state from their current positions
    cols = [c for c in cols if c not in ['state_code', 'state']]
    # Insert them after jurisdiction_name
    name_idx = cols.index('jurisdiction_name')
    cols.insert(name_idx + 1, 'state_code')
    cols.insert(name_idx + 2, 'state')
    df = df[cols]
    
    # Save migrated file
    print(f"💾 Saving migrated file...")
    df.to_parquet(file_path)
    
    print("✅ Migration complete!")
    print(f"\n📊 Updated schema:")
    print(f"   Columns: {df.columns.tolist()}")
    print(f"\n🔍 Sample row:")
    sample = df.iloc[0]
    print(f"   Name: {sample['jurisdiction_name']}")
    print(f"   State Code: {sample['state_code']}")
    print(f"   State: {sample['state']}")
    
    return True


if __name__ == "__main__":
    migrate_jurisdictions_details()
