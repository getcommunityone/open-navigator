"""Tests for remapping city YouTube channels off counties."""

from scripts.discovery.youtube_city_channel_remap import (
    parse_municipality_name_from_channel,
    _handle_to_place_name,
)
from scripts.discovery.youtube_channel_verification import (
    _looks_like_city_channel_for_county,
)


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


def test_houston_county_commission_not_mismatch():
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCLaqkkdvi6sYpsncNRiFggg",
        "channel_title": "Houston County Commission - Dothan Al",
        "channel_description": "Houston County Commission meetings",
    }
    assert not _looks_like_city_channel_for_county(row, jurisdiction_name="Houston County")
