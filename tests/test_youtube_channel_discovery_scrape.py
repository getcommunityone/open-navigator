"""YouTube link extraction and follow-up page discovery."""

import pytest

from scripts.datasources.youtube.youtube_channel_discovery import YouTubeChannelDiscovery


def test_extract_youtube_from_commission_page_html():
    html = """
    <html><body>
    <a href="https://www.youtube.com/channel/UCiOI7RWQKqnEuM3AKnWYLuA">
      Commission Meeting Video Archive
    </a>
    </body></html>
    """
    d = YouTubeChannelDiscovery()
    links = d._extract_youtube_links_from_html(
        html, base_url="https://chiltoncounty.org/commission/"
    )
    assert links == ["https://www.youtube.com/channel/UCiOI7RWQKqnEuM3AKnWYLuA"]


def test_collect_followup_includes_commission_page():
    html = """
    <a href="/commission/">County Commission</a>
    <a href="/contact/">Contact</a>
    """
    d = YouTubeChannelDiscovery()
    urls = d._collect_youtube_followup_page_urls(
        html, base_url="https://chiltoncounty.org/", max_pages=5
    )
    assert "https://chiltoncounty.org/commission" in urls[0] or urls[0].endswith("/commission/")


@pytest.mark.asyncio
async def test_scrape_chilton_home_finds_commission_channel():
    async with YouTubeChannelDiscovery() as discovery:
        channels = await discovery._scrape_website_for_channels("https://chiltoncounty.org/")
    assert any("UCiOI7RWQKqnEuM3AKnWYLuA" in c for c in channels)


def test_extract_whitley_county_handle_from_homepage_link():
    html = """
    <a href="https://www.youtube.com/@whitleycountygovernment">County YouTube</a>
    """
    d = YouTubeChannelDiscovery()
    links = d._extract_youtube_links_from_html(
        html, base_url="https://www.whitleycounty.in.gov/"
    )
    assert links == ["https://www.youtube.com/@whitleycountygovernment"]


@pytest.mark.asyncio
async def test_scrape_whitley_county_in_home_finds_government_handle():
    async with YouTubeChannelDiscovery() as discovery:
        channels = await discovery._scrape_website_for_channels(
            "https://www.whitleycounty.in.gov/"
        )
    assert "https://www.youtube.com/@whitleycountygovernment" in channels
