"""Discover write-through to bronze (#695)."""

from __future__ import annotations

from unittest.mock import MagicMock

from scrapers.youtube.load_missing_county_channels import (
    DISCOVER_UNREVIEWED_METHOD,
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
    assert params[2] == DISCOVER_UNREVIEWED_METHOD
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
