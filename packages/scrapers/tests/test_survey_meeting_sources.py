"""Meeting-source survey (#460): fingerprints, address parsing, county matching. No network."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import pytest

from scrapers.discovery import survey_meeting_sources as sms
from scrapers.discovery.meeting_source_fingerprints import (
    challenge_reason,
    classify_url,
    detect_meeting_sources,
    meeting_page_links,
    merge_sources,
)

HOMEPAGE = """
<html><head>
<script src="https://www.youtube.com/iframe_api"></script>
<script>var cfg = {"stream": "https://abilenetx.new.swagit.com/videos/12345"};</script>
</head><body>
<a href="/561/Live-Archived-Video">Live &amp; Archived Video</a>
<a href="/AgendaCenter">Agendas &amp; Minutes</a>
<a href="https://abilenetx.legistar.com/Calendar.aspx">Legislation</a>
<a href="https://www.youtube.com/@CityofAbilene">YouTube</a>
<a href="https://www.youtube.com/watch?v=abcdefghijk">Last meeting</a>
<a href="https://www.facebook.com/CityOfAbilene">Facebook page</a>
<a href="https://www.facebook.com/CityOfAbilene/videos/987654">Council livestream</a>
<iframe src="https://player.vimeo.com/video/76979871"></iframe>
<iframe src="https://boxcast.tv/channel/vabcd1234"></iframe>
<a href="https://taylorcotx.portal.civicclerk.com/">Portal</a>
<a href="https://go.boarddocs.com/tx/abil/Board.nsf/Public">BoardDocs</a>
<a href="https://abilene.iqm2.com/Citizens/Default.aspx">IQM2</a>
<a href="https://pub-abilene.escribemeetings.com/">eScribe</a>
<a href="https://abilene.primegov.com/public/portal">PrimeGov</a>
<a href="https://abilene-tx.municodemeetings.com/">Municode Meetings</a>
<a href="https://abilene.cablecast.tv/CablecastPublicSite/">Cablecast</a>
<a href="https://abilenetx.granicus.com/ViewPublisher.php?view_id=2">Granicus</a>
<a href="https://taylorcotx.suiteonemedia.com/">SuiteOne</a>
<a href="https://us06web.zoom.us/rec/share/AbCdEf">Recording</a>
<a href="https://www.granicus.com/">Powered by Granicus</a>
<a href="https://library.municode.com/tx/abilene">Code of ordinances</a>
<a href="/departments/parks">Parks</a>
<a href="https://other-site.org/meetings">Somebody else's meetings</a>
<a href="/docs/agenda.pdf">Agenda PDF</a>
</body></html>
"""


def _platforms(html: str, url: str = "https://abilenetx.gov/") -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for src in detect_meeting_sources(html, url):
        out.setdefault(src.platform, set()).add(src.url)
    return out


def test_detects_every_platform_in_links_iframes_and_scripts():
    found = _platforms(HOMEPAGE)
    assert set(found) == {
        "youtube", "swagit", "legistar", "facebook_video", "vimeo", "boxcast", "civicclerk", "boarddocs",
        "iqm2", "escribe", "primegov", "municode_meetings", "cablecast", "granicus", "suiteone",
        "zoom_recording", "civicplus_agenda_center",
    }
    assert found["youtube"] == {"https://www.youtube.com/@CityofAbilene", "https://www.youtube.com/watch?v=abcdefghijk"}
    assert found["swagit"] == {"https://abilenetx.new.swagit.com/"}  # from an inline script
    assert found["vimeo"] == {"https://vimeo.com/76979871"}
    assert found["facebook_video"] == {"https://www.facebook.com/CityOfAbilene/videos/987654"}
    assert found["civicplus_agenda_center"] == {"https://abilenetx.gov/AgendaCenter"}
    assert found["boarddocs"] == {"https://go.boarddocs.com/tx/abil/Board.nsf/Public"}


def test_vendor_marketing_sites_and_code_libraries_are_not_sources():
    assert classify_url("https://www.granicus.com/") is None
    assert classify_url("https://library.municode.com/tx/abilene") is None
    assert classify_url("https://www.facebook.com/CityOfAbilene") is None
    assert classify_url("https://www.youtube.com/iframe_api") is None
    assert classify_url("https://vimeo.com/join") is None


def test_media_per_platform():
    assert classify_url("https://abilenetx.new.swagit.com/videos/1")[2] == "video"
    assert classify_url("https://abilenetx.legistar.com/Calendar.aspx")[2] == "documents"
    assert classify_url("https://abilenetx.granicus.com/ViewPublisher.php?view_id=2")[2] == "both"


def test_youtube_embed_forms_canonicalize():
    assert classify_url("https://www.youtube.com/embed/abcdefghijk?rel=0")[1] == "https://www.youtube.com/watch?v=abcdefghijk"
    assert classify_url("https://youtu.be/abcdefghijk")[1] == "https://www.youtube.com/watch?v=abcdefghijk"
    assert classify_url("https://www.youtube.com/embed/live_stream?channel=UC123")[1] == "https://www.youtube.com/channel/UC123"


def test_meeting_page_links_are_same_site_keyword_links_only():
    links = meeting_page_links(HOMEPAGE, "https://abilenetx.gov/", "https://abilenetx.gov/", limit=10)
    assert "https://abilenetx.gov/561/Live-Archived-Video" in links
    assert "https://abilenetx.gov/AgendaCenter" not in links  # already a source, not a page to crawl
    assert all("other-site.org" not in u and not u.endswith(".pdf") and "parks" not in u for u in links)


def test_merge_keeps_channels_first_and_caps_per_platform():
    from scrapers.discovery.meeting_source_fingerprints import MeetingSource

    videos = [MeetingSource("youtube", f"https://www.youtube.com/watch?v=vid{i:08d}", "video", "p") for i in range(8)]
    channel = MeetingSource("youtube", "https://www.youtube.com/@City", "video", "p")
    merged = merge_sources(videos + [channel], cap=5)
    assert merged[0] == channel
    assert len(merged) == 5


@pytest.mark.parametrize(
    "html,status,expected",
    [
        ("<html><title>Just a moment...</title><script>window._cf_chl_opt={}</script></html>", 200, "cloudflare"),
        ("", 403, "http_403"),
        ("", 429, "http_429"),
        ("<html><body>Incapsula incident ID: 123</body></html>", 200, "incapsula"),
        (HOMEPAGE, 200, None),
    ],
)
def test_challenge_pages_count_as_blocked(html, status, expected):
    assert challenge_reason(html, status) == expected


@pytest.mark.parametrize(
    "address,place,state,zip_code,has_street",
    [
        ("5502 Spinks Rd, Abilene, TX 79601", "Abilene", "TX", "79601", False),
        ("14436-14998 Fairview Rd, Springfield, NE 68059, USA", "Springfield", "NE", "68059", False),
        ("1401 Meadowville Technology Parkway, Chester, VA", "Chester", "VA", None, False),
        ("216 Greenfield Rd, Lancaster, PA\n", "Lancaster", "PA", None, False),
        ("1626 County Line Road Ridgeland, Mississippi", "1626 County Line Road Ridgeland", "MS", None, True),
        ("3963 S Lincoln Ave, Vineland, New Jersey", "Vineland", "NJ", None, False),
        ("5800 EDGEWOOD RD SW CEDAR RAPIDS, IA 52404", "5800 EDGEWOOD RD SW CEDAR RAPIDS", "IA", "52404", True),
        ("Cheyenne, WY 82007, USA", "Cheyenne", "WY", "82007", False),
    ],
)
def test_parse_address(address, place, state, zip_code, has_street):
    parsed = sms.parse_address(address)
    assert parsed == sms.ParsedAddress(place, state, zip_code, has_street)


def test_parse_address_rejects_garbage():
    assert sms.parse_address("") is None
    assert sms.parse_address("somewhere in the desert") is None


def test_normalize_place_name_drops_census_suffixes():
    assert sms.normalize_place_name("Mount Pleasant village") == "mount pleasant"
    assert sms.normalize_place_name("St. Joseph city") == "saint joseph"
    assert sms.normalize_place_name("Mt Pleasant") == "mount pleasant"
    assert sms.normalize_place_name("New Carlisle town") == "new carlisle"


PLACES_IA = [
    {"jurisdiction_id": "cedar_rapids_1912000", "geoid": "1912000", "name": "Cedar Rapids", "lsad": "25"},
    {"jurisdiction_id": "fairfax_1926400", "geoid": "1926400", "name": "Fairfax city", "lsad": "25"},
]


def test_match_place_with_street_words_and_suffixes():
    parsed = sms.parse_address("5800 EDGEWOOD RD SW CEDAR RAPIDS, IA 52404")
    assert sms.match_place(parsed, PLACES_IA)["jurisdiction_id"] == "cedar_rapids_1912000"
    parsed = sms.parse_address("6200 76th Ave SW, Fairfax, IA 52228")
    assert sms.match_place(parsed, PLACES_IA)["jurisdiction_id"] == "fairfax_1926400"
    assert sms.match_place(sms.parse_address("1 Main St, Nowhere, IA 50000"), PLACES_IA) is None


class FakeWarehouse:
    def __init__(self) -> None:
        self.places_by_state = {
            "TX": [{"jurisdiction_id": "abilene_4801000", "geoid": "4801000", "name": "Abilene",
                    "jurisdiction_type": "municipality", "state_code": "TX", "state": "Texas", "lsad": "25"}],
            "VA": [{"jurisdiction_id": "sandston_5170256", "geoid": "5170256", "name": "Sandston",
                    "jurisdiction_type": "municipality", "state_code": "VA", "state": "Virginia", "lsad": "57"}],
        }
        self.counties = {
            "4801000": {"jurisdiction_id": "taylor_48441", "geoid": "48441", "name": "Taylor County",
                        "jurisdiction_type": "county", "state_code": "TX", "state": "Texas", "lsad": None},
            "5170256": {"jurisdiction_id": "henrico_51087", "geoid": "51087", "name": "Henrico County",
                        "jurisdiction_type": "county", "state_code": "VA", "state": "Virginia", "lsad": None},
        }
        self.places_by_state["VA"].append(
            {"jurisdiction_id": "manassas_5148952", "geoid": "5148952", "name": "Manassas",
             "jurisdiction_type": "municipality", "state_code": "VA", "state": "Virginia", "lsad": "25"})
        self.counties["5148952"] = {"jurisdiction_id": "manassas_51683", "geoid": "51683", "name": "Manassas city",
                                    "jurisdiction_type": "county", "state_code": "VA", "state": "Virginia", "lsad": None}
        self.zip_counties = {
            "20136": {"jurisdiction_id": "prince_william_51153", "geoid": "51153", "name": "Prince William County",
                      "jurisdiction_type": "county", "state_code": "VA", "state": "Virginia", "lsad": None},
        }

    def data_center_sites(self) -> list[dict[str, Any]]:
        return []

    def places(self, state_code: str) -> list[dict[str, Any]]:
        return self.places_by_state.get(state_code, [])

    def county_for_place(self, geoid: str) -> Optional[dict[str, Any]]:
        return self.counties.get(geoid)

    def county_for_zip(self, zip_code: str) -> Optional[dict[str, Any]]:
        return self.zip_counties.get(zip_code)

    def jurisdiction(self, jurisdiction_id: str) -> Optional[dict[str, Any]]:
        return None

    def websites(self, jurisdiction_id: str) -> list[dict[str, Any]]:
        return []


def test_resolve_city_and_county_with_cdp_and_zip_fallback():
    sites = [
        {"data_center_site_id": "a", "address": "5502 Spinks Rd, Abilene, TX 79601", "state_code": "TX"},
        {"data_center_site_id": "b", "address": "5502 Spinks Rd, Abilene, TX 79601", "state_code": "TX"},
        {"data_center_site_id": "c", "address": "6000 Technology Blvd, Sandston, VA 23150", "state_code": "VA"},
        {"data_center_site_id": "d", "address": "13001 Rollins Ford Road, Bristow, VA 20136", "state_code": "VA"},
        {"data_center_site_id": "e", "address": "5400 Prosperity Dr NW, Toney, AL", "state_code": "AL"},
        {"data_center_site_id": "f", "address": "9590 Hornbaker Rd, Manassas, VA 20109", "state_code": "VA"},
    ]
    govs, matches = sms.resolve_site_governments(sites, FakeWarehouse())
    by_id = {g.jurisdiction_id: g for g in govs}
    assert set(by_id) == {
        "abilene_4801000", "taylor_48441", "henrico_51087", "prince_william_51153", "manassas_5148952",
    }
    assert by_id["abilene_4801000"].site_ids == ["a", "b"]
    status = {m.data_center_site_id: (m.city_status, m.county_match) for m in matches}
    assert status == {
        "a": ("matched", "crosswalk"),
        "b": ("matched", "crosswalk"),
        "c": ("cdp", "crosswalk"),  # no municipal government; the county is surveyed
        "d": ("unmatched", "zip"),
        "e": ("unmatched", "unmatched"),
        "f": ("matched", "same_as_city"),  # Virginia independent city: one government, not two
    }


def _gov(name: str, jtype: str = "municipality", st: str = "TX", state: str = "Texas") -> sms.Government:
    return sms.Government(f"{name.lower()}_1", "1", name, st, state, jtype)


def test_rank_websites_prefers_named_gov_hosts_and_drops_wrong_rows():
    rows = [
        {"website_url": "http://www.abilenetx.com", "website_source": "uscm"},
        {"website_url": "https://downtownabilenetx.gov", "website_source": "gsa", "agency": "City of Abilene"},
        {"website_url": "https://abilenetx.gov", "website_source": "gsa", "agency": "City of Abilene"},
        {"website_url": "https://howland.gov", "website_source": "gsa", "agency": "Howland Township"},
        {"website_url": "https://abilenepd.gov", "website_source": "gsa", "agency": "City of Abilene"},
    ]
    assert sms.rank_websites(rows, _gov("Abilene")) == [
        "https://abilenetx.gov", "https://downtownabilenetx.gov", "http://www.abilenetx.com",
    ]
    county_rows = [
        {"website_url": "https://baldwincountyal.gov/", "website_source": "wikidata"},
        {"website_url": "http://www.allencounty.us/", "website_source": "naco"},
        {"website_url": "https://limestonecounty-al.gov/", "website_source": "scraped"},
    ]
    assert sms.rank_websites(county_rows, _gov("Allen County", "county", "IN", "Indiana")) == ["http://www.allencounty.us/"]


def test_youtube_channel_must_name_government_and_state():
    abilene = _gov("Abilene")
    assert sms.accept_youtube_channel("City of Abilene, Texas", "", abilene)
    assert sms.accept_youtube_channel("City of Abilene TV", "The official channel of Abilene, Texas", abilene)
    assert sms.accept_youtube_channel("City of Abilene", "Official channel of Abilene, TX", abilene)
    assert not sms.accept_youtube_channel("City of Abilene", "Kansas", abilene)
    assert not sms.accept_youtube_channel("City of Abilene", "Videos about Abilene, Texas", abilene)  # not "official"
    assert not sms.accept_youtube_channel("City of Abilene Animal Care Services", "Abilene, Texas", abilene)
    assert not sms.accept_youtube_channel("City of Abilene Wastewater", "official, Texas", abilene)
    assert not sms.accept_youtube_channel("Abilene ISD", "Abilene, Texas", abilene)
    assert not sms.accept_youtube_channel("Abilene Fans Texas", "", abilene)
    county = _gov("Fayette County", "county", "GA", "Georgia")
    assert sms.accept_youtube_channel("Fayette County Georgia BOC", "", county)
    assert not sms.accept_youtube_channel("Fayette County Kentucky", "", county)
    assert not sms.accept_youtube_channel("Humane Society of Fayette County, GA", "", county)
    assert not sms.accept_youtube_channel("Fayette County Health Department - Georgia", "", county)
    assert not sms.accept_youtube_channel("Defense of Democracy Fayette County GA", "", county)


def test_state_code_needs_address_form_not_any_capital_word():
    abilene = _gov("Abilene")
    assert sms.names_state("Abilene, TX 79601", abilene)
    assert sms.names_state("City of Abilene TX", abilene)
    indiana = _gov("Clark County", "county", "IN", "Indiana")
    assert not sms.names_state("SIGN IN to view Clark County meetings", indiana)


def test_school_names_are_not_the_city():
    columbus = _gov("Columbus", st="OH", state="Ohio")
    assert not sms.names_government("Columbus City Schools - BoardDocs", columbus)
    assert sms.names_government("City of Columbus, Ohio", columbus)


def test_youtube_search_uses_the_cache_without_spending_quota(tmp_path):
    import asyncio

    gov = _gov("Abilene")
    cache = sms.YouTubeSearchCache(tmp_path / "yt.json")
    cache.items[sms.youtube_query(gov)] = [
        {"id": {"channelId": "UCfan"}, "snippet": {"title": "Abilene Fans", "description": ""}},
        {"id": {"channelId": "UCcity"}, "snippet": {"title": "City of Abilene, Texas", "description": ""}},
    ]
    hits, spent, answered = asyncio.run(sms.youtube_channel_search(gov, "unused-key", client=None, cache=cache))
    assert answered and not spent
    assert [h.url for h in hits] == ["https://www.youtube.com/channel/UCcity"]
    assert hits[0].found_on == "youtube_search"


def test_vendor_page_must_name_government_and_state():
    abilene = _gov("Abilene")
    page = "<title>City of Abilene - Calendar</title>"
    assert sms.vendor_page_matches(page, "https://abilenetx.legistar.com/Calendar.aspx", abilene)
    assert not sms.vendor_page_matches(page, "https://abilene.legistar.com/Calendar.aspx", abilene)  # no state
    assert not sms.vendor_page_matches("<title>Invalid parameters</title>", "https://abilenetx.legistar.com/", abilene)


def test_bronze_rows_record_nothing_found_as_none():
    gov = _gov("Abilene")
    gov.site_ids = ["z", "a"]
    blocked = sms.GovernmentResult(gov, "https://abilenetx.gov", "blocked", "http_403", 0, [])
    rows = sms.bronze_rows([blocked], datetime(2026, 11, 16, tzinfo=timezone.utc))
    assert rows == [{
        "jurisdiction_id": "abilene_1", "geoid": "1", "state_code": "TX", "jurisdiction_type": "municipality",
        "website_status": "blocked", "data_center_site_id": "a", "surveyed_at": datetime(2026, 11, 16, tzinfo=timezone.utc),
        "platform": "none", "url": "https://abilenetx.gov", "media": None, "found_on": None,
    }]


def test_cli_requires_a_target():
    with pytest.raises(SystemExit):
        sms.main([])
