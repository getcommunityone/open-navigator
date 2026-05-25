"""Tests for meetings-scrape YouTube int → bronze sync helpers."""

from scripts.discovery.sync_bronze_jurisdiction_youtube_from_meetings_scrape import _build_row


def test_build_row_meetings_scrape_source():
    row = _build_row(
        {
            "channel_url": "https://www.youtube.com/@TuscaloosaCityAL",
            "channel_id": None,
            "channel_title": "City of Tuscaloosa",
            "channel_description": "Council meeting recordings.",
            "confidence_score": 0.85,
            "discovery_method": "website_scrape",
            "jurisdiction_type": "municipality",
            "jurisdiction_name": "Tuscaloosa city",
            "state_code": "AL",
            "website_url": "https://www.tuscaloosa.com",
            "discovered_on": "https://www.tuscaloosa.com/meetings",
            "link_type": "channel",
            "back_links_to_jurisdiction_website": True,
            "official_meeting_confidence": 0.85,
        }
    )
    assert row["source"] == "meetings_scrape"
    assert row["discovery_method"] == "website_scrape"
    assert row["raw_row"]["sync_source"] == "int_jurisdiction_meetings_scrape_youtube_channels"
