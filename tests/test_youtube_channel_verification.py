"""YouTube channel verification and county discovery guards."""

from scrapers.youtube.youtube_channel_discovery import YouTubeChannelDiscovery
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


def test_abington_township_on_lackawanna_county_is_mismatch():
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCVc9zTTGLh7v2kFLOgaLRew",
        "channel_title": "AbingtonTownship",
        "channel_description": (
            "This YouTube channel is dedicated to storing various Board of "
            "Commissioners meetings, community events, and informational videos."
        ),
        "official_meeting_confidence": 0.85,
        "discovery_method": "derived_from_localview",
        "external_links": [{"url": "https://abingtonpa.gov", "title": "Abington Township website"}],
    }
    assert not qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Lackawanna County",
        jurisdiction_state_code="PA",
        jurisdiction_homepage="",
    )


def test_pg_city_on_utah_county_is_mismatch():
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCOuXTzn9eDHmjpfFl4oJ2LA",
        "channel_title": "PG City",
        "channel_description": (
            "Watch live video streams and past videos of the Pleasant Grove City Council Meetings."
        ),
        "official_meeting_confidence": 0.85,
        "discovery_method": "derived_from_localview",
    }
    assert not qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Utah County",
        jurisdiction_state_code="UT",
        jurisdiction_homepage="",
    )


def test_dallas_county_rejects_city_of_selma_even_when_description_mentions_county():
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCUK2CbPoPIa1pqUSBSWiNAQ",
        "channel_title": "City of Selma, Alabama Government",
        "channel_description": "Selma is located in Dallas County of which it is the county seat.",
        "official_meeting_confidence": 0.6,
    }
    assert not qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Dallas County",
        jurisdiction_state_code="AL",
        jurisdiction_homepage="https://selma-al.gov",
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


def test_fulton_fgtv_tv_public_qualifies_with_gov_backlink():
    """FGTV links to fultoncountyga.gov on About — tv-public without meeting boilerplate."""
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCYH7E0jH6HxE-3KTRluH8SQ",
        "channel_title": "FGTV - Fulton Government Television",
        "channel_description": (
            "FGTV's original programming informs citizens about services in Fulton County, "
            "Georgia. www.fultoncountyga.gov"
        ),
        "discovery_method": "website_search",
        "official_meeting_confidence": 0.95,
        "back_links_to_jurisdiction_website": True,
        "external_links": ["https://www.fultoncountyga.gov/"],
    }
    assert qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Fulton County",
        jurisdiction_state_code="GA",
        jurisdiction_homepage="https://www.fultoncountyga.gov",
    )
    assert rejection_reason_for_channel(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Fulton County",
        jurisdiction_state_code="GA",
        jurisdiction_homepage="https://www.fultoncountyga.gov",
    ) is None


def test_dekalb_website_youtube_footer_link_accepted_at_county_general_confidence():
    """BOC page/footer links (website_search) beat county-general purpose bar without manual promotion."""
    row = {
        "youtube_channel_url": "https://www.youtube.com/user/DeKalbCountyGov",
        "channel_title": "DeKalbCountyGov",
        "channel_description": (
            "DeKalb County Television, Channel 23 continues to bring national exposure "
            "and a voice to the many initiatives, programs, services and events of "
            "DeKalb County, Georgia departments."
        ),
        "discovery_method": "website_search",
        "official_meeting_confidence": 0.6,
        "back_links_to_jurisdiction_website": False,
        "external_links": [],
    }
    assert qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="DeKalb County",
        jurisdiction_state_code="GA",
        jurisdiction_homepage="https://dekalbcountyga.gov",
    )
    assert rejection_reason_for_channel(
        row,
        jurisdiction_type="county",
        jurisdiction_name="DeKalb County",
        jurisdiction_state_code="GA",
        jurisdiction_homepage="https://dekalbcountyga.gov",
    ) is None


def test_localview_train_hobby_channel_rejected_for_county():
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCAVu4nbyK-IET2eFc9qqpAQ",
        "channel_title": "Jason Asselin",
        "channel_description": (
            "I have over 145M hits filming trains of the Escanaba & Lake Superior Railroad "
            "in upper Michigan and northern Wisconsin. If you like trains, this railroad "
            "runs mostly vintage equipment on old Milwaukee tracks."
        ),
        "discovery_method": "derived_from_localview",
        "official_meeting_confidence": 0.85,
        "back_links_to_jurisdiction_website": False,
        "external_links": [
            {"url": "https://facebook.com/JasonAsselinsAdventures", "title": "Follow Me on Facebook"},
            {"url": "https://etsy.com/shop/LakeShoreEmberlites", "title": "MY STORE"},
        ],
    }
    assert not qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Dickinson County",
        jurisdiction_state_code="MI",
        jurisdiction_homepage="",
    )
    assert rejection_reason_for_channel(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Dickinson County",
        jurisdiction_state_code="MI",
        jurisdiction_homepage="",
    ) == "non_government_channel"


def test_localview_unknown_without_government_signal_rejected():
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCexample",
        "channel_title": "Random Creator",
        "channel_description": "Music and vlogs from my hometown.",
        "discovery_method": "derived_from_localview",
        "official_meeting_confidence": 0.85,
        "back_links_to_jurisdiction_website": False,
        "external_links": [],
    }
    assert not qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="municipality",
        jurisdiction_name="Example City",
        jurisdiction_state_code="MI",
        jurisdiction_homepage="",
    )


def test_know_pickens_tourism_channel_rejected_for_county():
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCCfgk8u268MtXY7sWUmGA-Q",
        "channel_title": "Pickens County",
        "channel_description": (
            "Get to Know Pickens County in the North Georgia Mountains with videos of "
            "government meetings, parades, concerts, events, pets, animals, awards, "
            "veterans, formal balls, and the people in Jasper, Ga."
        ),
        "discovery_method": "derived_from_localview",
        "official_meeting_confidence": 0.85,
        "back_links_to_jurisdiction_website": False,
        "external_links": [
            {"url": "https://knowpickens.com", "title": "Website"},
            {"url": "https://facebook.com/knowpickens", "title": "Facebook"},
            {"url": "https://tiktok.com/@knowpicken", "title": "TikTok"},
        ],
    }
    assert not qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Pickens County",
        jurisdiction_state_code="GA",
        jurisdiction_homepage="",
    )
    assert rejection_reason_for_channel(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Pickens County",
        jurisdiction_state_code="GA",
        jurisdiction_homepage="",
    ) == "non_government_channel"


def test_localview_county_meeting_channel_still_accepted():
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCCfgk8u268MtXY7sWUmGA-Q",
        "channel_title": "Pickens County",
        "channel_description": "Pickens County commission meeting recordings.",
        "discovery_method": "derived_from_localview",
        "official_meeting_confidence": 0.85,
        "back_links_to_jurisdiction_website": False,
        "external_links": [],
    }
    assert qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Pickens County",
        jurisdiction_state_code="GA",
        jurisdiction_homepage="",
    )


def test_verified_bronze_franklin_cartoon_channel_rejected():
    """Franklin & Friends kids videos mis-tagged as Franklin County AL."""
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCQJ8D7gkhMCqP1qtusqmfgg",
        "channel_title": "Franklin County",
        "channel_description": "",
        "discovery_method": "verified_bronze_event_youtube",
        "official_meeting_confidence": 0.95,
        "back_links_to_jurisdiction_website": False,
    }
    assert not qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Franklin County",
        jurisdiction_state_code="AL",
        jurisdiction_homepage="http://franklincountyal.org/",
    )
    assert (
        rejection_reason_for_channel(
            row,
            jurisdiction_type="county",
            jurisdiction_name="Franklin County",
            jurisdiction_state_code="AL",
            jurisdiction_homepage="http://franklincountyal.org/",
        )
        in ("events_catalog_weak_signal", "channel_purpose_not_meeting_focused")
    )


def test_verified_bronze_county_commission_still_accepted():
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCLaqkkdvi6sYpsncNRiFggg",
        "channel_title": "Houston County Commission - Dothan Al",
        "channel_description": "Houston County Commission meetings",
        "discovery_method": "verified_bronze_event_youtube",
        "official_meeting_confidence": 0.75,
        "back_links_to_jurisdiction_website": False,
    }
    assert qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Houston County",
        jurisdiction_state_code="AL",
        jurisdiction_homepage="",
    )
