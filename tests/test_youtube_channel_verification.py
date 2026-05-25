"""YouTube channel verification and county discovery guards."""

from scripts.datasources.youtube.youtube_channel_discovery import YouTubeChannelDiscovery
from scripts.discovery.youtube_channel_verification import (
    qualifies_for_bronze_jurisdiction_youtube,
    rejection_reason_for_channel,
)


def test_county_handle_patterns_skip_city_templates():
    yt = YouTubeChannelDiscovery()
    county_only = yt._generate_handle_patterns(
        "Appling County",
        "GA",
        "Appling County",
        include_city_patterns=False,
    )
    assert "CityOfAppling" not in county_only
    assert "ApplingCounty" in county_only
    assert "CityOfBaxley" not in county_only


def test_appling_baxley_city_channel_rejected_for_county():
    row = {
        "youtube_channel_url": "https://www.youtube.com/@CityOfBaxley",
        "channel_title": "Videos",
        "channel_description": "Share your videos with friends, family, and the world",
        "discovery_method": "pattern_match",
        "official_meeting_confidence": 0.0,
        "back_links_to_jurisdiction_website": False,
        "external_links": [],
    }
    reason = rejection_reason_for_channel(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Appling County",
        jurisdiction_state_code="GA",
        jurisdiction_homepage="https://applingcounty.gov",
    )
    assert reason is not None
    assert not qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Appling County",
        jurisdiction_state_code="GA",
        jurisdiction_homepage="https://applingcounty.gov",
    )


def test_bacon_city_pattern_rejected_for_county():
    row = {
        "youtube_channel_url": "https://www.youtube.com/@BaconCity",
        "channel_title": "Home",
        "channel_description": "",
        "discovery_method": "pattern_match",
        "official_meeting_confidence": 0.5,
        "back_links_to_jurisdiction_website": False,
        "external_links": [],
    }
    assert not qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Bacon County",
        jurisdiction_state_code="GA",
        jurisdiction_homepage="https://baconcounty.org",
    )


def test_houston_county_rejects_city_of_dothan_channel():
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCjQLzllGnzicLNiMMzcLwKQ",
        "channel_title": "City of Dothan AL",
        "channel_description": "Welcome to the City of Dothan Youtube Channel.",
        "discovery_method": "youtube_api",
        "official_meeting_confidence": 0.7,
        "back_links_to_jurisdiction_website": False,
    }
    assert not qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Houston County",
        jurisdiction_state_code="AL",
        jurisdiction_homepage="https://houstoncosoal.gov",
    )
    assert (
        rejection_reason_for_channel(
            row,
            jurisdiction_type="county",
            jurisdiction_name="Houston County",
            jurisdiction_state_code="AL",
            jurisdiction_homepage="https://houstoncosoal.gov",
        )
        == "county_city_channel_mismatch"
    )


def test_houston_county_keeps_county_commission_channel():
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCLaqkkdvi6sYpsncNRiFggg",
        "channel_title": "Houston County Commission - Dothan Al",
        "channel_description": "Houston County Commission meetings",
        "discovery_method": "website_search",
        "official_meeting_confidence": 0.8,
        "back_links_to_jurisdiction_website": True,
    }
    assert qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Houston County",
        jurisdiction_state_code="AL",
        jurisdiction_homepage="https://houstoncosoal.gov",
    )


def test_website_search_channel_accepted_with_backlink():
    row = {
        "youtube_channel_url": "https://www.youtube.com/@CamdenCountyBOC",
        "channel_title": "Camden County Board of Commissioners",
        "channel_description": "Official meetings for Camden County, Georgia",
        "discovery_method": "website_search",
        "official_meeting_confidence": 1.0,
        "back_links_to_jurisdiction_website": True,
        "external_links": ["https://www.camden county.gov"],
    }
    assert qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Camden County",
        jurisdiction_state_code="GA",
        jurisdiction_homepage="https://www.camden county.gov",
    )
