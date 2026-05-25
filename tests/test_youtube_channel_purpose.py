"""Tests for YouTube channel purpose classification."""

from scripts.discovery.youtube_channel_purpose import (
    classify_channel_purpose,
    has_meeting_purpose_signal,
    is_tv_public_channel,
)
from scripts.discovery.youtube_channel_verification import (
    qualifies_for_bronze_jurisdiction_youtube,
    rejection_reason_for_channel,
)


def test_county_meeting_channel():
    purpose = classify_channel_purpose(
        channel_title="Adams County, Indiana Government",
        channel_description="Adams County Government's YouTube channel, to broadcast public meetings.",
        jurisdiction_type="county",
    )
    assert purpose == "county-meeting"


def test_county_general_channel():
    purpose = classify_channel_purpose(
        channel_title="Walton County Georgia Government",
        channel_description="Providing information and news about services, programs and events for our citizens.",
        jurisdiction_type="county",
    )
    assert purpose == "county-general"


def test_tv_public_channel():
    assert is_tv_public_channel("inSpalding TV", "department highlights for citizens")
    purpose = classify_channel_purpose(
        channel_title="Marion County TV news & events",
        channel_description="Marion County Alabama, local news and events.",
        jurisdiction_type="county",
    )
    assert purpose == "tv-public"


def test_county_general_rejected_without_meeting_signal():
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCexample",
        "channel_title": "Walton County Georgia Government",
        "channel_description": "News about services, programs and events for citizens.",
        "discovery_method": "website_search",
        "official_meeting_confidence": 0.9,
        "back_links_to_jurisdiction_website": True,
        "channel_purpose": "county-general",
    }
    assert not qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Walton County",
        jurisdiction_state_code="GA",
        jurisdiction_homepage="https://waltoncountyga.gov",
    )
    assert (
        rejection_reason_for_channel(
            row,
            jurisdiction_type="county",
            jurisdiction_name="Walton County",
            jurisdiction_state_code="GA",
            jurisdiction_homepage="https://waltoncountyga.gov",
        )
        == "channel_purpose_not_meeting_focused"
    )


def test_tv_public_with_meetings_can_qualify_at_high_confidence():
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCexample",
        "channel_title": "Boston City TV",
        "channel_description": "Live and broadcast town meetings and board meetings.",
        "discovery_method": "website_search",
        "official_meeting_confidence": 0.9,
        "back_links_to_jurisdiction_website": True,
        "channel_purpose": "tv-public",
    }
    assert has_meeting_purpose_signal(row["channel_title"], row["channel_description"])
    assert qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Suffolk County",
        jurisdiction_state_code="MA",
        jurisdiction_homepage="https://boston.gov",
    )


def test_county_meeting_qualifies_at_default_threshold():
    row = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCexample",
        "channel_title": "Miller County Government - Georgia",
        "channel_description": "Official channel for Miller County Board of Commissioners meetings.",
        "discovery_method": "website_search",
        "official_meeting_confidence": 0.7,
        "back_links_to_jurisdiction_website": True,
        "channel_purpose": "county-meeting",
    }
    assert qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type="county",
        jurisdiction_name="Miller County",
        jurisdiction_state_code="GA",
        jurisdiction_homepage="https://millercountyga.gov",
    )
