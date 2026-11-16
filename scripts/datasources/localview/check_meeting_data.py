#!/usr/bin/env python3
"""
Check Current Meeting Data Status for Priority States

Analyzes what meeting data exists and what needs to be loaded/scraped.

Usage:
    python scripts/datasources/localview/check_meeting_data.py
    python scripts/datasources/localview/check_meeting_data.py --states AL,GA,IN,MA,MT,WA,WI
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from loguru import logger

try:
    import polars as pl
    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    logger.warning("polars not available - install with: pip install polars")

# Priority states for development
PRIORITY_STATES = ['AL', 'GA', 'IN', 'MA', 'WA', 'WI']


def check_openstates_events(states: List[str]) -> Dict[str, Dict]:
    """Check OpenStates legislative events (committee hearings, etc.)"""
    logger.info("📋 Checking OpenStates Legislative Events...")

    results = {}
    gold_dir = Path("data/gold/states")

    for state in states:
        state_dir = gold_dir / state
        events_file = state_dir / "events_events.parquet"
        participants_file = state_dir / "events_participants.parquet"

        state_data = {
            "has_events": events_file.exists(),
            "has_participants": participants_file.exists(),
            "event_count": 0,
            "participant_count": 0,
            "date_range": None,
        }

        if POLARS_AVAILABLE and events_file.exists():
            try:
                df = pl.read_parquet(events_file)
                state_data["event_count"] = len(df)

                if "start_date" in df.columns:
                    dates = df["start_date"].drop_nulls()
                    if len(dates) > 0:
                        state_data["date_range"] = f"{dates.min()} to {dates.max()}"

            except Exception as e:
                logger.warning(f"Could not read {events_file}: {e}")

        if POLARS_AVAILABLE and participants_file.exists():
            try:
                df = pl.read_parquet(participants_file)
                state_data["participant_count"] = len(df)
            except Exception as e:
                logger.warning(f"Could not read {participants_file}: {e}")

        results[state] = state_data

    # Print summary
    print("\n" + "=" * 70)
    print("📋 OPENSTATES LEGISLATIVE EVENTS (Committee Hearings, Sessions)")
    print("=" * 70)

    for state, data in results.items():
        print(f"\n{state}:")
        if data["has_events"]:
            print(f"  ✅ Events: {data['event_count']:,}")
            print(f"  ✅ Participants: {data['participant_count']:,}")
            if data["date_range"]:
                print(f"  📅 Date Range: {data['date_range']}")
        else:
            print("  ❌ No event data found")

    return results


def check_localview_meetings(states: List[str]) -> Dict[str, Dict]:
    """Check LocalView municipal meetings (city council, county boards)"""
    logger.info("🏛️ Checking LocalView Municipal Meetings...")

    results = {}
    gold_dir = Path("data/gold/states")
    meetings_global = Path("data/gold/meetings/meetings_transcripts.parquet")

    # Check state-specific files
    for state in states:
        state_dir = gold_dir / state
        meetings_file = state_dir / "meetings_local.parquet"

        state_data = {
            "has_meetings": meetings_file.exists(),
            "meeting_count": 0,
            "date_range": None,
        }

        if POLARS_AVAILABLE and meetings_file.exists():
            try:
                df = pl.read_parquet(meetings_file)
                state_data["meeting_count"] = len(df)

                if "meeting_date" in df.columns:
                    dates = df["meeting_date"].drop_nulls()
                    if len(dates) > 0:
                        state_data["date_range"] = f"{dates.min()} to {dates.max()}"
            except Exception as e:
                logger.warning(f"Could not read {meetings_file}: {e}")

        results[state] = state_data

    # Check global meetings file
    global_exists = meetings_global.exists()
    global_count = 0
    global_range = None

    if POLARS_AVAILABLE and global_exists:
        try:
            df = pl.read_parquet(meetings_global)
            global_count = len(df)

            if "meeting_date" in df.columns:
                dates = df["meeting_date"].drop_nulls()
                if len(dates) > 0:
                    global_range = f"{dates.min()} to {dates.max()}"

            # Count by state (pl.len() works across Polars 0.20+ and 1.x)
            if "state" in df.columns:
                count_expr = pl.len().alias("count") if hasattr(pl, "len") else pl.count().alias("count")
                state_counts = df.group_by("state").agg(count_expr)
                print("\n" + "=" * 70)
                print("🏛️ LOCALVIEW MUNICIPAL MEETINGS (City Council, County Boards)")
                print("=" * 70)
                print(f"\nGlobal Dataset: {global_count:,} total meetings")
                if global_range:
                    print(f"Date Range: {global_range}")
                print("\nBy State:")

                for row in state_counts.iter_rows(named=True):
                    state = row.get("state", "Unknown")
                    count = row.get("count", 0)
                    if state in states:
                        print(f"  {state}: {count:,} meetings")
                        results[state]["meeting_count"] = count
        except Exception as e:
            logger.warning(f"Could not read {meetings_global}: {e}")
    else:
        print("\n" + "=" * 70)
        print("🏛️ LOCALVIEW MUNICIPAL MEETINGS")
        print("=" * 70)
        print("\n❌ No LocalView data found")
        print("\nTo load LocalView data:")
        print("1. Download from: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM")
        print("2. Save to: data/cache/localview/")
        print("3. Run: python -m ingestion.localview.events")

    return results


def check_youtube_cache(states: List[str]) -> Dict[str, Dict]:
    """Check cached YouTube scraping data"""
    logger.info("📹 Checking YouTube Scraping Cache...")

    cache_dir = Path("data/cache/localview")
    results = {}

    # Check for municipality channels
    channels_file = cache_dir / "municipality_channels.csv"
    has_channels = channels_file.exists()

    if POLARS_AVAILABLE and has_channels:
        try:
            df = pl.read_csv(channels_file)

            print("\n" + "=" * 70)
            print("📹 YOUTUBE SCRAPING CACHE")
            print("=" * 70)

            print(f"\nMunicipality Channels: {len(df):,} total")

            if "state" in df.columns:
                for state in states:
                    state_channels = df.filter(pl.col("state") == state)
                    count = len(state_channels)
                    results[state] = {"channel_count": count}
                    print(f"  {state}: {count} channels")

                    # Show municipalities
                    if count > 0 and "municipality" in df.columns:
                        munis = state_channels["municipality"].to_list()[:5]
                        print(f"       {', '.join(munis)}")
                        if count > 5:
                            print(f"       ... and {count - 5} more")

            # Check for video cache
            video_files = list(cache_dir.glob("videos_*.parquet"))
            if video_files:
                print(f"\n✅ Cached video data: {len(video_files)} files")
                for vf in video_files[:5]:
                    print(f"  - {vf.name}")
            else:
                print("\n⚠️  No cached video data")

        except Exception as e:
            logger.warning(f"Could not read {channels_file}: {e}")
    else:
        print("\n" + "=" * 70)
        print("📹 YOUTUBE SCRAPING CACHE")
        print("=" * 70)
        print("\n❌ No YouTube channel data found")
        print("\nTo discover channels:")
        print("python -m scrapers.youtube.update_municipality_list --states AL,GA,IN,MA,MT,WA,WI")

    return results


def print_recommendations(states: List[str]):
    """Print recommended next steps"""
    print("\n" + "=" * 70)
    print("🎯 RECOMMENDED NEXT STEPS")
    print("=" * 70)

    print("\n1️⃣  Download LocalView Historical Data (2006-2023)")
    print("   Visit: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM")
    print("   Save to: data/cache/localview/")
    print("   Run: python -m ingestion.localview.events")

    print("\n2️⃣  Discover Municipal YouTube Channels")
    print("   python -m scrapers.youtube.update_municipality_list \\")
    print(f"       --states {','.join(states)}")

    print("\n3️⃣  Scrape Recent Meetings (2024-2026)")
    print("   # First, get YouTube API key from Google Cloud Console")
    print("   # Add to .env: YOUTUBE_API_KEY=your_key_here")
    print("   python -m scrapers.youtube.scrape_youtube_channels \\")
    print(f"       --states {','.join(states)} \\")
    print("       --since 2024-01-01")

    print("\n4️⃣  Extract Transcripts and Contacts")
    print("   python scripts/datasources/localview/extract_transcripts.py \\")
    print(f"       --states {','.join(states)}")
    print("")
    print("   python -m ingestion.publication.gold.manage_contacts extract \\")
    print(f"       --states {','.join(states)} \\")
    print("       --batch-size 1000")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Check meeting data status for priority states"
    )
    parser.add_argument(
        '--states',
        default=','.join(PRIORITY_STATES),
        help=f'Comma-separated state codes (default: {",".join(PRIORITY_STATES)})',
    )

    args = parser.parse_args()
    states = [s.strip().upper() for s in args.states.split(',') if s.strip()]

    logger.info(f"Checking meeting data for: {', '.join(states)}")

    # Run all checks
    check_openstates_events(states)
    check_localview_meetings(states)
    check_youtube_cache(states)

    # Print recommendations
    print_recommendations(states)


if __name__ == "__main__":
    main()
