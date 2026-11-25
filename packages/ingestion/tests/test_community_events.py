"""ingestion.data_centers.community_events (#532): pure parsing, matching and politeness."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import httpx

from ingestion.data_centers import community_events as ce
from ingestion.data_centers import recording_candidates as rc


def test_matched_kinds_finds_each_meeting_word_once() -> None:
    text = "Applied Digital to host town hall; a second Town Halls and an open house follow"
    assert ce.matched_kinds(text) == ["open_house", "town_hall"]
    assert ce.matched_kinds("Data center council vote") == []


def test_says_data_center() -> None:
    assert ce.says_data_center("New data center campus")
    assert ce.says_data_center("Datacenters planned")
    assert not ce.says_data_center("Community center opens")


def test_blocked_hosts_are_never_fetched() -> None:
    assert ce.is_blocked_host("https://www.americansentiment.com/x")
    assert ce.is_blocked_host("https://prophecygov.com/")
    # #956/#958: terms forbid scraping, bulk copying or competing use
    for url in ("https://govmeet.us/topics/data-centers", "https://dcmap.us/", "https://cleanview.co/data-centers",
                "https://geolocity.com/data-centers", "https://zoninglabs.com/data-centers", "https://www.datacentermap.com/usa/"):
        assert ce.is_blocked_host(url), url
    # CC BY lead sources stay fetchable
    for url in ("https://datacenterfights.com/data.json", "https://sitingradar.com/data/siting-radar-upcoming.csv",
                "https://padatacenterordinances.org/coming-up", "https://publicevidence.org/data/x.csv"):
        assert not ce.is_blocked_host(url), url
    assert not ce.is_blocked_host("https://www.abc3340.com/news")


def test_parse_gdelt_keeps_headline_as_verbatim_snippet_and_drops_blocked() -> None:
    body = json.dumps(
        {
            "articles": [
                {"url": "https://example.com/a", "title": "Company to hold town hall on data center",
                 "seendate": "20261002T141500Z", "domain": "example.com", "language": "English"},
                {"url": "https://prophecygov.com/b", "title": "blocked", "seendate": "20261002T141500Z"},
                {"url": "", "title": "no url"},
            ]
        }
    )
    items = ce.parse_gdelt(body, "q")
    assert len(items) == 1
    item = items[0]
    assert item.snippet == item.title == "Company to hold town hall on data center"
    assert item.publisher == "example.com"
    assert item.published_at == datetime(2026, 10, 2, 14, 15, tzinfo=timezone.utc)
    assert ce.parse_gdelt("{}", "q") == []


def test_parse_rss_and_dates() -> None:
    feed = b"""<?xml version="1.0"?><rss><channel>
      <item><title>Delta Forge 2 update</title><link>https://ir.example.com/1</link>
      <pubDate>Mon, 08 Jun 26 16:05:00 -0400</pubDate><description>&lt;p&gt;Hi&lt;/p&gt;</description></item>
    </channel></rss>"""
    items = ce.parse_rss(feed)
    assert items[0]["title"] == "Delta Forge 2 update"
    assert ce.strip_html(items[0]["description"]) == "Hi"
    assert ce.parse_rss_datetime(items[0]["pubDate"]).date() == date(2026, 6, 8)


def test_verbatim_passages_keeps_whole_sentences_only() -> None:
    text = (
        "Applied Digital announced a campus. The company will hold a town hall at the library. "
        "Delta Forge 2 is expected to bring jobs. Unrelated sentence."
    )
    out = ce.verbatim_passages(text, ["Delta Forge 2"])
    assert out == [
        "The company will hold a town hall at the library.",
        "Delta Forge 2 is expected to bring jobs.",
    ]
    assert all(s in text for s in out)


def test_gdelt_queries_cover_each_meeting_word_and_projects() -> None:
    qs = ce.gdelt_queries(["Delta Forge 2", "short"])
    assert '"data center" "town hall" sourcecountry:US' in qs
    assert '"Delta Forge 2"' in qs
    assert '"short"' not in qs
    assert len(qs) == len(ce.KIND_TERMS) + 1


def test_user_agent_names_the_project_without_personal_details() -> None:
    assert "open-navigator" in ce.USER_AGENT
    assert "@" not in ce.USER_AGENT


def _fetcher(handler) -> ce.PoliteFetcher:
    client = httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": ce.USER_AGENT})
    return ce.PoliteFetcher(min_interval=0, client=client, sleep=lambda s: None)


def test_robots_disallow_is_respected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\nAllow: /$\n",
                                  headers={"content-type": "text/plain"})
        raise AssertionError("must not fetch a disallowed path")

    fetcher = _fetcher(handler)
    assert not fetcher.allowed("https://news.google.com/rss/search?q=x")
    try:
        ce.fetch_google_news(fetcher, "x")
    except PermissionError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected PermissionError")


def test_missing_robots_allows_and_gdelt_backs_off_on_429() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, text="<html>nope</html>", headers={"content-type": "text/html"})
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, text="Please limit requests to one every 5 seconds")
        return httpx.Response(200, text='{"articles": []}')

    slept: list[float] = []
    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetcher = ce.PoliteFetcher(min_interval=0, client=client, sleep=slept.append)
    assert ce.fetch_gdelt(fetcher, "q", retries=2, backoff=10) == []
    assert calls["n"] == 2 and 10 in slept


def test_recording_candidate_needs_name_and_date_window() -> None:
    event = rc.Event("e1", "Applied Digital", "Brookwood", "Alabama", "town_hall", date(2026, 10, 6))
    assert rc.search_query(event) == "Applied Digital Brookwood data center town hall"
    assert rc.match_reason(event, "Applied Digital Brookwood town hall", date(2026, 10, 7))
    assert rc.match_reason(event, "Applied Digital town hall", date(2026, 12, 1)) is None  # too late
    assert rc.match_reason(event, "Some other meeting", date(2026, 10, 7)) is None  # names neither
    assert rc.match_reason(event, "Brookwood council", None) is None  # undated


def test_main_content_drops_navigation() -> None:
    page = "<nav>Skip to main content</nav><main><article><p>Delta Forge 2 is a campus.</p></article></main>"
    assert ce.strip_html(ce.main_content(page)) == "Delta Forge 2 is a campus."
    assert ce.main_content("<p>plain</p>") == "<p>plain</p>"


def test_sentences_do_not_split_after_abbreviations() -> None:
    text = "DALLAS, Oct. 2, 2026 -- Applied Digital will hold a town hall at St. Mark Hall. Next."
    assert ce.verbatim_passages(text, []) == [
        "DALLAS, Oct. 2, 2026 -- Applied Digital will hold a town hall at St. Mark Hall."
    ]


def test_robots_server_error_means_disallow() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(503, text="down")
        raise AssertionError("must not fetch while robots.txt errors")

    assert not _fetcher(handler).allowed("https://example.com/page")


def test_release_page_error_keeps_the_feed_item() -> None:
    feed_xml = (b'<?xml version="1.0"?><rss><channel><item><title>Data center town hall set</title>'
                b'<link>https://ir.example.com/r/1</link><pubDate>Mon, 05 Oct 26 08:00:00 -0400</pubDate>'
                b'<description>Example will hold a town hall.</description></item></channel></rss>')

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, text="none", headers={"content-type": "text/html"})
        if request.url.path == "/feed":
            return httpx.Response(200, content=feed_xml)
        raise httpx.ConnectError("boom", request=request)

    feed = ce.CompanyFeed("ex", "Example", "https://ir.example.com/feed")
    items = ce.fetch_company_feed(_fetcher(handler), feed)
    assert len(items) == 1 and items[0].snippet == "Example will hold a town hall."


def test_main_content_without_article_drops_head_and_nav() -> None:
    page = "<html><head><title>X :: Co</title></head><body><nav>Skip</nav><p>Body.</p></body></html>"
    assert ce.strip_html(ce.main_content(page)) == "Body."
