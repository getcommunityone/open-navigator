"""Tests for website YouTube scraping fallback behavior."""

import pytest

from scripts.datasources.youtube.youtube_channel_discovery import YouTubeChannelDiscovery


class _FakeResponse:
    def __init__(self, url: str, text: str, status_code: int = 200):
        self.url = url
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status_code


@pytest.mark.asyncio
async def test_scrape_extracts_cobb_user_url_directly_without_site_search():
    discovery = YouTubeChannelDiscovery()
    calls: list[str] = []

    homepage_html = """
    <html><body>
      <a href="https://www.youtube.com/user/CobbCountyGovt">YouTube</a>
    </body></html>
    """

    async def fake_get(url: str, *args, **kwargs):
        calls.append(url)
        return _FakeResponse(url=url, text=homepage_html, status_code=200)

    discovery.client.get = fake_get  # type: ignore[method-assign]

    channels = await discovery._scrape_website_for_channels("https://www.cobbcounty.org/")

    assert channels == ["https://www.youtube.com/user/CobbCountyGovt"]
    assert calls == ["https://www.cobbcounty.org/"]

    await discovery.close()


@pytest.mark.asyncio
async def test_scrape_uses_site_search_only_when_direct_links_missing():
    discovery = YouTubeChannelDiscovery()
    calls: list[str] = []

    homepage_html = "<html><body><a href='https://www.cobbcounty.org/departments'>Departments</a></body></html>"
    search_html = """
    <html><body>
      <a href="https://www.youtube.com/user/CobbCountyGovt">Cobb YouTube</a>
    </body></html>
    """

    async def fake_get(url: str, *args, **kwargs):
        calls.append(url)
        if "search" in url or "?s=" in url:
            return _FakeResponse(url=url, text=search_html, status_code=200)
        return _FakeResponse(url=url, text=homepage_html, status_code=200)

    discovery.client.get = fake_get  # type: ignore[method-assign]

    channels = await discovery._scrape_website_for_channels("https://www.cobbcounty.org/")

    assert "https://www.youtube.com/user/CobbCountyGovt" in channels
    assert calls[0] == "https://www.cobbcounty.org/"
    assert any("search" in u or "?s=" in u for u in calls[1:])

    await discovery.close()
