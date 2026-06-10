"""Tests for remapping city YouTube channels off counties."""

from scripts.discovery.youtube_city_channel_remap import (
    _pick_best_place_match,
    parse_municipality_name_from_channel,
    parse_place_kind_from_channel,
    _handle_to_place_name,
)
from scrapers.discovery.youtube_channel_verification import (
    _looks_like_city_channel_for_county,
)


def test_parse_town_name_from_title():
    row = {"channel_title": "Town of Nantucket", "youtube_channel_url": "https://youtube.com/x"}
    assert parse_municipality_name_from_channel(row) == "Nantucket"
    assert parse_place_kind_from_channel(row) == "town"


def test_pick_nantucket_town_over_cdp():
    hits = [
        {
            "jurisdiction_id": "nantucket_2543755",
            "name": "Nantucket CDP",
            "jurisdiction_type": "municipality",
            "website_url": "",
        },
        {
            "jurisdiction_id": "nantucket_2501943790",
            "name": "Nantucket town",
            "jurisdiction_type": "township",
            "website_url": "https://nantucket-ma.gov",
        },
    ]
    picked = _pick_best_place_match(
        hits,
        place_kind="town",
        channel_title="Town of Nantucket",
    )
    assert picked is not None
    assert picked["jurisdiction_id"] == "nantucket_2501943790"


def test_nantucket_town_channel_is_county_mismatch():
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UC-sgxA1fdoxteLNzRAUHIxA",
        "channel_title": "Town of Nantucket",
        "channel_description": "Nantucket Government TV ... town meetings ...",
    }
    assert _looks_like_city_channel_for_county(row, jurisdiction_name="Nantucket County")


def test_parse_city_name_from_title():
    row = {"channel_title": "City of Dothan AL", "youtube_channel_url": "https://youtube.com/x"}
    assert parse_municipality_name_from_channel(row) == "Dothan"


def test_parse_city_name_from_title_with_suffix():
    row = {
        "channel_title": "City of Selma, Alabama Government",
        "youtube_channel_url": "https://youtube.com/x",
    }
    assert parse_municipality_name_from_channel(row) == "Selma"


def test_parse_city_name_from_handle():
    row = {
        "channel_title": "",
        "youtube_channel_url": "https://www.youtube.com/user/cityofboston",
    }
    assert parse_municipality_name_from_channel(row) == "Boston"


def test_handle_to_place_name_camel_case():
    assert _handle_to_place_name("CityOfDothan") == "Dothan"


def test_houston_county_dothan_is_mismatch():
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCjQLzllGnzicLNiMMzcLwKQ",
        "channel_title": "City of Dothan AL",
        "channel_description": "Welcome to the City of Dothan Youtube Channel.",
    }
    assert _looks_like_city_channel_for_county(row, jurisdiction_name="Houston County")


def test_covington_county_cityof_compact_title_is_mismatch():
    """``cityofcovington`` must not stick to Covington County (city handle, not county)."""
    row = {
        "youtube_channel_url": "https://www.youtube.com/@cityofcovington",
        "channel_title": "cityofcovington",
        "channel_description": "City of Covington, Alabama",
    }
    assert _looks_like_city_channel_for_county(row, jurisdiction_name="Covington County")
    assert parse_municipality_name_from_channel(row) == "Covington"


def test_houston_county_commission_not_mismatch():
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCLaqkkdvi6sYpsncNRiFggg",
        "channel_title": "Houston County Commission - Dothan Al",
        "channel_description": "Houston County Commission meetings",
    }
    assert not _looks_like_city_channel_for_county(row, jurisdiction_name="Houston County")
