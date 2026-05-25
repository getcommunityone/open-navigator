"""Tests for LocalView → bronze_jurisdiction_youtube sync."""

from scripts.discovery.sync_bronze_jurisdiction_youtube_from_localview import _build_row


def test_build_row_marks_localview_derived_as_verified():
    row = _build_row(
        {
            "channel_id": "UCabc123",
            "channel_url": "https://www.youtube.com/channel/UCabc123",
            "channel_title": "Mobile County Commission Meetings",
            "channel_description": "Official commission meeting recordings and livestreams.",
            "subscriber_count": 100,
            "video_count": 50,
            "view_count": 1000,
            "discovery_method": "derived_from_localview",
            "confidence_score": 0.85,
            "channel_external_links": [],
            "jurisdiction_id": "mobile_01097",
            "jurisdiction_name": "Mobile County",
            "state_code": "AL",
            "jurisdiction_type": "county",
            "website_url": "https://www.mobilecountyal.gov",
        }
    )
    assert row["is_verified"] is True
    assert row["discovery_method"] == "derived_from_localview"
    assert row["channel_purpose"] == "county-meeting"
    assert row["source"] == "localview"


def test_build_row_tv_public_without_meeting_signal_not_verified():
    row = _build_row(
        {
            "channel_id": "UCtv999",
            "channel_url": "https://www.youtube.com/channel/UCtv999",
            "channel_title": "County Government TV",
            "channel_description": "Government programming 24 hours a day.",
            "discovery_method": "derived_from_localview",
            "confidence_score": 0.85,
            "channel_external_links": [],
            "jurisdiction_id": "example_01001",
            "jurisdiction_name": "Example County",
            "state_code": "AL",
            "jurisdiction_type": "county",
            "website_url": None,
        }
    )
    assert row["channel_purpose"] == "tv-public"
    assert row["is_verified"] is False
    assert row["rejection_reason"] == "channel_purpose_not_meeting_focused"
