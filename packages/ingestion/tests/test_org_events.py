"""Organization events parsers and polite client (#1347), offline."""
from __future__ import annotations

from datetime import date

import httpx
import pytest

from ingestion.org_events import parse
from ingestion.org_events.crawl import crawl_site
from ingestion.org_events.fetch import USER_AGENT, PoliteClient


def test_normalize_website():
    assert parse.normalize_website("WWW.CAPESAMARITAN.COM") == "https://www.capesamaritan.com/"
    assert parse.normalize_website("http://example.org/about") == "https://example.org/about/"
    assert parse.normalize_website("N/A") is None
    assert parse.normalize_website("info@example.org") is None
    assert parse.normalize_website("www.facebook.com/someorg") is None


def test_website_from_990_xml():
    xml = (
        '<Return xmlns="http://www.irs.gov/efile"><ReturnData><IRS990>'
        "<WebsiteAddressTxt>WWW.EXAMPLE.ORG</WebsiteAddressTxt></IRS990></ReturnData></Return>"
    )
    assert parse.website_from_990_xml(xml) == "https://www.example.org/"
    assert parse.website_from_990_xml("<not xml") is None


JSONLD_PAGE = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
 {"@type":"Event","name":"Town hall on water","startDate":"2026-12-10T18:30:00-05:00",
  "url":"/events/town-hall","location":{"@type":"Place","name":"Library","address":{"addressLocality":"Savannah","addressRegion":"GA"}}},
 {"@type":"Event","name":"Cancelled gala","startDate":"2026-12-12","eventStatus":"https://schema.org/EventCancelled"},
 {"@type":"Event","name":"No date"}
]}
</script></head><body>
<a href="/events/">Events</a> <a href="https://other.org/events/">x</a> <a href="/?ical=1">iCal</a>
</body></html>
"""


def test_events_from_jsonld_keeps_stated_dates_only():
    evs = parse.events_from_jsonld(JSONLD_PAGE, ein="123456789", page_url="https://www.example.org/")
    assert [e.title for e in evs] == ["Town hall on water"]
    e = evs[0]
    assert e.start_date == date(2026, 12, 10)
    assert e.event_url == "https://www.example.org/events/town-hall"
    assert e.location == "Library, Savannah, GA"
    assert e.source_format == "jsonld"


ICS = """BEGIN:VCALENDAR\r
BEGIN:VEVENT\r
SUMMARY:Pickleball open play\\, all levels\r
DTSTART;TZID=America/New_York:20261205T090000\r
LOCATION:Central Park courts\r
URL:https://www.example.org/e/1\r
END:VEVENT\r
BEGIN:VEVENT\r
SUMMARY:Board meeting\r
DTSTART;VALUE=DATE:20261220\r
STATUS:CANCELLED\r
END:VEVENT\r
BEGIN:VEVENT\r
SUMMARY:Annual meet\r
 ing\r
DTSTART:20270115T170000Z\r
END:VEVENT\r
END:VCALENDAR\r
"""


def test_events_from_ical():
    evs = parse.events_from_ical(ICS, ein="1", feed_url="https://www.example.org/?ical=1")
    assert [e.title for e in evs] == ["Pickleball open play, all levels", "Annual meeting"]
    assert evs[0].start_date == date(2026, 12, 5)
    assert evs[0].location == "Central Park courts"
    assert evs[1].start_at is not None and evs[1].start_at.tzinfo is not None


def test_event_links_same_site_feeds_first():
    links = parse.event_links(JSONLD_PAGE, "https://www.example.org/")
    assert links == ["https://www.example.org/?ical=1", "https://www.example.org/events/"]


def test_upcoming_drops_past_and_dupes():
    evs = parse.events_from_ical(ICS, ein="1", feed_url="f")
    assert len(parse.upcoming(evs + evs, date(2026, 12, 6))) == 1


def _client(handler) -> PoliteClient:
    return PoliteClient(min_interval=0, client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None)


def test_crawl_respects_robots_and_ua():
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n", headers={"content-type": "text/plain"})
        return httpx.Response(200, text=JSONLD_PAGE, headers={"content-type": "text/html"})

    status, events = crawl_site(_client(handler), "1", "https://www.example.org/", date(2026, 12, 1))
    assert status == "robots_disallowed" and events == []
    assert [r.url.path for r in seen] == ["/robots.txt"]
    assert seen[0].headers["user-agent"] == USER_AGENT


def test_crawl_stops_on_429():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(429)

    c = _client(handler)
    status, _ = crawl_site(c, "1", "https://www.example.org/", date(2026, 12, 1))
    assert status == "blocked" and "www.example.org" in c.blocked


def test_crawl_reads_feed():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.params.get("ical") == "1":
            return httpx.Response(200, text=ICS, headers={"content-type": "text/calendar"})
        return httpx.Response(200, text=JSONLD_PAGE, headers={"content-type": "text/html"})

    status, events = crawl_site(_client(handler), "1", "https://www.example.org/", date(2026, 12, 1))
    assert status == "ok"
    assert {e.title for e in events} == {"Town hall on water", "Pickleball open play, all levels", "Annual meeting"}


@pytest.mark.parametrize("raw", ["", None, "   "])
def test_normalize_empty(raw):
    assert parse.normalize_website(raw) is None
