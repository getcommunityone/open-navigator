"""#770: Discover runs stamp channel_checked_at on scraped rows, so Last activity moves during a run."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from scrapers.youtube import discover_progress as dp

COUNTIES = "bronze.bronze_jurisdictions_counties_scraped"
MUNIS = "bronze.bronze_jurisdictions_municipalities_scraped"


def _conn(rowcount: int = 1, fetch=None):
    conn = MagicMock()
    cur = MagicMock()
    cur.rowcount = rowcount
    cur.fetchall.return_value = fetch if fetch is not None else [(COUNTIES,), (MUNIS,)]
    conn.cursor.return_value = cur
    return conn, cur


def _sqls(cur) -> list[str]:
    return [c.args[0] for c in cur.execute.call_args_list]


def test_stamp_channel_checked_updates_the_county_row_only():
    conn, cur = _conn(rowcount=1)
    assert dp.stamp_channel_checked(conn, state_code="al", geoid="01031") is True
    update = [s for s in _sqls(cur) if "UPDATE" in s]
    assert len(update) == 1
    assert COUNTIES in update[0] and "channel_checked_at = NOW()" in update[0]
    assert "discovered_at" not in update[0]
    assert cur.execute.call_args_list[-1].args[1] == ("AL", "01031")
    conn.commit.assert_called()


def test_stamp_for_a_jurisdiction_updates_both_tables_through_int_jurisdictions():
    conn, cur = _conn(rowcount=1)
    assert dp.stamp_channel_checked_for_jurisdiction(conn, "county_13223") == 2
    updates = [s for s in _sqls(cur) if "UPDATE" in s]
    assert [t for t in (COUNTIES, MUNIS) if any(t in u for u in updates)] == [COUNTIES, MUNIS]
    assert all("intermediate.int_jurisdictions" in u and "channel_checked_at = NOW()" in u for u in updates)
    assert all("discovered_at" not in u for u in updates)


def test_a_failed_stamp_warns_and_never_raises():
    conn, cur = _conn()
    cur.execute.side_effect = RuntimeError("lock timeout")
    assert dp.stamp_channel_checked(conn, state_code="AL", geoid="01031") is False
    assert dp.stamp_channel_checked_for_jurisdiction(conn, "county_01031") == 0
    conn.rollback.assert_called()


def test_the_column_is_added_only_when_missing():
    conn, cur = _conn(fetch=[(COUNTIES,)])  # municipalities lacks the column
    dp._COLUMN_READY.clear()
    dp.ensure_channel_checked_column(conn)
    alters = [s for s in _sqls(cur) if "ALTER TABLE" in s]
    assert len(alters) == 1 and MUNIS in alters[0]
    assert "ADD COLUMN IF NOT EXISTS channel_checked_at" in alters[0]


def test_discover_channels_reports_every_county_tried(monkeypatch):
    from scrapers.youtube import load_missing_county_channels as lmc

    class FakeDiscovery:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def discover_channels(self, **kw):
            if kw["county_name"] == "Bad County":
                raise RuntimeError("site down")
            return []

    monkeypatch.setattr(lmc, "YouTubeChannelDiscovery", FakeDiscovery)
    rows = [
        {"jurisdiction_id": "county_01031", "geoid": "01031", "county_name": "Coffee County"},
        {"jurisdiction_id": "county_01999", "geoid": "01999", "county_name": "Bad County"},
    ]
    seen: list[str] = []
    out = asyncio.run(
        lmc.discover_channels(rows, "AL", skip_homepage_scrape=True, on_checked=lambda r: seen.append(r["geoid"]))
    )
    assert seen == ["01031", "01999"]
    assert len(out) == 2


def test_a_failing_callback_does_not_stop_discovery(monkeypatch):
    from scrapers.youtube import load_missing_county_channels as lmc

    class FakeDiscovery:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def discover_channels(self, **kw):
            return []

    def boom(row):
        raise RuntimeError("db gone")

    monkeypatch.setattr(lmc, "YouTubeChannelDiscovery", FakeDiscovery)
    rows = [{"jurisdiction_id": "county_01031", "geoid": "01031", "county_name": "Coffee County"}]
    assert len(asyncio.run(lmc.discover_channels(rows, "AL", skip_homepage_scrape=True, on_checked=boom))) == 1


@pytest.mark.parametrize("outcome", ["rows", "noop", "error"])
def test_the_per_county_load_stamps_whatever_happens(monkeypatch, outcome):
    from scrapers.youtube import load_youtube_for_jurisdiction as lyj

    stamped: list[str] = []
    monkeypatch.setattr(lyj, "stamp_channel_checked_for_jurisdiction", lambda conn, jid: stamped.append(jid) or 1)
    loader = MagicMock()
    if outcome == "error":
        loader.process_jurisdiction.side_effect = RuntimeError("yt-dlp failed")
    else:
        loader.process_jurisdiction.return_value = 79 if outcome == "rows" else 0
    jurisdiction = {"jurisdiction_id": "county_13223"}
    if outcome == "error":
        with pytest.raises(RuntimeError):
            lyj.load_and_stamp(loader, jurisdiction)
    else:
        assert lyj.load_and_stamp(loader, jurisdiction) == (79 if outcome == "rows" else 0)
    assert stamped == ["county_13223"]
