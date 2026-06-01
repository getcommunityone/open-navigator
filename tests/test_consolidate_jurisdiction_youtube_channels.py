"""Consolidate merge helpers."""

from __future__ import annotations

from scripts.discovery.consolidate_jurisdiction_youtube_channels import (
    _merge_channel,
    _payload_from_row,
)


def test_merge_channel_prefers_higher_confidence():
    by: dict = {}
    row = {"jurisdiction_id": "boston_2507000", "state_code": "MA"}
    low = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCaaa",
        "official_meeting_confidence": 0.55,
    }
    high = {
        "youtube_channel_url": "https://www.youtube.com/channel/UCaaa",
        "official_meeting_confidence": 0.9,
        "youtube_channel_id": "UCaaa",
    }
    _merge_channel(by, row, low)
    _merge_channel(by, row, high)
    assert by["boston_2507000"][0]["official_meeting_confidence"] == 0.9


def test_payload_from_row_verified_bronze():
    out = _payload_from_row(
        {
            "youtube_channel_url": "https://www.youtube.com/channel/UCx",
            "youtube_channel_id": "UCx",
            "discovery_method": "verified_bronze_event_youtube",
            "official_meeting_confidence": 0.5,
        },
        default_primary=True,
    )
    assert out is not None
    assert out["official_meeting_confidence"] >= 0.55
    assert out["is_primary"] is True
