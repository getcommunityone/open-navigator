"""Primary YouTube channel selection from discovery payloads."""

from scripts.discovery.youtube_primary_channel import pick_primary_youtube_channel


def test_pick_primary_prefers_official_meeting_confidence():
    channels = [
        {
            "channel_url": "https://www.youtube.com/@low",
            "discovery_method": "pattern_match",
            "confidence": 0.95,  # legacy upstream field — ignored for ranking
            "official_meeting_confidence": 0.2,
        },
        {
            "channel_url": "https://www.youtube.com/@official",
            "discovery_method": "website_scrape",
            "confidence": 0.7,
            "official_meeting_confidence": 0.88,
        },
    ]
    url, method, conf = pick_primary_youtube_channel(channels)
    assert url == "https://www.youtube.com/@official"
    assert method == "website_scrape"
    assert conf == 0.88


def test_pick_primary_empty():
    assert pick_primary_youtube_channel([]) == (None, None, None)


def test_pick_primary_prefers_homepage_scrape_over_youtube_api():
    channels = [
        {
            "channel_url": "https://www.youtube.com/channel/UCwrong",
            "discovery_method": "youtube_api",
            "official_meeting_confidence": 0.3,
            "video_count": 900,
        },
        {
            "channel_url": "https://www.youtube.com/@whitleycountygovernment",
            "discovery_method": "website_scrape",
            "official_meeting_confidence": 0.9,
            "video_count": 1,
        },
    ]
    url, method, conf = pick_primary_youtube_channel(channels)
    assert url == "https://www.youtube.com/@whitleycountygovernment"
    assert method == "website_scrape"
    assert conf == 0.9


def test_pick_primary_skips_tv_public_and_general():
    channels = [
        {
            "channel_url": "https://www.youtube.com/@CountyTV",
            "discovery_method": "website_scrape",
            "official_meeting_confidence": 0.95,
            "channel_purpose": "tv-public",
        },
        {
            "channel_url": "https://www.youtube.com/@CountyCommission",
            "discovery_method": "website_scrape",
            "official_meeting_confidence": 0.7,
            "channel_purpose": "county-meeting",
        },
    ]
    url, method, conf = pick_primary_youtube_channel(channels)
    assert url == "https://www.youtube.com/@CountyCommission"
    assert conf == 0.7


def test_pick_primary_ignores_legacy_confidence_without_official_score():
    """Method priority still breaks ties when only legacy ``confidence`` is present."""
    channels = [
        {
            "channel_url": "https://www.youtube.com/channel/UCwrong",
            "discovery_method": "youtube_api",
            "confidence": 0.99,
            "video_count": 900,
        },
        {
            "channel_url": "https://www.youtube.com/@whitleycountygovernment",
            "discovery_method": "website_scrape",
            "confidence": 0.1,
            "video_count": 1,
        },
    ]
    url, method, conf = pick_primary_youtube_channel(channels)
    assert url == "https://www.youtube.com/@whitleycountygovernment"
    assert method == "website_scrape"
    assert conf is None
