"""#549: local news feeds, keyed news APIs and YouTube Data API search (recorded fixtures, no network)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from ingestion.data_centers import community_events as ce
from ingestion.data_centers import news_apis as na
from ingestion.data_centers import news_feeds as nf
from ingestion.data_centers import video_search as vs

FIXTURES = Path(__file__).parent / "fixtures" / "data_centers"
RSS = (FIXTURES / "abc3340_topic_applied_digital.rss").read_bytes()
ARTICLE = (FIXTURES / "abc3340_town_hall_article.html").read_text()
ATOM = (FIXTURES / "atom_sample.xml").read_bytes()
TOWN_HALL_URL = (
    "https://abc3340.com/news/local/"
    "applied-digital-town-hall-addresses-brookwood-residents-questions-about-proposed-data-cen"
)
NAMES = nf.TrackedNames(("Applied Digital",), ("Delta Forge 2",), ("Ellendale",))


def _fetcher(handler) -> ce.PoliteFetcher:
    client = httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": ce.USER_AGENT})
    return ce.PoliteFetcher(min_interval=0, client=client, sleep=lambda s: None)


def _robots_ok(request: httpx.Request) -> httpx.Response | None:
    if request.url.path == "/robots.txt":
        return httpx.Response(200, text="User-agent: *\nAllow: /\n", headers={"content-type": "text/plain"})
    return None


# --- seed ---------------------------------------------------------------------------------


def test_seed_round_trips_and_only_allowed_enabled_feeds_are_usable(tmp_path: Path) -> None:
    seed = tmp_path / "local_news_feeds.csv"
    seed.write_text(
        "feed_id,outlet,state_code,feed_url,robots_checked_on,robots_allowed,enabled,note\n"
        "a,A,al,https://a.test/feed,2026-11-17,true,true,\n"
        "b,B,AL,https://b.test/feed,2026-11-17,false,true,\n"
        "c,C,AL,https://c.test/feed,2026-11-17,true,false,HTTP 429\n"
        "d,D,AL,,,false,false,no feed\n"
    )
    feeds = nf.read_feed_seed(seed)
    assert [f.feed_id for f in feeds if f.usable] == ["a"]
    assert feeds[0].state_code == "AL" and feeds[0].robots_checked_on == date(2026, 11, 17)
    nf.write_feed_seed(feeds, seed)
    assert nf.read_feed_seed(seed) == feeds


def test_repo_seed_has_contract_columns_and_no_google_news() -> None:
    feeds = nf.read_feed_seed()
    assert {f.state_code for f in feeds} >= {"AL", "GA", "VA", "TX", "IN", "OH", "ND", "LA", "AZ", "WI", "MN"}
    assert len({f.feed_id for f in feeds}) == len(feeds)
    for f in feeds:
        assert "news.google.com" not in f.feed_url
        assert not ce.is_blocked_host(f.feed_url or "https://x.test")
        if f.feed_url:
            assert f.robots_checked_on is not None
    outlets = {f.outlet for f in feeds}
    assert {"ABC 33/40", "Spectrum News", "AL.com", "Business Alabama"} <= outlets


def test_template_feed_expands_per_term_url_encoded() -> None:
    urls = nf.expand_feed_url("https://abc3340.com/topic/{term}.rss", ["Applied Digital", "xA", "Applied Digital"])
    assert urls == ["https://abc3340.com/topic/Applied%20Digital.rss"]
    assert nf.expand_feed_url("https://a.test/feed", ["x"]) == ["https://a.test/feed"]


# --- feed parsing -------------------------------------------------------------------------


def test_parse_recorded_rss_feed() -> None:
    items = nf.parse_feed(RSS)
    assert items[0]["link"] == TOWN_HALL_URL
    assert items[0]["title"] == "Applied Digital addresses Brookwood residents' questions about proposed data center"
    assert nf.parse_feed_datetime(items[0]["published"]) == datetime(2026, 10, 2, 2, 59, 35, tzinfo=timezone.utc)


def test_parse_atom_feed() -> None:
    items = nf.parse_feed(ATOM)
    assert [i["link"] for i in items] == [
        "https://gazette.example.test/news/county-data-center",
        "https://gazette.example.test/sports/scores",
    ]
    assert nf.parse_feed_datetime(items[0]["published"]) == datetime(2026, 10, 5, 14, 30, tzinfo=timezone.utc)
    assert nf.parse_feed_datetime(items[1]["published"]).utcoffset() == timedelta(hours=-5)
    assert ce.strip_html(items[0]["summary"]) == "Example Digital will hold an open house on Oct. 20."


def test_relevance_needs_data_center_or_a_project_name() -> None:
    assert nf.is_relevant("County hears data center plan", "", [])
    assert nf.is_relevant("Delta Forge 2 update", "", ["Delta Forge 2"])
    assert not nf.is_relevant("Google opens office", "", ["Delta Forge 2"])  # a company alone isn't enough
    assert nf.names_any("Meta platforms", ["Meta"]) == ["Meta"]
    assert nf.names_any("metal works", ["Meta"]) == []


def test_fetch_local_feed_lands_brookwood_town_hall_with_verbatim_article_sentences() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if (r := _robots_ok(request)) is not None:
            return r
        if request.url.path.startswith("/topic/"):
            return httpx.Response(200, content=RSS, headers={"content-type": "application/xml"})
        if request.url.path.startswith("/news/local/"):
            return httpx.Response(200, text=ARTICLE, headers={"content-type": "text/html"})
        raise AssertionError(f"unexpected {request.url}")

    feed = nf.LocalNewsFeed("abc3340-topic", "ABC 33/40", "AL", "https://abc3340.com/topic/{term}.rss",
                            date(2026, 11, 17), True)
    items, entries = nf.fetch_local_feed(_fetcher(handler), feed, NAMES, max_pages=5)
    # two expansions (Applied Digital, Ellendale) of a 2-item feed, each article kept once
    assert entries == 4
    assert [i.url for i in items] == [TOWN_HALL_URL, items[1].url]
    town_hall = items[0]
    assert town_hall.source == "rss" and town_hall.publisher == "ABC 33/40"
    assert "held its first town hall on its planned Delta Forge 2 data center campus" in town_hall.snippet
    assert "Skip to main content" not in town_hall.snippet
    for passage in town_hall.snippet.split(" … "):
        assert passage in ce.strip_html(ARTICLE)  # verbatim
    assert town_hall.raw["kinds"] == ["town_hall"]


def test_feed_not_fetched_when_robots_disallows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /topic/\n", headers={"content-type": "text/plain"})
        raise AssertionError("must not fetch a disallowed feed")

    feed = nf.LocalNewsFeed("x", "X", "AL", "https://x.test/topic/{term}.rss", date(2026, 11, 17), True)
    items, entries = nf.fetch_local_feed(_fetcher(handler), feed, NAMES)
    assert (items, entries) == ([], 0)


def test_bot_challenge_or_429_in_place_of_robots_means_disallowed() -> None:
    challenge = "<html><title>Just a moment...</title>Checking your browser</html>"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "challenge.test":
            return httpx.Response(200, text=challenge, headers={"content-type": "text/html"})
        return httpx.Response(429, text="slow down", headers={"content-type": "text/plain"})

    fetcher = _fetcher(handler)
    assert not fetcher.allowed("https://challenge.test/feed/")
    assert not fetcher.allowed("https://limited.test/feed/")
    assert ce.looks_like_bot_challenge(challenge)
    assert not ce.looks_like_bot_challenge("<html><article>News</article></html>")


def test_check_robots_records_date_and_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "no.test":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n", headers={"content-type": "text/plain"})
        return httpx.Response(200, text="User-agent: *\nAllow: /\n", headers={"content-type": "text/plain"})

    feeds = [nf.LocalNewsFeed("y", "Y", "AL", "https://yes.test/feed"),
             nf.LocalNewsFeed("n", "N", "AL", "https://no.test/feed", date(2026, 1, 1), True),
             nf.LocalNewsFeed("e", "E", "AL", "")]
    out = nf.check_robots(_fetcher(handler), feeds, date(2026, 11, 17))
    assert [(f.robots_allowed, f.robots_checked_on) for f in out] == [
        (True, date(2026, 11, 17)), (False, date(2026, 11, 17)), (False, None)]


# --- keyed APIs ---------------------------------------------------------------------------


def test_providers_skip_quietly_without_a_key() -> None:
    fetcher = _fetcher(lambda r: (_ for _ in ()).throw(AssertionError("no call without a key")))
    for provider, env_name in na.KEY_ENV.items():
        items, line = na.run_provider(provider, fetcher, ["q"], env={})
        assert items == [] and line == f"skipped ({env_name} not set)"
    assert na.api_key("newsapi", {"NEWSAPI_KEY": "  "}) is None


def test_keys_never_appear_in_logged_errors() -> None:
    secret = "-".join(["not", "a", "real", "key"])  # built at runtime: a fake key
    assert na.redact(f"GET https://x.test/?api-key={secret} failed", secret) == "GET https://x.test/?api-key=*** failed"

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(401, text=f'{{"message": "bad key {secret}"}}')

    from loguru import logger

    messages: list[str] = []
    sink = logger.add(messages.append, format="{message}")
    try:
        items, _ = na.run_provider("guardian", _fetcher(handler), ["data center"], env={"GUARDIAN_API_KEY": secret})
    finally:
        logger.remove(sink)
    assert items == [] and seen and seen[0].url.params["api-key"] == secret
    assert messages and not any(secret in m for m in messages)


def test_newsapi_key_goes_in_header_and_items_parse() -> None:
    body = {"status": "ok", "articles": [
        {"source": {"name": "Example Gazette"}, "url": "https://gazette.example.test/a",
         "title": "Example Digital town hall on data center", "description": "<b>Residents</b> asked questions.",
         "publishedAt": "2026-10-02T12:00:00Z"},
        {"source": {"name": "x"}, "url": "https://removed.test", "title": "[Removed]"},
        {"source": {"name": "x"}, "url": "https://prophecygov.com/x", "title": "blocked"},
    ]}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Api-Key"] == "k1" and "apiKey" not in request.url.params
        return httpx.Response(200, json=body)

    items, line = na.run_provider("newsapi", _fetcher(handler), ["q"], env={"NEWSAPI_KEY": "k1"})
    assert line == "1 items from 1 queries"
    assert items[0].publisher == "Example Gazette" and items[0].snippet == "Residents asked questions."
    assert items[0].published_at == datetime(2026, 10, 2, 12, tzinfo=timezone.utc)


def test_guardian_and_brave_parse() -> None:
    g = na.parse_guardian({"response": {"results": [
        {"webUrl": "https://www.theguardian.com/x", "webTitle": "Data centers", "webPublicationDate": "2026-10-01T08:00:00Z",
         "fields": {"trailText": "<p>Towns push back</p>"}}]}}, "q")
    assert g[0].publisher == "The Guardian" and g[0].snippet == "Towns push back"
    b = na.parse_brave({"web": {"results": [
        {"url": "https://www.brookwood.example.test/notice", "title": "Town hall <strong>notice</strong>",
         "description": "Applied Digital will host a <strong>town hall</strong>.", "page_age": "2026-09-30T00:00:00",
         "meta_url": {"hostname": "www.brookwood.example.test"}}]}}, "q")
    assert b[0].title == "Town hall notice" and b[0].snippet == "Applied Digital will host a town hall ."
    assert b[0].publisher == "www.brookwood.example.test"


def test_query_builders() -> None:
    targets = [na.SearchTarget("Applied Digital", "Delta Forge 2", None, "AL"),
               na.SearchTarget("Applied Digital", "Polaris Forge 1", "Ellendale", "ND"),
               na.SearchTarget("Meta")]
    nq = na.news_queries(targets)
    assert nq[0] == '"data center" AND "town hall"'
    assert any(q.startswith('"Applied Digital" AND "data center" AND (') for q in nq)
    wq = na.web_queries(targets)
    assert '"Delta Forge 2" town hall' in wq
    assert '"Applied Digital" data center community meeting Ellendale ND' in wq
    assert '"Meta" data center town hall' in wq


# --- YouTube Data API search --------------------------------------------------------------

SEARCH_JSON = {"items": [
    {"id": {"kind": "youtube#video", "videoId": "AAAAAAAAAAA"},
     "snippet": {"publishedAt": "2026-10-02T01:00:00Z", "channelId": "UC1", "channelTitle": "ABC 33/40 News",
                 "title": "Applied Digital holds Brookwood town hall &amp; Q&amp;A", "description": "short…",
                 "liveBroadcastContent": "none"}},
    {"id": {"kind": "youtube#channel", "channelId": "UC2"}, "snippet": {"title": "a channel"}},
]}
VIDEOS_JSON = {"items": [{"id": "AAAAAAAAAAA", "snippet": {"description": "Full description of the Brookwood town hall."}}]}


def test_video_queries_follow_projects_and_window() -> None:
    today = date(2026, 11, 17)
    qs = vs.video_queries([
        vs.ProjectTarget("Applied Digital", "Delta Forge 2", None, None, "AL", date(2026, 6, 8)),
        vs.ProjectTarget("Applied Digital", "Polaris Forge 1", "Ellendale", None, "ND", date(2021, 1, 1)),
        vs.ProjectTarget("Meta"),
    ], today)
    by_q = {q.query: q.published_after for q in qs}
    assert by_q['"Delta Forge 2" town hall'] == date(2026, 6, 8)
    assert by_q['"Polaris Forge 1" town hall'] == today - vs.LOOKBACK  # never more than 18 months back
    assert '"Applied Digital" community meeting Ellendale ND' in by_q
    assert '"Applied Digital" data center Ellendale' in by_q
    assert '"Meta" data center town hall' in by_q


def test_due_queries_resume_and_respect_budget() -> None:
    now = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
    qs = [vs.VideoQuery(f"q{i}", date(2026, 1, 1)) for i in range(5)]
    last = {"q0": now - timedelta(days=1), "q1": now - timedelta(days=30), "q2": now - timedelta(days=10)}
    due = vs.due_queries(qs, last, budget_left=3, refresh_days=7, now=now)
    assert [q.query for q in due] == ["q3", "q4", "q1"]  # never searched, then the stalest
    assert vs.due_queries(qs, last, budget_left=0, refresh_days=7, now=now) == []


def test_quota_day_is_pacific() -> None:
    assert vs.quota_day(datetime(2026, 11, 18, 5, tzinfo=timezone.utc)) == date(2026, 11, 17)


def test_data_api_search_lands_hits_with_full_description_and_redacts_key() -> None:
    secret = "-".join(["fake", "youtube", "key"])
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.url.host == "www.googleapis.com" and request.url.params["key"] == secret
        if request.url.path.endswith("/search"):
            assert request.url.params["publishedAfter"] == "2025-05-18T00:00:00Z"
            return httpx.Response(200, json=SEARCH_JSON)
        return httpx.Response(200, json=VIDEOS_JSON)

    api = vs.DataApi(secret, client=httpx.Client(transport=httpx.MockTransport(handler)), pause=0)
    q = vs.VideoQuery('"Applied Digital" Brookwood town hall', date(2025, 5, 18))
    hits = api.search(q)
    assert [h["video_id"] for h in hits] == ["AAAAAAAAAAA"]
    item = vs.hit_item(hits[0], q, api.descriptions(["AAAAAAAAAAA"])["AAAAAAAAAAA"])
    assert item.source == "youtube_search" and item.url == "https://www.youtube.com/watch?v=AAAAAAAAAAA"
    assert item.title == "Applied Digital holds Brookwood town hall & Q&A"
    assert item.publisher == "ABC 33/40 News" and item.query == q.query
    assert item.snippet == "Full description of the Brookwood town hall."
    assert item.raw["channel_id"] == "UC1" and secret not in json.dumps(item.raw)

    def quota(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text='{"error": {"errors": [{"reason": "quotaExceeded"}]}}')

    api = vs.DataApi(secret, client=httpx.Client(transport=httpx.MockTransport(quota)), pause=0)
    with pytest.raises(vs.QuotaExceeded):
        api.search(q)

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"failed {request.url}")

    api = vs.DataApi(secret, client=httpx.Client(transport=httpx.MockTransport(boom)), pause=0)
    with pytest.raises(RuntimeError) as err:
        api.search(q)
    assert secret not in str(err.value)


def test_one_word_townhall_is_a_town_hall() -> None:
    assert ce.matched_kinds("Behind the Build Ep. 2: The Townhall") == ["town_hall"]
    assert ce.matched_kinds("Two townhalls and a town hall") == ["town_hall"]
