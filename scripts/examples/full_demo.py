"""
Comprehensive demo: AI Summarization + Keyword Alerts + Batch Processing

Shows the complete workflow from:
1. Loading discovered jurisdictions
2. AI summarization of meeting content
3. Keyword alert generation
4. Quality metrics tracking
"""
import asyncio
from datetime import datetime
from pathlib import Path

# Check for OpenAI API key
from config.settings import settings

# Import our new capabilities
from scripts.extraction.summarizer import MeetingSummarizer, summarize_meeting_simple
from scripts.alerts.keyword_monitor import KeywordAlertSystem, generate_alert_email
from scripts.discovery.batch_processor import BatchProcessor, JurisdictionQuality
from models.meeting_event import MeetingEvent, Classification, Location


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def demo_ai_summarization():
    """Demo: AI-powered meeting summarization (OpenTowns pattern)."""
    print_section("🤖 AI SUMMARIZATION (OpenTowns Pattern)")
    
    # Example meeting
    event = MeetingEvent(
        title="City Council Regular Meeting",
        description="Discussion of community water fluoridation program",
        classification=Classification.COUNCIL,
        start=datetime(2026, 4, 15, 18, 0),
        location=Location(
            name="City Hall Council Chambers",
            address="710 N 20th Street",
            city="Birmingham",
            state="AL"
        ),
        jurisdiction_name="Birmingham",
        state_code="AL",
        source="https://birminghamal.gov/meetings/2026-04-15"
    )
    
    # Example meeting transcript
    transcript = """
    BIRMINGHAM CITY COUNCIL REGULAR MEETING
    April 15, 2026 - 6:00 PM
    City Hall Council Chambers
    
    PRESENT: Mayor Woodfin, Council President Scales, Councilors Smith,
    Johnson, Martinez, Davis, Brown, Wilson, Thompson, Lee
    
    AGENDA ITEM 3: RESOLUTION 2026-045
    Community Water Fluoridation Program Implementation
    
    Mayor Woodfin: "Tonight we are considering Resolution 2026-045, which
    would implement a community water fluoridation program for Birmingham's
    municipal water system. Dr. Sarah Johnson from the Alabama Department
    of Public Health is here to present."
    
    Dr. Johnson: "Thank you, Mayor. Community water fluoridation is recognized
    by the CDC as one of the ten great public health achievements of the 20th
    century. It's a safe, effective, and equitable way to prevent tooth decay
    across all age groups and socioeconomic levels.
    
    The proposed program would adjust fluoride levels in Birmingham's water
    to 0.7 mg/L, consistent with CDC and American Dental Association guidelines.
    Research shows this reduces tooth decay by 25% in children and adults.
    
    We estimate the program would cost $120,000 annually in operation and
    maintenance. However, the economic benefits are substantial - for every
    dollar invested, we save approximately $10 in dental treatment costs.
    That's $1.2 million in prevented costs annually for Birmingham."
    
    Councilor Smith: "I've reviewed the financial analysis and support this
    initiative. Tooth decay is a significant problem in our community,
    particularly among children. This is a cost-effective prevention measure."
    
    Councilor Johnson: "I appreciate the presentation, but I'd like to hear
    from our residents before we vote. I propose we schedule a public hearing
    to gather community input."
    
    Mayor Woodfin: "That's a reasonable request. Let's schedule a public
    hearing for May 6th at 6:00 PM."
    
    MOTION by Councilor Smith, seconded by Councilor Martinez, to schedule
    a public hearing on Resolution 2026-045 for May 6, 2026 at 6:00 PM.
    
    VOTE: 9 Ayes, 1 No (Councilor Thompson)
    Motion carried.
    
    AGENDA ITEM 4: UPDATE ON MEDICAID DENTAL EXPANSION
    
    Health Director Martinez: "The state has approved expanded Medicaid dental
    coverage for adults. We're working with local dental clinics to ensure
    capacity. We expect 5,000 newly eligible residents in Birmingham."
    
    MEETING ADJOURNED at 8:15 PM
    Next meeting: April 29, 2026 at 6:00 PM
    """
    
    # Check if API key is configured
    if not settings.openai_api_key:
        print("⚠️  OpenAI API key not configured.")
        print("\nTo enable AI summarization:")
        print("  1. Set OPENAI_API_KEY in your .env file")
        print("  2. Or export OPENAI_API_KEY='sk-...'")
        print("\n📝 Showing what the output would look like:\n")
        
        # Show mock summary
        print("Executive Summary:")
        print("  The Birmingham City Council voted 9-1 to schedule a public hearing")
        print("  on a community water fluoridation program. The program would cost")
        print("  $120,000 annually but could prevent $1.2M in dental costs.")
        print("\nKey Decisions:")
        print("  • Public hearing scheduled for May 6, 2026")
        print("  • Resolution 2026-045 moved to public comment phase")
        print("\nHealth Policy Items:")
        print("  • Community water fluoridation program (0.7 mg/L CDC standard)")
        print("  • Medicaid dental expansion for 5,000 Birmingham residents")
        print("\nNext Actions:")
        print("  • Public hearing: May 6, 2026 at 6:00 PM")
        print("  • Next council meeting: April 29, 2026")
        return
    
    # Generate real summary
    try:
        summarizer = MeetingSummarizer()
        summary = summarizer.summarize(event, transcript, focus_on_health=True)
        
        print(f"📋 Meeting: {event.title}")
        print(f"📍 Location: {event.jurisdiction_name}, {event.state_code}")
        print(f"📅 Date: {event.start.strftime('%B %d, %Y')}")
        print(f"\n✨ Executive Summary:")
        print(f"  {summary.executive_summary}")
        
        if summary.key_decisions:
            print(f"\n✅ Key Decisions ({len(summary.key_decisions)}):")
            for decision in summary.key_decisions:
                print(f"  • {decision}")
        
        if summary.health_policy_items:
            print(f"\n🏥 Health Policy Items ({len(summary.health_policy_items)}):")
            for item in summary.health_policy_items:
                print(f"  • {item}")
        
        if summary.next_actions:
            print(f"\n⏭️  Next Actions ({len(summary.next_actions)}):")
            for action in summary.next_actions:
                print(f"  • {action}")
        
        print(f"\n📊 Quality Metrics:")
        print(f"  Confidence: {summary.confidence_score:.0%}")
        print(f"  Source length: {summary.source_length:,} chars")
        print(f"  Summary length: {summary.summary_length:,} chars")
        print(f"  Compression ratio: {(summary.summary_length/summary.source_length):.1%}")
        print(f"  Model: {summary.model_used}")
        print(f"  Tokens used: {summary.tokens_used:,}")
        
    except Exception as e:
        print(f"❌ Error generating summary: {e}")


def demo_keyword_alerts():
    """Demo: Keyword-based alert system (OpenTowns pattern)."""
    print_section("🔔 KEYWORD ALERTS (OpenTowns Pattern)")
    
    # Same event and transcript as above
    event = MeetingEvent(
        title="City Council Regular Meeting",
        classification=Classification.COUNCIL,
        start=datetime(2026, 4, 15, 18, 0),
        jurisdiction_name="Birmingham",
        state_code="AL",
        source="https://birminghamal.gov/meetings/2026-04-15"
    )
    
    transcript = """
    Birmingham City Council - April 15, 2026
    
    Resolution 2026-045: Community Water Fluoridation Program
    
    The council voted to schedule a public hearing on implementing community
    water fluoridation. Dr. Johnson from the Alabama Department of Public Health
    presented data showing fluoridation reduces tooth decay by 25%. The program
    would adjust fluoride levels to 0.7 mg/L per CDC guidelines.
    
    Cost-benefit analysis: $120,000 annual cost, $1.2 million in prevented
    dental treatment costs. Vote: 9-1 to schedule public hearing May 6.
    
    Also discussed: Medicaid dental expansion for adults, 5,000 newly eligible
    Birmingham residents. Health Director Martinez coordinating with dental
    clinics to ensure capacity.
    """
    
    # Scan for keywords
    alert_system = KeywordAlertSystem()
    alerts = alert_system.scan_meeting(event, transcript)
    
    if alerts:
        alert = alerts[0]
        
        print(f"🚨 ALERT GENERATED!")
        print(f"\nAlert ID: {alert.alert_id}")
        print(f"Priority: {alert.priority.value.upper()} ({'🔴' if alert.priority.value == 'critical' else '🟠' if alert.priority.value == 'high' else '🟡'})")
        print(f"\n📍 Meeting Details:")
        print(f"  Jurisdiction: {alert.jurisdiction_name}, {alert.state_code}")
        print(f"  Title: {alert.meeting_title}")
        print(f"  Date: {alert.meeting_date.strftime('%B %d, %Y at %I:%M %p')}")
        
        print(f"\n🎯 Match Details:")
        print(f"  Total matches: {alert.total_matches}")
        print(f"  Categories: {', '.join(alert.categories_matched)}")
        print(f"  Confidence: {alert.confidence_score:.0%}")
        
        print(f"\n🔑 Keywords Found ({len(alert.keywords_found)}):")
        for i, keyword in enumerate(alert.keywords_found[:12], 1):
            print(f"  {i:2d}. {keyword}")
        if len(alert.keywords_found) > 12:
            print(f"  ... and {len(alert.keywords_found) - 12} more")
        
        print(f"\n📄 Relevant Excerpt:")
        print(f"  \"{alert.snippet[:250]}...\"")
        
        print(f"\n📧 Email Alert:")
        print(f"  Generated HTML email ready to send to subscribers")
        print(f"  Preview: 'CRITICAL Priority Alert: {alert.meeting_title}'")
        
        # Show first few lines of HTML email
        email_html = generate_alert_email(alert)
        print(f"  Length: {len(email_html):,} chars")
        
    else:
        print("ℹ️  No alerts generated (insufficient keyword matches)")


def demo_batch_processing():
    """Demo: Batch processing with quality metrics (LocalView pattern)."""
    print_section("📊 BATCH PROCESSING & QUALITY METRICS (LocalView Pattern)")
    
    print("This system handles large-scale processing of 1,000+ jurisdictions:\n")
    
    # Show quality metric example
    print("📈 Quality Tracking Per Jurisdiction:\n")
    
    example_metrics = JurisdictionQuality(
        jurisdiction_name="Birmingham",
        state_code="AL",
        fips_code="0107000",
        url="https://birminghamal.gov",
        platform="legistar",
        total_meetings_expected=24,  # Biweekly meetings
        total_meetings_found=20,
        meetings_with_agendas=20,
        meetings_with_minutes=15,
        meetings_with_videos=10,
        meetings_with_transcripts=8,
        last_scraped=datetime.utcnow(),
        last_meeting_found=datetime(2026, 4, 15),
        scraping_frequency="biweekly",
        consecutive_successes=5,
        consecutive_failures=0,
        total_scrapes=10,
        successful_scrapes=10,
        last_success=datetime.utcnow(),
        last_error=None,
        completeness_score=85.0,
        reliability_score=100.0,
        freshness_score=100.0,
        overall_quality=90.0,
        health_status="healthy",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime.utcnow()
    )
    
    print(f"Jurisdiction: {example_metrics.jurisdiction_name}, {example_metrics.state_code}")
    print(f"Platform: {example_metrics.platform}")
    print(f"\nData Completeness:")
    print(f"  Expected meetings: {example_metrics.total_meetings_expected}")
    print(f"  Found meetings: {example_metrics.total_meetings_found}")
    print(f"  With agendas: {example_metrics.meetings_with_agendas}")
    print(f"  With minutes: {example_metrics.meetings_with_minutes}")
    print(f"  With videos: {example_metrics.meetings_with_videos}")
    
    print(f"\nReliability:")
    print(f"  Total scrapes: {example_metrics.total_scrapes}")
    print(f"  Successful: {example_metrics.successful_scrapes}")
    print(f"  Success rate: {(example_metrics.successful_scrapes/example_metrics.total_scrapes)*100:.0f}%")
    print(f"  Consecutive successes: {example_metrics.consecutive_successes}")
    
    print(f"\nQuality Scores:")
    print(f"  Completeness: {example_metrics.completeness_score:.1f}/100")
    print(f"  Reliability: {example_metrics.reliability_score:.1f}/100")
    print(f"  Freshness: {example_metrics.freshness_score:.1f}/100")
    print(f"  Overall: {example_metrics.overall_quality:.1f}/100")
    
    print(f"\nHealth Status: {example_metrics.health_status.upper()} ✅")
    
    print("\n🔄 Batch Processing Features:")
    print("  • Process 100 jurisdictions at a time")
    print("  • Track success/failure per batch")
    print("  • Automatic retry with exponential backoff")
    print("  • Resume from interruption")
    print("  • Quality metrics per jurisdiction")
    print("  • System-wide health reporting")
    
    print("\n💡 Example Usage:")
    print("""
  from scripts.discovery.batch_processor import BatchProcessor
  
  processor = BatchProcessor(batch_size=100)
  
  # Process all high-priority jurisdictions
  for batch_result in processor.process_all_jurisdictions(priority_filter='high'):
      print(f"Batch {batch_result.batch_number}: "
            f"{batch_result.success_rate:.1f}% success")
      print(f"  Meetings found: {batch_result.meetings_found}")
      print(f"  Duration: {batch_result.duration_seconds:.0f}s")
  
  # Get system health report
  health = processor.get_system_health_report()
  print(f"System health: {health['health_percentage']:.1f}% healthy jurisdictions")
    """)


def demo_integration_summary():
    """Show summary of all integrated capabilities."""
    print_section("🎯 COMPLETE INTEGRATION SUMMARY")
    
    print("✅ Integrated Patterns from 11 Civic Tech Projects:\n")
    
    capabilities = [
        ("Platform Detection", "Civic Scraper", "✅ discovery/platform_detector.py"),
        ("Event Schema", "City Scrapers", "✅ models/meeting_event.py"),
        ("Matter Tracking", "Engagic", "✅ models/meeting_event.py"),
        ("AI Summarization", "OpenTowns", "✅ extraction/summarizer.py"),
        ("Keyword Alerts", "OpenTowns", "✅ alerts/keyword_monitor.py"),
        ("Batch Processing", "LocalView", "✅ discovery/batch_processor.py"),
        ("Quality Metrics", "LocalView", "✅ discovery/batch_processor.py"),
        ("Summary Validation", "MeetingBank", "✅ extraction/summarizer.py"),
        ("Video Ingestion", "CDP", "📋 Roadmapped"),
        ("Cross-Jurisdiction Search", "CivicBand", "📋 Architecture designed"),
        ("Person/Vote Tracking", "Councilmatic", "📋 Planned"),
    ]
    
    for capability, source, status in capabilities:
        icon = "✅" if "✅" in status else "📋"
        print(f"{icon} {capability:25s} ({source:15s}) → {status.replace('✅', '').replace('📋', '').strip()}")
    
    print("\n📚 Documentation:")
    print("  • docs/INTEGRATION_GUIDE.md - First 5 projects (Civic Scraper, City Scrapers, CDP, Engagic, Councilmatic)")
    print("  • docs/SCALE_AND_SEARCH_PATTERNS.md - Next 6 projects (OpenTowns, LocalView, etc.)")
    
    print("\n🎬 Demo Scripts:")
    print("  • examples/integration_demo.py - Platform detection & event models")
    print("  • examples/full_demo.py (this file) - AI summarization, alerts, batch processing")
    
    print("\n🚀 Ready for Production:")
    print("  1. ✅ Jurisdiction discovery (85,302 records from Census)")
    print("  2. ✅ URL matching (76 .gov domains found)")
    print("  3. ✅ Platform detection (8 platforms supported)")
    print("  4. ✅ AI summarization (GPT-4o-mini)")
    print("  5. ✅ Keyword alerts (6 categories, 4 priority levels)")
    print("  6. ✅ Batch processing (100 at a time with quality tracking)")
    print("  7. 📋 Next: Implement actual scrapers (Legistar, Granicus, etc.)")


def main():
    """Run all demos."""
    print("\n" + "🦷" * 40)
    print("  CommunityOne Open Navigatory")
    print("  Full Integration Demo: AI + Alerts + Scale")
    print("🦷" * 40)
    
    # Run demos
    demo_ai_summarization()
    demo_keyword_alerts()
    demo_batch_processing()
    demo_integration_summary()
    
    print("\n" + "=" * 80)
    print("  ✅ Demo Complete!")
    print("=" * 80)
    
    print("\n💡 Try it yourself:")
    print("  python examples/full_demo.py")
    print("\n  Or explore individual capabilities:")
    print("  • python extraction/summarizer.py")
    print("  • python alerts/keyword_monitor.py")
    print("  • python scripts/discovery/batch_processor.py")


if __name__ == "__main__":
    main()
