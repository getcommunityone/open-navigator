"""Both YouTube loaders set bronze_event_youtube.loaded_at on insert and never on update.

Neither set it before, and the column had no default, so 159,724 of 213,906 rows
(2026-11-16) had no loaded_at.
"""

from __future__ import annotations

import inspect


def _split(sql: str) -> tuple[str, str]:
    insert, _, update = sql.partition("ON CONFLICT")
    return insert, update


def test_ingestion_loader_sets_loaded_at_on_insert_only():
    from ingestion.youtube.events import _UPSERT_YOUTUBE_SQL

    insert, update = _split(str(_UPSERT_YOUTUBE_SQL))
    assert "loaded_at" in insert
    assert "loaded_at =" not in update


def test_catalog_loader_sets_loaded_at_on_insert_only():
    from scrapers.youtube.load_youtube_events_to_postgres import YouTubeEventsLoader

    src = inspect.getsource(YouTubeEventsLoader.insert_events)
    insert, update = _split(src)
    assert "loaded_at" in insert
    assert "loaded_at =" not in update
