"""
Example: Using platform detection with discovered URLs.

This script demonstrates how to:
1. Load discovered URLs from Silver layer
2. Detect which platform each URL uses
3. Prepare optimized scraping strategies
"""
import asyncio
from pathlib import Path

# Imports from your project
from scripts.discovery.platform_detector import detect_platform_async, get_platform_capabilities
from models.meeting_event import MeetingEvent, Classification
from config.settings import settings


async def analyze_discovered_urls():
    """
    Analyze all discovered URLs and detect their platforms.
    """
    print("🔍 Analyzing discovered URLs for platform detection...\n")
    
    # Check if we have discovered URLs
    silver_path = Path(f"{settings.delta_lake_path}/silver/discovered_urls")
    if not silver_path.exists():
        print("❌ No discovered URLs found. Run: python main.py discover-jurisdictions --limit 500")
        return
    
    # Load URLs using pandas (simpler than PySpark for small data)
    import pandas as pd
    df = pd.read_parquet(silver_path, engine='pyarrow')
    
    print(f"📊 Found {len(df)} discovered URLs\n")
    print("=" * 80)
    
    # Analyze each URL
    platform_counts = {}
    platform_examples = {}
    
    for idx, row in df.head(20).iterrows():  # Analyze first 20 for demo
        url = row['url']
        jurisdiction = row['jurisdiction_name']
        state = row['state_code']
        
        # Detect platform (async for thorough detection)
        result = await detect_platform_async(url, fetch_html=False)
        
        platform = result['platform'] or 'unknown'
        confidence = result['confidence']
        
        # Track counts
        platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        # Store example
        if platform not in platform_examples:
            platform_examples[platform] = {
                'url': url,
                'jurisdiction': jurisdiction,
                'state': state
            }
        
        # Display
        status = "✅" if result['scraper_available'] else "⚠️"
        print(f"{status} {jurisdiction}, {state}")
        print(f"   Platform: {platform} (confidence: {confidence:.1%})")
        print(f"   URL: {url}")
        
        # Show capabilities
        if platform != 'unknown':
            caps = get_platform_capabilities(platform)
            if caps.get('has_api'):
                print(f"   🚀 API Available: {caps.get('api_docs', 'Yes')}")
            if caps.get('scraper_class'):
                print(f"   🤖 Scraper: {caps['scraper_class']}")
        
        print()
    
    # Summary
    print("=" * 80)
    print("\n📈 Platform Distribution:\n")
    for platform, count in sorted(platform_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(df.head(20))) * 100
        bar = "█" * int(percentage / 5)
        print(f"  {platform:15s} {count:3d} ({percentage:5.1f}%) {bar}")
    
    print("\n💡 Next Steps:")
    print("  1. Implement scrapers for top platforms")
    print("  2. Test scraping on example URLs")
    print("  3. Add platform info to Silver layer")
    
    return platform_counts, platform_examples


async def demo_event_creation():
    """
    Demonstrate creating standardized MeetingEvent objects.
    """
    print("\n" + "=" * 80)
    print("📅 Demo: Creating Standardized Meeting Events\n")
    
    # Example 1: From Birmingham
    event1 = MeetingEvent(
        title="Birmingham City Council Regular Meeting",
        description="Regular meeting with discussion of water system improvements",
        classification=Classification.COUNCIL,
        start=datetime(2026, 4, 21, 18, 0),
        location=Location(
            name="City Hall Council Chambers",
            address="710 N 20th Street",
            city="Birmingham",
            state="AL"
        ),
        source="https://birminghamal.gov/meetings",
        jurisdiction_name="Birmingham city",
        state_code="AL"
    )
    
    # Add documents
    event1.add_link("Agenda", "https://birminghamal.gov/agenda-20260421.pdf")
    event1.add_link("Video Recording", "https://birminghamal.gov/video/20260421")
    
    # Mark as oral health relevant
    event1.oral_health_relevant = True
    event1.keywords_found = ["water", "fluoridation", "public health"]
    event1.confidence_score = 0.85
    
    print(f"Event 1: {event1.title}")
    print(f"  Location: {event1.location}")
    print(f"  Has agenda: {event1.has_agenda()}")
    print(f"  Has video: {event1.has_video()}")
    print(f"  Oral health relevant: {event1.oral_health_relevant}")
    print(f"  Keywords: {', '.join(event1.keywords_found)}")
    print(f"  Confidence: {event1.confidence_score:.1%}")
    
    # Show how it converts to Delta Lake format
    print(f"\n📝 Delta Lake format (first 5 fields):")
    data_dict = event1.to_dict()
    for key in list(data_dict.keys())[:5]:
        print(f"  {key}: {data_dict[key]}")
    
    print(f"\n✅ Event ID: {event1.id}")
    print(f"   (Generated from: {event1.source} + {event1.start.isoformat()})")


async def demo_matter_tracking():
    """
    Demonstrate tracking a policy matter across meetings.
    """
    from models.meeting_event import Matter
    from datetime import datetime
    
    print("\n" + "=" * 80)
    print("📋 Demo: Matter Tracking (Legislative Item Evolution)\n")
    
    # Track a fluoridation ordinance
    matter = Matter(
        matter_id="BHM-2024-FL001",
        matter_number="Ordinance 2024-045",
        title="Community Water Fluoridation Program Implementation",
        type="Ordinance",
        first_introduced=datetime(2024, 1, 15),
        status="Committee Review"
    )
    
    # Add related meetings
    matter.related_meetings = [
        "mtg-20240115-council",
        "mtg-20240205-health-committee", 
        "mtg-20240220-public-hearing"
    ]
    
    # Add documents
    from models.meeting_event import Link
    matter.related_documents = [
        Link("Original Ordinance", "https://example.gov/ord-2024-045.pdf"),
        Link("Committee Report", "https://example.gov/committee-report.pdf"),
        Link("Public Comments", "https://example.gov/comments.pdf")
    ]
    
    # Mark as health policy
    matter.is_health_policy = True
    matter.policy_keywords = ["fluoridation", "oral health", "CDC guidelines"]
    
    print(f"Matter: {matter.title}")
    print(f"  Number: {matter.matter_number}")
    print(f"  Type: {matter.type}")
    print(f"  Status: {matter.status}")
    print(f"  First introduced: {matter.first_introduced.strftime('%B %d, %Y')}")
    print(f"  Related meetings: {len(matter.related_meetings)}")
    print(f"  Documents: {len(matter.related_documents)}")
    print(f"  Health policy: {matter.is_health_policy}")
    print(f"  Keywords: {', '.join(matter.policy_keywords)}")
    
    print("\n💡 This allows you to:")
    print("  - Track how a policy evolves across multiple meetings")
    print("  - See all related documents in one place")
    print("  - Identify windows of opportunity for advocacy")
    print("  - Monitor voting patterns on health issues")


if __name__ == "__main__":
    from datetime import datetime
    from models.meeting_event import Location
    
    print("🦷 CommunityOne Open Navigatory - Platform Integration Demo")
    print("=" * 80)
    
    # Run async demos
    asyncio.run(analyze_discovered_urls())
    asyncio.run(demo_event_creation())
    asyncio.run(demo_matter_tracking())
    
    print("\n" + "=" * 80)
    print("✅ Demo complete!")
    print("\n📖 For more details, see:")
    print("   - docs/INTEGRATION_GUIDE.md")
    print("   - discovery/platform_detector.py")
    print("   - models/meeting_event.py")
