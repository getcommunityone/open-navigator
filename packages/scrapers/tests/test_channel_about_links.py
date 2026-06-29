"""
Offline Pytest Coverage for channel_about_links.py
Test Cases 3 & 4
"""
import pytest
from scrapers.youtube.channel_about_links import (
    parse_compact_count,
    parse_channel_about_page,
    ChannelAboutSnapshot
)

def test_parse_compact_count():
    """Case 4: parse_compact_count handles 1.2M, 856 videos, and empty input."""
    assert parse_compact_count("1.2M subscribers") == 1200000
    assert parse_compact_count("856 videos") == 856
    assert parse_compact_count("3.4B views") == 3400000000
    assert parse_compact_count("45K") == 45000
    assert parse_compact_count("hidden") is None
    assert parse_compact_count("") is None
    assert parse_compact_count(None) is None

def test_parse_channel_about_page_offline():
    """Case 3: Extract featured links + subscriber counts from mocked ytInitialData HTML."""
    mock_html = """
    <html>
        <body>
            <script>
                var ytInitialData = {
                    "header": {
                        "c4TabbedHeaderRenderer": {
                            "subscriberCountText": {"simpleText": "2.5M subscribers"},
                            "videosCountText": {"simpleText": "1,234 videos"}
                        }
                    },
                    "metadata": {
                        "channelMetadataRenderer": {
                            "title": "City Gov Channel",
                            "description": "Official city channel. Visit https://city.gov for more."
                        }
                    },
                    "contents": {
                        "channelExternalLinkViewModel": {
                            "title": {"simpleText": "Official Website"},
                            "link": {"content": "https://www.city.gov"}
                        }
                    }
                };
            </script>
        </body>
    </html>
    """
    
    snapshot = parse_channel_about_page(mock_html)
    
    assert snapshot.subscriber_count == 2500000
    assert snapshot.video_count == 1234
    assert snapshot.channel_title == "City Gov Channel"
    assert snapshot.channel_type == "municipal"
    
    urls = [link["url"] for link in snapshot.links]
    assert "https://city.gov" in urls
    assert "https://www.city.gov" in urls