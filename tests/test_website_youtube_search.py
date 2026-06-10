"""Website YouTube link extraction for jurisdiction pilot."""

from scrapers.discovery.website_youtube_search import (
    _extract_youtube_urls_from_html,
    _normalize_youtube_url,
)


def test_normalize_legacy_custom_channel_slug():
    assert _normalize_youtube_url("https://www.youtube.com/augustagagov") == (
        "https://www.youtube.com/@augustagagov"
    )


def test_normalize_modern_handle_and_channel():
    assert _normalize_youtube_url("https://www.youtube.com/@AugustaGeorgiaGov") == (
        "https://www.youtube.com/@AugustaGeorgiaGov"
    )
    assert _normalize_youtube_url(
        "https://www.youtube.com/channel/UCj33t_Opz-YZ7auj6-RIs_A"
    ) == ("https://www.youtube.com/channel/UCj33t_Opz-YZ7auj6-RIs_A")


def test_extract_from_civicplus_youtube_hub_html():
    html = """
    <a href="https://www.youtube.com/channel/UCj33t_Opz-YZ7auj6-RIs_A">Channel</a>
    <a href="http://www.youtube.com/@AugustaGeorgiaGov">Handle</a>
    <a href="https://www.youtube.com/augustagagov">Legacy</a>
    """
    urls = _extract_youtube_urls_from_html(html)
    assert "https://www.youtube.com/channel/UCj33t_Opz-YZ7auj6-RIs_A" in urls
    assert "https://www.youtube.com/@AugustaGeorgiaGov" in urls
    assert "https://www.youtube.com/@augustagagov" in urls
