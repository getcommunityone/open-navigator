"""Primary YouTube channel selection from discovery payloads."""

from scripts.discovery.youtube_primary_channel import pick_primary_youtube_channel


def test_pick_primary_prefers_official_meeting_confidence():
    channels = [
        {
            "channel_url": "https://www.youtube.com/@low",
            "discovery_method": "pattern_match",
            "confidence": 0.95,
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
