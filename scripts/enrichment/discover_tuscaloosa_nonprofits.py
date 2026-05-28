#!/usr/bin/env python3
"""
Run Tuscaloosa Nonprofit Discovery Pipeline

This script discovers nonprofits and churches in Tuscaloosa, AL using:
1. ProPublica Nonprofit Explorer API (free)
2. IRS Tax-Exempt Organization data
3. Every.org Charity API
4. Local service directories (211, Findhelp.org)

Output: frontend/policy-dashboards/src/data/tuscaloosa_nonprofits.json
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.irs.nonprofit_discovery import (
    NonprofitDiscovery,
    discover_tuscaloosa_nonprofits
)
from loguru import logger


def main():
    """Run complete nonprofit discovery for Tuscaloosa"""
    
    logger.info("="*70)
    logger.info("TUSCALOOSA NONPROFIT DISCOVERY PIPELINE")
    logger.info("="*70)
    
    # Target NTEE codes for oral health policy
    ntee_codes = [
        "E",    # Health - General
        "E32",  # School-Based Health Care (dental programs)
        "E40",  # Reproductive Health Care
        "F",    # Mental Health
        "K",    # Food, Agriculture, Nutrition
        "K30",  # Food Service Programs
        "O",    # Youth Development
        "O50",  # Youth Development Programs
        "P",    # Human Services
        "X",    # Religion Related
        "X20"   # Christian (churches with health ministries)
    ]
    
    logger.info(f"Searching for {len(ntee_codes)} NTEE code categories...")
    
    # Run discovery
    nonprofits = discover_tuscaloosa_nonprofits(ntee_codes)
    
    logger.info("="*70)
    logger.info("DISCOVERY COMPLETE")
    logger.info("="*70)
    logger.info(f"Total nonprofits discovered: {len(nonprofits)}")
    
    # Categorize results
    by_category = {}
    for org in nonprofits:
        ntee = org.get("ntee_code", "Unknown")[:1]  # Major category
        if ntee not in by_category:
            by_category[ntee] = []
        by_category[ntee].append(org)
    
    print("\nBreakdown by Category:")
    category_names = {
        "E": "Health Services",
        "F": "Mental Health",
        "K": "Food & Nutrition",
        "O": "Youth Development",
        "P": "Human Services",
        "X": "Religious Organizations"
    }
    
    for code, orgs in sorted(by_category.items(), key=lambda x: len(x[1]), reverse=True):
        name = category_names.get(code, f"NTEE {code}")
        total_revenue = sum(org.get("revenue_amount", 0) or 0 for org in orgs)
        print(f"  {name}: {len(orgs)} orgs, ${total_revenue:,} total revenue")
    
    # Highlight top organizations
    print("\nTop 10 Organizations by Revenue:")
    sorted_orgs = sorted(
        nonprofits,
        key=lambda x: x.get("revenue_amount", 0) or 0,
        reverse=True
    )
    
    for i, org in enumerate(sorted_orgs[:10], 1):
        revenue = org.get("revenue_amount", 0) or 0
        ntee = org.get("ntee_code", "N/A")
        print(f"  {i}. {org['name']}")
        print(f"     NTEE: {ntee} | Revenue: ${revenue:,}/year")
    
    # Health-specific analysis
    health_orgs = [
        org for org in nonprofits
        if org.get("ntee_code", "").startswith("E") or
           org.get("ntee_code", "").startswith("F")
    ]
    
    print(f"\nHealth & Mental Health Organizations: {len(health_orgs)}")
    print("Top 5 Health Orgs:")
    for org in sorted(health_orgs, key=lambda x: x.get("revenue_amount", 0) or 0, reverse=True)[:5]:
        revenue = org.get("revenue_amount", 0) or 0
        print(f"  • {org['name']}: ${revenue:,}/year")
    
    print("\n✓ Data exported to: frontend/policy-dashboards/src/data/tuscaloosa_nonprofits.json")
    print("\nNext Steps:")
    print("  1. Review the exported data")
    print("  2. Manually verify contact information")
    print("  3. Add specific 'services provided' from local directories")
    print("  4. Launch frontend with: cd frontend/policy-dashboards && npm start")


if __name__ == "__main__":
    main()
