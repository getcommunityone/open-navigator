#!/usr/bin/env python3
"""
Organize meetings and contacts data by state for HuggingFace.

Structure:
- data/gold/states/{STATE}/meetings.parquet
- data/gold/states/{STATE}/contacts_local_officials.parquet
- data/gold/states/{STATE}/contacts_meeting_attendance.parquet
"""

import shutil
from pathlib import Path

import pandas as pd
from loguru import logger


# State name to abbreviation mapping
STATE_ABBREV = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
    'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
    'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
    'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
    'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
    'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
    'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
    'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
    'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
    'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
    'Wisconsin': 'WI', 'Wyoming': 'WY',
    'District of Columbia': 'DC', 'Puerto Rico': 'PR'
}


def load_all_meetings() -> pd.DataFrame:
    """Load and consolidate all meeting data from cache."""
    logger.info("📂 Loading all meeting data from cache...")
    
    cache_dir = Path("data/cache/localview")
    meeting_files = sorted(cache_dir.glob("meetings.*.parquet"))
    
    if not meeting_files:
        logger.error(f"No meeting files found in {cache_dir}")
        return pd.DataFrame()
    
    logger.info(f"   Found {len(meeting_files)} year files (2006-2023)")
    
    dfs = []
    total_rows = 0
    
    for file in meeting_files:
        year = file.stem.split('.')[1]
        df = pd.read_parquet(file)
        dfs.append(df)
        total_rows += len(df)
        logger.info(f"   {year}: {len(df):,} meetings")
    
    combined_df = pd.concat(dfs, ignore_index=True)
    logger.success(f"   ✅ Loaded {total_rows:,} total meetings")
    
    return combined_df


def add_state_code(df: pd.DataFrame) -> pd.DataFrame:
    """Add state abbreviation column."""
    logger.info("🗺️  Mapping state names to abbreviations...")
    
    if 'state_name' not in df.columns:
        logger.error("No 'state_name' column found!")
        return df
    
    df['state'] = df['state_name'].map(STATE_ABBREV)
    
    # Check for unmapped states
    unmapped = df[df['state'].isna()]['state_name'].unique()
    if len(unmapped) > 0:
        logger.warning(f"   ⚠️  Unmapped states: {unmapped}")
    
    # Drop rows with no state mapping
    before = len(df)
    df = df.dropna(subset=['state'])
    after = len(df)
    
    if before > after:
        logger.warning(f"   Dropped {before - after:,} rows with unmapped states")
    
    logger.success(f"   ✅ Mapped {len(df):,} meetings to state codes")
    return df


def split_meetings_by_state(df: pd.DataFrame, output_dir: Path):
    """Split meetings into state directories."""
    logger.info("\n📊 Splitting meetings by state...")
    
    states = sorted(df['state'].unique())
    logger.info(f"   Found {len(states)} states with meeting data")
    
    total_size = 0
    state_counts = {}
    
    for state in states:
        state_df = df[df['state'] == state]
        
        # Create state directory
        state_dir = output_dir / state
        state_dir.mkdir(parents=True, exist_ok=True)
        
        # Save meetings
        output_file = state_dir / "meetings.parquet"
        state_df.to_parquet(output_file, index=False, compression='snappy')
        
        size = output_file.stat().st_size
        total_size += size
        state_counts[state] = len(state_df)
        
        logger.info(f"   ✅ {state}: {len(state_df):,} meetings → {output_file.relative_to(output_dir.parent)} ({size / 1024 / 1024:.1f} MB)")
    
    logger.success(f"   📦 Total: {len(states)} states, {total_size / 1024 / 1024:.1f} MB")
    
    return state_counts


def create_national_meetings(df: pd.DataFrame, output_dir: Path):
    """Create consolidated national meetings file."""
    logger.info("\n🌎 Creating national meetings file...")
    
    national_dir = output_dir / "national"
    national_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = national_dir / "meetings.parquet"
    df.to_parquet(output_file, index=False, compression='snappy')
    
    size = output_file.stat().st_size
    logger.success(f"   ✅ Created {output_file.relative_to(output_dir.parent)} ({size / 1024 / 1024:.1f} MB)")
    logger.info(f"      {len(df):,} total meetings from {len(df['state'].unique())} states")


def update_readmes(output_dir: Path, state_counts: dict):
    """Update README files with meetings information."""
    logger.info("\n📝 Updating README files...")
    
    # Update national README
    national_readme = output_dir / "national" / "README.md"
    if national_readme.exists():
        content = national_readme.read_text()
        
        # Add meetings section if not present
        if "meetings.parquet" not in content:
            addition = """
## Meetings Data

- **meetings.parquet** - 153K+ government meeting transcripts (2006-2023)
  - City council meetings, county board meetings, etc.
  - Columns: state, jurisdiction, meeting_date, transcript, demographics, etc.
  - Source: LocalView project
"""
            # Insert before the Example section
            if "## Example" in content:
                content = content.replace("## Example", addition + "\n## Example")
            else:
                content += addition
            
            national_readme.write_text(content)
            logger.success(f"   ✅ Updated {national_readme.relative_to(output_dir.parent)}")
    
    # Update states README
    states_readme = output_dir / "states" / "README.md"
    if states_readme.exists():
        content = states_readme.read_text()
        
        # Add meetings to structure if not present
        if "meetings.parquet" not in content:
            # Find the structure section and add meetings
            content = content.replace(
                "│   └── nonprofits_programs.parquet",
                """│   ├── nonprofits_programs.parquet
│   └── meetings.parquet"""
            )
            
            # Add to datasets section
            datasets_addition = """
5. **meetings.parquet** - Government meeting transcripts (where available)
"""
            if "## 📊 Datasets" in content:
                content = content.replace(
                    "4. **nonprofits_programs.parquet**",
                    "4. **nonprofits_programs.parquet**" + datasets_addition
                )
            
            states_readme.write_text(content)
            logger.success(f"   ✅ Updated {states_readme.relative_to(output_dir.parent)}")
    
    # Create meetings-specific README
    meetings_readme = output_dir / "states" / "MEETINGS_README.md"
    
    # Build state coverage table
    top_states = sorted(state_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    state_table = "\n".join([f"| {state} | {count:,} |" for state, count in top_states])
    
    meetings_readme.write_text(f"""# Government Meetings Data by State

Local government meeting transcripts from the LocalView project (2006-2023).

## Coverage

**Total:** 153,000+ meetings across {len(state_counts)} states

**Top 20 States by Meeting Count:**

| State | Meetings |
|-------|----------|
{state_table}

## Data Structure

Each state directory contains:
- `meetings.parquet` - Meeting transcripts for that state

## Columns

- **state** - State abbreviation
- **state_name** - Full state name  
- **place_name** - City/jurisdiction name
- **meeting_date** - Date of meeting
- **caption_text** - Full meeting transcript
- **channel_title** - Government channel (e.g., "City Council")
- **vid_upload_date** - When video was uploaded
- **Demographics** - Census data (acs_18_* columns)
- And more...

## Usage Examples

### Load meetings for a single state

```python
import pandas as pd

# California meetings
ca_meetings = pd.read_parquet('states/CA/meetings.parquet')
print(f"California meetings: {{len(ca_meetings):,}}")
print(f"Jurisdictions: {{ca_meetings['place_name'].nunique()}}")
```

### Search across multiple states

```python
import pandas as pd
import glob

# Load West Coast meetings
states = ['CA', 'OR', 'WA']
dfs = [pd.read_parquet(f'states/{{s}}/meetings.parquet') for s in states]
west_coast = pd.concat(dfs)

# Search for topic
dental_meetings = west_coast[
    west_coast['caption_text'].str.contains('dental|oral health', case=False, na=False)
]
print(f"Found {{len(dental_meetings)}} meetings mentioning oral health")
```

### Load national dataset

```python
import pandas as pd

# All meetings in one file
all_meetings = pd.read_parquet('national/meetings.parquet')
print(f"Total meetings: {{len(all_meetings):,}}")
print(f"Date range: {{all_meetings['meeting_date'].min()}} to {{all_meetings['meeting_date'].max()}}")
```

## Data Source

LocalView project - automated scraping of government meeting videos and transcripts from municipal YouTube channels.

**Years:** 2006-2023  
**Coverage:** 153K+ meetings  
**States:** {len(state_counts)} states with data

## Notes

- Not all states have equal coverage (depends on jurisdictions publishing to YouTube)
- Transcript quality varies by jurisdiction's captioning practices
- Some meetings may have incomplete transcripts
- Demographics linked via Census tract data
""")
    logger.success(f"   ✅ Created {meetings_readme.relative_to(output_dir.parent)}")


def main():
    """Main execution."""
    logger.info("=" * 70)
    logger.info("🚀 Organizing meetings data by state for HuggingFace")
    logger.info("=" * 70)
    
    output_dir = Path("data/gold")
    
    # Load all meetings
    df = load_all_meetings()
    
    if df.empty:
        logger.error("No meeting data found. Exiting.")
        return
    
    # Add state codes
    df = add_state_code(df)
    
    # Split by state
    state_counts = split_meetings_by_state(df, output_dir / "states")
    
    # Create national file
    create_national_meetings(df, output_dir)
    
    # Update READMEs
    update_readmes(output_dir, state_counts)
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.success("✅ COMPLETE: Meetings data organized by state")
    logger.info("=" * 70)
    logger.info(f"\n📁 Structure:")
    logger.info(f"   data/gold/national/meetings.parquet - All {len(df):,} meetings")
    logger.info(f"   data/gold/states/{{STATE}}/meetings.parquet - State-specific")
    logger.info(f"\n📊 Coverage: {len(state_counts)} states")
    logger.info(f"   Top states: {', '.join(sorted(state_counts.keys())[:10])}")


if __name__ == "__main__":
    main()
