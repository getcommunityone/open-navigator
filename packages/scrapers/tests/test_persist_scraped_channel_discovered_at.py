"""#740: persisting a scraped channel id bumps discovered_at for Discover last activity."""

from __future__ import annotations

from unittest.mock import MagicMock

from scrapers.youtube.load_youtube_events_to_postgres import YouTubeEventsLoader


def test_persist_scraped_channel_resolution_bumps_discovered_at() -> None:
    loader = YouTubeEventsLoader.__new__(YouTubeEventsLoader)
    loader.persist_scraped_channel_ids = True
    loader._scraped_channel_id_columns_ready = {
        "bronze.bronze_jurisdictions_counties_scraped"
    }
    loader.conn = MagicMock()
    cursor = MagicMock()
    cursor.rowcount = 1
    loader.conn.cursor.return_value = cursor

    ok = loader.persist_scraped_channel_resolution(
        table="bronze.bronze_jurisdictions_counties_scraped",
        geoid="01001",
        channel_id="UCabcdefghijklmnopqrstuv",
        canonical_url="https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv",
    )

    assert ok is True
    sql = cursor.execute.call_args[0][0]
    assert "discovered_at = NOW()" in sql
    assert "youtube_channel_id" in sql
    loader.conn.commit.assert_called_once()
