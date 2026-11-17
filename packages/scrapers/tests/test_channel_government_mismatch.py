"""Guard: a channel whose title or @handle names another government is not assigned
on name evidence alone (#514, #515). Pure: no network, no database."""

from __future__ import annotations

import asyncio

import pytest

from scrapers.discovery.channel_government_mismatch import (
    channel_videos_name_other_government,
    handle_text,
    named_governments,
    real_channel_title,
    title_names_other_government,
)

# Verbatim titles from bronze.bronze_event_youtube (channel UCXouBUErOAg75vra7x9iBGQ,
# filed under Gordon GA / Douglas GA before #514).
BROOKS_BOC = "BROOKS COUNTY BOARD OF COMMISSIONERS REGULAR MONTHLY MEETING FEB 2, 2026 IN Quitman, Georgia"
QUITMAN = "QUITMAN CITY COUNCIL MEETING FEB 3, 2026 WITH THE PUBLIC RIGHT TO KNOW    TUESDAY"
QUITMAN_GA = "Quitman, GA. City Council Meeting March 3, 2026 With George Boston Rhynes/The Getto Free Press News."
VALDOSTA = "Valdosta City Council Meeting WORK Session June 4, 2024 With The Getto Free Press.  G.B.R."


def _other(title: str, name: str, jtype: str, state: str = "GA", url: str = "") -> str | None:
    return title_names_other_government(
        title, jurisdiction_name=name, jurisdiction_type=jtype, state_code=state, channel_url=url
    )


# ── #515: City of Bartow FL vs Bartow County GA ─────────────────────────────


def test_city_of_bartow_handle_is_not_bartow_county() -> None:
    url = "https://www.youtube.com/@CityOfBartow"
    assert handle_text(url) == "City Of Bartow"
    # Even with no real title, the handle gives the channel away.
    assert _other("", "Bartow County", "county", url=url) == "names_city_not_county"
    assert _other("City of Bartow", "Bartow County", "county") == "names_city_not_county"


def test_city_of_bartow_fits_the_florida_city() -> None:
    assert _other("City of Bartow", "Bartow", "municipality", "FL") is None
    assert _other("", "Bartow", "municipality", "FL", url="https://www.youtube.com/@CityOfBartow") is None


# ── #514: Brooks County GA commission filed under Gordon / Douglas GA ─────────


@pytest.mark.parametrize("name", ["Gordon", "Douglas"])
def test_brooks_county_commission_is_not_a_city(name: str) -> None:
    assert _other(BROOKS_BOC, name, "municipality") == "names_county_government"


def test_brooks_county_commission_fits_brooks_county() -> None:
    assert _other(BROOKS_BOC, "Brooks County", "county") is None


def test_brooks_county_commission_is_not_another_county() -> None:
    assert _other(BROOKS_BOC, "Gordon County", "county") == "names_other_county"


@pytest.mark.parametrize("title", [QUITMAN, QUITMAN_GA])
def test_quitman_council_is_not_douglas(title: str) -> None:
    assert _other(title, "Douglas", "municipality") == "names_other_city"
    assert _other(title, "Quitman", "municipality") is None


# ── Things that must stay allowed ───────────────────────────────────────────


@pytest.mark.parametrize(
    "title,name,jtype,state",
    [
        ("Tuscaloosa County Commission", "Tuscaloosa County", "county", "AL"),
        ("City of Tuscaloosa", "Tuscaloosa", "municipality", "AL"),
        ("City Commission Meeting - 9/3/2026", "Bartow", "municipality", "FL"),
        ("Special City Commission Meeting - Non-Profits", "Bartow", "municipality", "FL"),
        ("Getto Free Press NEWS G.B.R.", "Douglas", "municipality", "GA"),
        ("Valdosta-Lowndes County GA. Before You Ask For MY VOTE", "Lowndes County", "county", "GA"),
        ("Miami-Dade County Board of County Commissioners", "Miami-Dade County", "county", "FL"),
        ("IN THE COUNTY, IN the city", "Gordon", "municipality", "GA"),
        ("Oregon Village Board 2/1/16", "Oregon", "municipality", "WI"),
        ("June 10, 2024 Nevada City Council meeting", "Nevada", "municipality", "IA"),
    ],
)
def test_titles_naming_the_target_or_nothing_pass(title: str, name: str, jtype: str, state: str) -> None:
    assert _other(title, name, jtype, state) is None


def test_other_state_is_flagged() -> None:
    assert _other("Board of Commissioners, Orange County, FL", "Orange County", "county", "CA") == "names_other_state"


def test_named_governments_keeps_hyphenated_county() -> None:
    named = named_governments("Valdosta-Lowndes County and Miami-Dade County")
    assert named.counties == {"valdosta lowndes", "miami dade"}


# ── Loader: never store the jurisdiction's name as the channel's title ──────


def test_real_channel_title_drops_jurisdiction_name_fallback() -> None:
    assert real_channel_title("Bartow County", "Bartow County") is None
    assert real_channel_title("douglas city", "Douglas city") is None
    assert real_channel_title("Unknown Channel", "Gordon") is None
    assert real_channel_title("", "Gordon") is None
    assert real_channel_title("Getto Free Press NEWS G.B.R.", "Douglas city") == "Getto Free Press NEWS G.B.R."


# ── Video-level consistency (the read-only scan) ────────────────────────────


def test_videos_consistently_naming_other_governments_are_flagged() -> None:
    titles = [BROOKS_BOC, QUITMAN, QUITMAN_GA, VALDOSTA, "Church service Feb 2, 2025"]
    hit = channel_videos_name_other_government(titles, jurisdiction_name="Gordon", jurisdiction_type="municipality", state_code="GA")
    assert hit == (5, 4, 4)


def test_own_meetings_are_not_flagged() -> None:
    titles = ["Amendment 3- City of Bartow", "City Commission Meeting - 11/2/2026", "City of Bartow budget", "City of Bartow PSA"]
    assert channel_videos_name_other_government(
        titles, jurisdiction_name="Bartow", jurisdiction_type="municipality", state_code="FL"
    ) is None
    assert channel_videos_name_other_government(
        titles, jurisdiction_name="Bartow County", jurisdiction_type="county", state_code="GA"
    ) == (4, 3, 3)


# ── Wiring: golden-channel gate and name-search discovery ───────────────────


def _catalog_row(**over: object) -> dict:
    row = {
        "youtube_channel_url": "https://www.youtube.com/@CityOfBartow",
        "youtube_channel_id": "UCEjfi-Q9u3GkMC3TVGC-kcQ",
        # loader fallback: the county's own name, not the YouTube title
        "channel_title": "Bartow County",
        "channel_description": "City Commission meetings",
        "discovery_method": "verified_bronze_event_youtube",
        "official_meeting_confidence": 0.95,
        "back_links_to_jurisdiction_website": False,
    }
    row.update(over)
    return row


def test_gate_rejects_city_handle_for_county_on_name_evidence() -> None:
    from scrapers.discovery.youtube_channel_verification import (
        qualifies_for_bronze_jurisdiction_youtube,
        rejection_reason_for_channel,
    )

    kw = dict(
        jurisdiction_type="county",
        jurisdiction_name="Bartow County",
        jurisdiction_state_code="GA",
        jurisdiction_homepage="http://www.bartowga.org",
    )
    assert not qualifies_for_bronze_jurisdiction_youtube(_catalog_row(), **kw)
    assert rejection_reason_for_channel(_catalog_row(), **kw) == "title_names_other_government"


def test_gate_trusts_a_channel_linked_from_the_jurisdiction_site() -> None:
    from scrapers.discovery.youtube_channel_verification import _names_other_government_without_proof

    kw = dict(jurisdiction_type="county", jurisdiction_name="Bartow County", jurisdiction_state_code="GA")
    assert _names_other_government_without_proof(_catalog_row(), **kw) == "names_city_not_county"
    assert _names_other_government_without_proof(_catalog_row(discovery_method="website_scrape"), **kw) is None
    assert _names_other_government_without_proof(_catalog_row(back_links_to_jurisdiction_website=True), **kw) is None


def test_api_name_search_drops_hits_naming_another_government(monkeypatch: pytest.MonkeyPatch) -> None:
    from scrapers.youtube.youtube_channel_discovery import YouTubeChannelDiscovery

    hits = [
        {"channel_url": "https://www.youtube.com/@CityOfBartow", "channel_id": "UCEjfi-Q9u3GkMC3TVGC-kcQ",
         "channel_title": "City of Bartow", "video_count": 80, "discovery_method": "youtube_api"},
        {"channel_url": "https://www.youtube.com/channel/UCcounty0000000000000", "channel_id": "UCcounty0000000000000",
         "channel_title": "Bartow County Government", "video_count": 40, "discovery_method": "youtube_api"},
    ]

    async def fake_search(self, city_name, state_code):  # noqa: ANN001
        return hits

    monkeypatch.setattr(YouTubeChannelDiscovery, "_generate_handle_patterns", lambda self, *a, **k: [])
    monkeypatch.setattr(YouTubeChannelDiscovery, "_search_youtube_api", fake_search)

    async def run() -> list[dict]:
        d = YouTubeChannelDiscovery(youtube_api_key="test-key")
        try:
            return await d.discover_channels(None, "GA", county_name="Bartow County")
        finally:
            await d.close()

    found = asyncio.run(run())
    assert [c["channel_id"] for c in found] == ["UCcounty0000000000000"]
