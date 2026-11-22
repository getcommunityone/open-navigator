"""Discover write-through to bronze + Jev gate (#695, #697)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from scrapers.youtube.load_missing_county_channels import (
    DISCOVER_JEV_METHOD,
    channel_gate_reject_reason,
    evaluate_discover_for_bronze,
    persist_discovered_channel_to_bronze,
)


def test_persist_discovered_channel_updates_empty_scraped_row():
    conn = MagicMock()
    cur = MagicMock()
    cur.rowcount = 1
    conn.cursor.return_value.__enter__.return_value = cur

    ok = persist_discovered_channel_to_bronze(
        conn,
        {
            "geoid": "37003",
            "jurisdiction_id": "alexander_37003",
            "channel_id": "UCROYv-P7pqmMxR3jCCJQSmw",
            "channel_url": "https://www.youtube.com/@alexandercountync",
            "policy_score": "0.42",
        },
        state_code="NC",
    )

    assert ok is True
    sql = cur.execute.call_args[0][0]
    params = cur.execute.call_args[0][1]
    assert "UPDATE bronze.bronze_jurisdictions_counties_scraped" in sql
    assert "discovered_at = NOW()" in sql
    assert params[0] == "UCROYv-P7pqmMxR3jCCJQSmw"
    assert params[2] == DISCOVER_JEV_METHOD
    assert params[3] == 0.42
    assert params[5] == "37003"
    assert params[6] == "NC"
    conn.commit.assert_called_once()


def test_persist_discovered_channel_skips_without_channel_id():
    conn = MagicMock()
    assert (
        persist_discovered_channel_to_bronze(
            conn,
            {"geoid": "37003", "channel_id": "", "channel_url": ""},
            state_code="NC",
        )
        is False
    )
    conn.cursor.assert_not_called()


def test_persist_discovered_channel_builds_url_from_id():
    conn = MagicMock()
    cur = MagicMock()
    cur.rowcount = 1
    conn.cursor.return_value.__enter__.return_value = cur

    persist_discovered_channel_to_bronze(
        conn,
        {"geoid": "37087", "channel_id": "UCxxxxxxxxxxxxxxxxxxx", "channel_url": ""},
        state_code="NC",
    )
    params = cur.execute.call_args[0][1]
    assert params[1] == "https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxx"


def test_channel_gate_rejects_other_government_api_hit():
    reason = channel_gate_reject_reason(
        {
            "discovery_method": "youtube_api",
            "channel_title": "City of Bartow Florida Official",
            "county_name": "Bartow County",
            "channel_url": "https://www.youtube.com/@CityOfBartow",
        },
        state_code="GA",
    )
    assert reason is not None


def test_channel_gate_allows_website_scrape():
    assert (
        channel_gate_reject_reason(
            {
                "discovery_method": "website_scrape",
                "channel_title": "Anything",
                "county_name": "Haywood County",
            },
            state_code="NC",
        )
        is None
    )


def test_evaluate_accepts_when_jev_keep_above_threshold():
    row = {
        "channel_id": "UCxxxxxxxxxxxxxxxxxxx",
        "channel_title": "Haywood County Government",
        "county_name": "Haywood County",
        "discovery_method": "website_scrape",
        "channel_url": "https://www.youtube.com/c/HaywoodCountyGovernment",
    }
    with (
        patch(
            "scrapers.youtube.load_missing_county_channels.fetch_newest_channel_upload",
            return_value={
                "video_id": "abcdefghijk",
                "title": "County Commissioners Meeting",
                "description": "Agenda",
            },
        ),
        patch(
            "scrapers.youtube.load_missing_county_channels.jev_meta_keep_for_upload",
            return_value=(0.85, "abcdefghijk"),
        ),
    ):
        ok, reason, keep_p = evaluate_discover_for_bronze(
            row, state_code="NC", youtube_api_key="fake",
        )
    assert ok is True
    assert keep_p == 0.85
    assert reason.startswith("jev_ok:")


def test_evaluate_rejects_when_jev_keep_below_threshold():
    row = {
        "channel_id": "UCxxxxxxxxxxxxxxxxxxx",
        "channel_title": "Random Channel",
        "county_name": "Haywood County",
        "discovery_method": "website_scrape",
    }
    with (
        patch(
            "scrapers.youtube.load_missing_county_channels.fetch_newest_channel_upload",
            return_value={"video_id": "abcdefghijk", "title": "Vlog", "description": ""},
        ),
        patch(
            "scrapers.youtube.load_missing_county_channels.jev_meta_keep_for_upload",
            return_value=(0.1, "abcdefghijk"),
        ),
    ):
        ok, reason, keep_p = evaluate_discover_for_bronze(
            row, state_code="NC", youtube_api_key="fake", min_meeting_p=0.6,
        )
    assert ok is False
    assert keep_p == 0.1
    assert "jev_below_threshold" in reason
