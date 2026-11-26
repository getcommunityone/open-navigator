"""The YouTube loader never stores a jurisdiction id as jurisdiction_name (#501).

Chilton County AL showed on the site as ``chilton_01021`` / ``c-AL-01021``: the
loader wrote ``COALESCE(j.name, s.jurisdiction_id)`` and the bronze fallback source
copied that id forward on every refresh. No database, no YouTube calls.
"""

from __future__ import annotations

import inspect
import re

import pytest

from scrapers.youtube.load_youtube_events_to_postgres import (
    YouTubeEventsLoader,
    display_jurisdiction_name,
    is_id_shaped_jurisdiction_name,
)


@pytest.mark.parametrize(
    "name",
    ["chilton_01021", "c-AL-01021", "c-WA-53015", "clanton_0102190603", "arab_0102116"],
)
def test_id_shapes_are_detected(name):
    assert is_id_shaped_jurisdiction_name(name)
    assert display_jurisdiction_name(name, "chilton_01021") is None


@pytest.mark.parametrize(
    "name",
    ["Chilton County", "Arab", "Winston-Salem", "District 9", "Town of Hull", "Lowndes County School District"],
)
def test_real_names_pass_through(name):
    assert not is_id_shaped_jurisdiction_name(name)
    assert display_jurisdiction_name(f"  {name} ", "chilton_01021") == name


def test_blank_or_equal_to_id_is_none():
    assert display_jurisdiction_name(None, "x_01021") is None
    assert display_jurisdiction_name("   ", "x_01021") is None
    # Equal to the id even when the id has an unusual shape.
    assert display_jurisdiction_name("AL", "AL") is None


def test_scraped_channel_queries_do_not_fall_back_to_the_id():
    for fn in (
        YouTubeEventsLoader.get_jurisdictions_from_counties_scraped,
        YouTubeEventsLoader.get_jurisdictions_from_municipalities_scraped,
    ):
        src = inspect.getsource(fn)
        assert "COALESCE(j.name, s.jurisdiction_id)" not in src
        assert "j.name AS jurisdiction_name" in src


class _FakeLoader(YouTubeEventsLoader):
    """process_jurisdiction with every DB / network step stubbed out."""

    def __init__(self):  # noqa: D401 - no DB connection
        self.upserted: list[dict] = []
        self.records: list[dict] = []

    def extract_channel_ids(self, channels, trust_catalog=False):
        return [{"channel_id": "UCiOI7RWQKqnEuM3AKnWYLuA", "channel_type": "county"}]

    def upsert_channel(self, **kwargs):
        self.upserted.append(kwargs)


def test_process_jurisdiction_nulls_an_id_name_and_logs(monkeypatch):
    loader = _FakeLoader()
    seen_names: list = []

    def stop_after_name(*args, **kwargs):
        seen_names.append(kwargs.get("jurisdiction_name"))
        raise RuntimeError("stop")  # nothing past the channel upsert is needed

    monkeypatch.setattr(loader, "upsert_channel", stop_after_name)
    warnings: list[str] = []
    from loguru import logger

    sink = logger.add(lambda m: warnings.append(str(m)), level="WARNING")
    try:
        with pytest.raises(RuntimeError, match="stop"):
            loader.process_jurisdiction(
                {
                    "jurisdiction_id": "chilton_01021",
                    "jurisdiction_name": "c-AL-01021",  # carried forward from bronze
                    "state_code": "AL",
                    "state": "Alabama",
                    "jurisdiction_type": "county",
                    "youtube_channels": [],
                }
            )
    finally:
        logger.remove(sink)
    assert seen_names == [None]
    assert any("chilton_01021" in w and "NULL" in w for w in warnings)


def test_video_record_with_null_name_does_not_crash_for_cities():
    loader = YouTubeEventsLoader.__new__(YouTubeEventsLoader)
    rec = loader.video_to_event_record(
        video={"video_id": "abc", "title": "Council Meeting 9/23/2024"},
        jurisdiction_id="x_0100001",
        jurisdiction_name=None,
        jurisdiction_type="city",
        state_code="AL",
        state="Alabama",
        channel_id="UCx",
    )
    assert rec["jurisdiction_name"] is None and rec["city"] is None


def test_upsert_keeps_real_name_but_drops_an_id_shaped_one():
    src = inspect.getsource(YouTubeEventsLoader.insert_events)
    update = src.partition("ON CONFLICT")[2]
    assert "jurisdiction_name = EXCLUDED.jurisdiction_name," not in update
    # #778 wraps the geo columns in CASE WHEN <keep other place> ... ELSE <rule> END.
    assert re.search(
        r"jurisdiction_name = (CASE WHEN \{keep\} THEN y\.jurisdiction_name ELSE )?COALESCE\(\s*EXCLUDED\.jurisdiction_name",
        update,
    )
    # Braces are doubled in the source because the query is a str.format template.
    assert re.search(r"'\^c-\[A-Z\]\{\{?2\}?\}-\[0-9\]\+\$'", update)
