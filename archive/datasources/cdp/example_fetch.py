#!/usr/bin/env python3
"""
Quick example: Fetch Seattle CDP data and show sample

This demonstrates how to use cdp-data package to fetch Council Data Project data.

⚠️ REQUIREMENTS:
- Python 3.10 or 3.11 (NOT 3.12+ due to pandas version conflicts)
- cdp-data package: pip install cdp-data

SETUP:
    python3.11 -m venv cdp-env
    source cdp-env/bin/activate
    pip install cdp-data
    python example_fetch.py
"""

import sys

try:
    from cdp_data import CDPInstances, datasets
    import pandas as pd
    HAS_CDP = True
except ImportError as e:
    HAS_CDP = False
    import_error = str(e)

def main():
    if not HAS_CDP:
        print("❌ cdp-data package not available")
        print(f"   Error: {import_error}\n")
        print("╔════════════════════════════════════════════════════════════════╗")
        print("║  CDP-DATA REQUIRES PYTHON 3.10 or 3.11 (NOT 3.12+)           ║")
        print("╚════════════════════════════════════════════════════════════════╝\n")
        
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        print(f"Current Python version: {python_version}")
        
        if sys.version_info >= (3, 12):
            print("\n⚠️  You're using Python 3.12+, which is incompatible with cdp-data")
            print("   (pandas version conflict)\n")
        
        print("SETUP INSTRUCTIONS:")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        print("1. Install Python 3.11:")
        print("   sudo apt install python3.11 python3.11-venv")
        print("")
        print("2. Create isolated environment:")
        print("   python3.11 -m venv cdp-env")
        print("   source cdp-env/bin/activate")
        print("")
        print("3. Install cdp-data:")
        print("   pip install cdp-data")
        print("")
        print("4. Run this script:")
        print("   python scripts/datasources/cdp/example_fetch.py")
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("\nALTERNATIVE: Use CDP web interface to manually export data")
        print("   https://councildataproject.org/seattle\n")
        return 1

    # Fetch Seattle council sessions from 2024
    print("📥 Fetching Seattle council sessions from CDP...")
    print("   This may take a minute...\n")

    ds = datasets.get_session_dataset(
        infrastructure_slug=CDPInstances.Seattle,
        start_datetime="2024-01-01",
        store_transcript=False,  # Set to True to download transcripts
        replace_py_objects=True,  # Convert Python objects to IDs for storage
    )

    print(f"✅ Fetched {len(ds)} sessions!\n")

    # Show sample data
    print("Sample sessions:")
    print("="*80)
    print(ds[['session_datetime', 'video_uri']].head(10))
    print("="*80)

    print(f"\nColumns available: {', '.join(ds.columns.tolist())}")
    print(f"\nDataset shape: {ds.shape}")

    # Optionally save to CSV
    # ds.to_csv('seattle_cdp_sessions.csv', index=False)
    # print("\n💾 Saved to seattle_cdp_sessions.csv")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
