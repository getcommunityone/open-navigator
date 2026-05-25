"""Tests for int YouTube channel metadata cache helpers."""

from scripts.discovery.int_youtube_channel_metadata import (
    _norm_channel_id,
    row_needs_youtube_metadata_refresh,
    values_from_enriched_metadata,
)


def test_norm_channel_id_accepts_uc_only():
    assert _norm_channel_id("UCabc123def456") == "UCabc123def456"
    assert _norm_channel_id("@CityOfFoo") is None
    assert _norm_channel_id("") is None


def test_row_needs_refresh_when_channel_id_or_description_missing():
    assert row_needs_youtube_metadata_refresh({"youtube_channel_id": "", "channel_description": "x"})
    assert row_needs_youtube_metadata_refresh(
        {"youtube_channel_id": "UCabc", "channel_description": "", "channel_title": "City of Foo"}
    )
    assert not row_needs_youtube_metadata_refresh(
        {
            "youtube_channel_id": "UCabc123def456789012",
            "channel_title": "City of Foo",
            "channel_description": "Official meetings",
            "subscriber_count": 100,
            "video_count": 10,
            "view_count": 5000,
            "latest_upload": "2026-01-01",
        }
    )


def test_values_from_enriched_metadata_prefers_scrape_fields():
    values = values_from_enriched_metadata(
        {
            "youtube_channel_id": "UCnew123456789012345",
            "channel_title": "City of Example",
            "channel_description": "Official channel",
            "subscriber_count": 42,
            "video_count": 7,
            "view_count": 9001,
            "latest_upload": "2026-05-01T12:00:00Z",
            "external_links": ["https://example.gov"],
            "jurisdiction_website_back_links": ["https://example.gov/meetings"],
            "back_links_to_jurisdiction_website": True,
            "official_meeting_confidence": 0.9,
        },
        {"youtube_channel_id": "UCold", "channel_title": "Home"},
    )
    assert values["youtube_channel_id"] == "UCnew123456789012345"
    assert values["channel_title"] == "City of Example"
    assert values["latest_upload"] == "2026-05-01"
    assert values["back_links_to_jurisdiction_website"] is True
    assert values["jurisdiction_website_back_links"] == ["https://example.gov/meetings"]
