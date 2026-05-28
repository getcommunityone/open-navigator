"""Tests for website YouTube scraping fallback behavior."""

import pytest

from scrapers.youtube.youtube_channel_discovery import YouTubeChannelDiscovery


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


@pytest.mark.asyncio
async def test_site_search_tries_youtube_meeting_before_youtube():
    """The site-search fallback should prefer the more specific
    "youtube meeting" query and only escalate to "youtube" when the
    specific query produces no YouTube channel links."""
    discovery = YouTubeChannelDiscovery()
    calls: list[str] = []

    homepage_html = "<html><body><p>nothing useful here</p></body></html>"
    meeting_results_html = """
    <html><body>
      <a href="https://www.youtube.com/channel/UCmeetingchannel00000">Meetings</a>
    </body></html>
    """

    async def fake_get(url: str, *args, **kwargs):
        calls.append(url)
        if "youtube+meeting" in url:
            return _FakeResponse(url=url, text=meeting_results_html, status_code=200)
        return _FakeResponse(url=url, text=homepage_html, status_code=200)

    discovery.client.get = fake_get  # type: ignore[method-assign]

    channels = await discovery._scrape_website_for_channels("https://example.gov/")

    assert "https://www.youtube.com/channel/UCmeetingchannel00000" in channels
    # We should never have escalated to the broader "youtube" query.
    assert not any("q=youtube&" in u or u.endswith("q=youtube") or "s=youtube&" in u or u.endswith("s=youtube") for u in calls)
    assert any("youtube+meeting" in u for u in calls)

    await discovery.close()


@pytest.mark.asyncio
async def test_form_discovery_uses_real_search_endpoint():
    """When the homepage advertises a non-standard search form, the
    discovery layer should derive the real endpoint and use it instead
    of relying solely on guessed URL patterns."""
    discovery = YouTubeChannelDiscovery()
    calls: list[str] = []

    homepage_html = """
    <html><body>
      <form id="site-search" action="/Search.aspx" method="get">
        <input type="hidden" name="scope" value="all" />
        <input type="text" name="searchtext" />
      </form>
    </body></html>
    """
    search_html = """
    <html><body>
      <a href="https://www.youtube.com/@ExampleGov">YouTube channel</a>
    </body></html>
    """

    async def fake_get(url: str, *args, **kwargs):
        calls.append(url)
        if "/Search.aspx" in url:
            return _FakeResponse(url=url, text=search_html, status_code=200)
        return _FakeResponse(url=url, text=homepage_html, status_code=200)

    discovery.client.get = fake_get  # type: ignore[method-assign]

    channels = await discovery._scrape_website_for_channels("https://example.gov/")

    assert channels == ["https://www.youtube.com/@ExampleGov"]
    # Form discovery should have fired before any guessed URLs.
    search_calls = [u for u in calls if "Search.aspx" in u or "search" in u.lower() or "?s=" in u]
    assert search_calls, "expected at least one search request"
    assert "Search.aspx" in search_calls[0], (
        f"discovered form endpoint should be tried before guessed URLs; saw {search_calls!r}"
    )
    # Discovered URL should carry the hidden field and the meeting query.
    assert "scope=all" in search_calls[0]
    assert "searchtext=youtube+meeting" in search_calls[0]

    await discovery.close()


@pytest.mark.asyncio
async def test_playwright_fallback_renders_js_search_results(monkeypatch):
    """When httpx returns no YouTube links across every search URL, the
    Playwright tier should render those URLs and surface JS-only
    results."""
    discovery = YouTubeChannelDiscovery()

    empty_html = "<html><body><p>no static results</p></body></html>"
    js_rendered_html = """
    <html><body>
      <a href="https://www.youtube.com/@JsRenderedGov">Watch our meetings</a>
    </body></html>
    """

    async def fake_get(url: str, *args, **kwargs):
        return _FakeResponse(url=url, text=empty_html, status_code=200)

    discovery.client.get = fake_get  # type: ignore[method-assign]

    pw_calls: list[str] = []

    async def fake_playwright_fetch(url, *, timeout_ms, user_agent):
        pw_calls.append(url)
        return js_rendered_html, "", url

    fake_module = type(
        "FakeModule",
        (),
        {
            "fetch_html_via_playwright": fake_playwright_fetch,
            "playwright_fallback_enabled": lambda: True,
        },
    )

    import sys

    monkeypatch.setitem(sys.modules, "scripts.discovery.meetings_playwright_fetch", fake_module)

    channels = await discovery._scrape_website_for_channels("https://example.gov/")

    assert channels == ["https://www.youtube.com/@JsRenderedGov"]
    assert pw_calls, "expected Playwright tier to fire after httpx tiers returned nothing"

    await discovery.close()


@pytest.mark.asyncio
async def test_playwright_fallback_skipped_when_httpx_finds_links(monkeypatch):
    """The Playwright tier is expensive; verify it is not invoked when
    the httpx tiers already located a YouTube channel."""
    discovery = YouTubeChannelDiscovery()

    homepage_html = "<html><body><p>nothing</p></body></html>"
    search_html = """
    <html><body>
      <a href="https://www.youtube.com/@StaticGov">YouTube</a>
    </body></html>
    """

    async def fake_get(url: str, *args, **kwargs):
        if "search" in url or "?s=" in url:
            return _FakeResponse(url=url, text=search_html, status_code=200)
        return _FakeResponse(url=url, text=homepage_html, status_code=200)

    discovery.client.get = fake_get  # type: ignore[method-assign]

    pw_calls: list[str] = []

    async def fake_playwright_fetch(url, *, timeout_ms, user_agent):
        pw_calls.append(url)
        return None, "should-not-be-called", url

    fake_module = type(
        "FakeModule",
        (),
        {
            "fetch_html_via_playwright": fake_playwright_fetch,
            "playwright_fallback_enabled": lambda: True,
        },
    )

    import sys

    monkeypatch.setitem(sys.modules, "scripts.discovery.meetings_playwright_fetch", fake_module)

    channels = await discovery._scrape_website_for_channels("https://example.gov/")

    assert "https://www.youtube.com/@StaticGov" in channels
    assert pw_calls == [], (
        f"Playwright should not run when httpx already found channels; saw calls={pw_calls!r}"
    )

    await discovery.close()
