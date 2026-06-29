"""Unit tests for the LocalView events pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pandas as pd
import pytest

from ingestion.localview.events import (  # noqa: E402
    LocalviewEventRow,
    LocalviewEventsPipeline,
    find_parquet_files,
    get_state_abbrev,
    infer_jurisdiction_type,
    row_to_event,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _write_parquet(path, records: list[dict]):
    pd.DataFrame(records).to_parquet(path)
    return path


def test_infer_jurisdiction_type_maps_and_defaults():
    assert infer_jurisdiction_type("County Commission") == "county"
    assert infer_jurisdiction_type("school board") == "school_district"
    # Unknown but present govt strings default to "city".
    assert infer_jurisdiction_type("Some Random Board") == "city"
    # Missing / NaN govt -> "unknown".
    assert infer_jurisdiction_type(None) == "unknown"
    assert infer_jurisdiction_type(float("nan")) == "unknown"


def test_get_state_abbrev_known_and_fallback():
    assert get_state_abbrev("California") == "CA"
    assert get_state_abbrev("Texas") == "TX"
    # Unknown name -> first two chars uppercased.
    assert get_state_abbrev("Freedonia") == "FR"
    assert get_state_abbrev(float("nan")) is None


def test_row_to_event_builds_expected_fields():
    row = pd.Series({
        "meeting_date": "2023-05-10",
        "vid_id": "abc123",
        "state_name": "California",
        "place_name": "Springfield",
        "place_govt": "City Commission",
        "vid_title": "Council Meeting",
        "channel_id": "chan1",
    })
    event = row_to_event(row)
    assert event["datasource_id"] == "abc123"
    assert event["video_url"] == "https://www.youtube.com/watch?v=abc123"
    assert event["state_code"] == "CA"
    assert event["jurisdiction_type"] == "city"
    assert event["datasource"] == "localview"
    assert event["title"] == "Council Meeting"


def test_row_to_event_synthesizes_title_when_missing():
    row = pd.Series({
        "meeting_date": "2023-05-10",
        "vid_id": "xyz",
        "state_name": "Texas",
        "place_name": "Austin",
        "place_govt": "City Council",
        "vid_title": None,
    })
    event = row_to_event(row)
    assert event["title"].startswith("Austin Meeting - ")


def test_row_schema_accepts_minimal_valid_row():
    r = LocalviewEventRow(
        source="localview_events",
        source_version="meetings.2023",
        natural_key="abc123",
        datasource_id="abc123",
        datasource="localview",
        state_code="CA",
    )
    assert r.datasource_id == "abc123"
    assert r.state_code == "CA"
    assert r.vid_views is None


def test_row_schema_rejects_missing_datasource_id():
    # datasource_id is the upsert key and required (min_length=1).
    with pytest.raises(Exception):
        LocalviewEventRow(
            source="localview_events",
            source_version="v",
            natural_key="x",
            datasource_id="",
        )
    # state_code is capped at 2 chars.
    with pytest.raises(Exception):
        LocalviewEventRow(
            source="localview_events",
            source_version="v",
            natural_key="x",
            datasource_id="abc",
            state_code="CAL",
        )


def test_pipeline_metadata():
    p = LocalviewEventsPipeline()
    assert p.source == "localview_events"
    assert p.batch_size == 1000
    assert p.row_schema is LocalviewEventRow


def test_find_parquet_files_raises_when_missing(tmp_path, monkeypatch):
    import ingestion.localview.events as ev
    monkeypatch.setattr(ev, "CACHE_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        find_parquet_files()


def test_find_parquet_files_filters_by_year(tmp_path, monkeypatch):
    import ingestion.localview.events as ev
    monkeypatch.setattr(ev, "CACHE_DIR", tmp_path)
    (tmp_path / "meetings.2022.parquet").write_text("")
    (tmp_path / "meetings.2023.parquet").write_text("")
    files = find_parquet_files(year=2023)
    assert [f.name for f in files] == ["meetings.2023.parquet"]


def test_extract_roundtrip_and_validation(tmp_path):
    path = tmp_path / "meetings.2023.parquet"
    _write_parquet(path, [
        {  # valid
            "meeting_date": "2023-01-15", "vid_id": "vid1", "state_name": "California",
            "place_name": "Oakland", "place_govt": "County Commission",
            "vid_title": "Board Meeting", "channel_id": "chanA", "channel_title": "Oakland TV",
        },
        {  # missing vid_id -> dropped
            "meeting_date": "2023-02-15", "vid_id": None, "state_name": "Texas",
            "place_name": "Dallas", "place_govt": "City Council",
            "vid_title": "X", "channel_id": "chanB", "channel_title": "Dallas TV",
        },
        {  # missing meeting_date -> dropped
            "meeting_date": None, "vid_id": "vid3", "state_name": "Ohio",
            "place_name": "Columbus", "place_govt": "School Board",
            "vid_title": "Y", "channel_id": "chanC", "channel_title": "Columbus TV",
        },
    ])
    p = LocalviewEventsPipeline(path=path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 1
    raw = extracted[0]
    assert raw["source"] == "localview_events"
    assert raw["source_version"] == "meetings.2023"
    assert raw["natural_key"] == "vid1"
    assert raw["datasource_id"] == "vid1"
    assert raw["state_code"] == "CA"
    assert raw["jurisdiction_type"] == "county"
    assert raw["channel_id"] == "chanA"

    # Extracted rows validate cleanly against the schema.
    row = p.validate(raw)
    assert row is not None
    assert row.datasource_id == "vid1"


def test_extract_respects_limit(tmp_path):
    path = tmp_path / "meetings.2024.parquet"
    _write_parquet(path, [
        {
            "meeting_date": "2024-03-01", "vid_id": f"vid{i}", "state_name": "Texas",
            "place_name": f"City{i}", "place_govt": "City Council",
            "vid_title": f"Meeting {i}", "channel_id": f"chan{i}", "channel_title": "TV",
        }
        for i in range(10)
    ])
    p = LocalviewEventsPipeline(path=path, limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3


"""Case 10 -- Extended offline tests for ingestion.localview.events.

Supplements the existing test_localview_events_pipeline.py with focused tests
for:
  - extract() field-level correctness and schema round-trip
  - row_to_event: title synthesis, ACS float passthrough, null tolerances
  - _row_to_channel_mapping edge-cases (NaN vid/channel, trimming)
  - get_state_abbrev: full name, fallback, NaN
  - infer_jurisdiction_type: all known types, unknown, NaN
  - find_parquet_files: year filter, multi-year glob, missing dir
  - LocalviewEventRow schema: missing/blank datasource_id, state_code cap
  - extract() deduplication: same parquet path, limit boundary

No database sessions are opened; extract() is driven directly.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from core_lib.pipeline.schemas import PipelineContext
from ingestion.localview.events import (
    LocalviewEventRow,
    LocalviewEventsPipeline,
    _row_to_channel_mapping,
    find_parquet_files,
    get_state_abbrev,
    infer_jurisdiction_type,
    row_to_event,
)
import ingestion.localview.events as _ev_module


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="case10", started_at=datetime.now(timezone.utc))


def _write_parquet(path: Path, records: list[dict[str, Any]]) -> Path:
    pd.DataFrame(records).to_parquet(path)
    return path


def _minimal_row(**overrides) -> dict[str, Any]:
    """Minimal valid parquet row — both meeting_date and vid_id are non-null."""
    base: dict[str, Any] = {
        "meeting_date": "2023-06-15",
        "vid_id": "abc123xyz00",
        "state_name": "California",
        "place_name": "Oakland",
        "place_govt": "County Commission",
        "vid_title": "Board Meeting - June 2023",
        "channel_id": "UCOakland123",
        "channel_title": "Oakland County TV",
        "st_fips": "06",
        "vid_length_min": 90.5,
        "vid_views": 1200.0,
        "vid_likes": 45.0,
        "acs_18_pop": 425212.0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# infer_jurisdiction_type -- exhaustive coverage
# ---------------------------------------------------------------------------


class TestInferJurisdictionType:
    @pytest.mark.parametrize(
        "input_val, expected",
        [
            # Municipal variants
            ("MUNICIPAL COUNCIL", "city"),
            ("City Commission", "city"),
            ("Board of Health", "city"),
            ("Committee", "city"),
            # Town / village
            ("Board of Selectmen", "town"),
            ("Village Board", "village"),
            # County
            ("County Commission", "county"),
            ("BOARD OF SUPERVISORS", "county"),
            # School district
            ("School Board", "school_district"),
            ("Board of Education", "school_district"),
            # Unknown -> default city
            ("Some Random Board", "city"),
            ("", "unknown"),  # empty string hits falsy check -> unknown
            # Null/NaN -> unknown
            (None, "unknown"),
            (float("nan"), "unknown"),
        ],
    )
    def test_all_variants(self, input_val, expected: str) -> None:
        assert infer_jurisdiction_type(input_val) == expected


# ---------------------------------------------------------------------------
# get_state_abbrev
# ---------------------------------------------------------------------------


class TestGetStateAbbrev:
    @pytest.mark.parametrize(
        "name, expected",
        [
            ("California", "CA"),
            ("Texas", "TX"),
            ("New York", "NY"),
            ("West Virginia", "WV"),
            # Unknown: fall back to first two chars uppercased
            ("Freedonia", "FR"),
            ("xy", "XY"),
        ],
    )
    def test_known_and_fallback(self, name: str, expected: str) -> None:
        assert get_state_abbrev(name) == expected

    def test_nan_returns_none(self) -> None:
        assert get_state_abbrev(float("nan")) is None


# ---------------------------------------------------------------------------
# row_to_event field mapping
# ---------------------------------------------------------------------------


class TestRowToEvent:
    def _row(self, **overrides) -> pd.Series:
        return pd.Series(_minimal_row(**overrides))

    def test_standard_fields(self) -> None:
        event = row_to_event(self._row())
        assert event["datasource_id"] == "abc123xyz00"
        assert event["datasource"] == "localview"
        assert event["video_url"] == "https://www.youtube.com/watch?v=abc123xyz00"
        assert event["state_code"] == "CA"
        assert event["jurisdiction_type"] == "county"
        assert event["title"] == "Board Meeting - June 2023"
        assert event["jurisdiction_name"] == "Oakland"
        assert event["city"] == "Oakland"
        assert event["st_fips"] == "06"
        assert event["vid_length_min"] == pytest.approx(90.5)
        assert event["acs_18_pop"] == pytest.approx(425212.0)

    def test_title_synthesis_when_vid_title_null(self) -> None:
        event = row_to_event(self._row(vid_title=None))
        assert event["title"].startswith("Oakland Meeting - ")

    def test_title_synthesis_caps_at_500_chars(self) -> None:
        long_title = "X" * 600
        event = row_to_event(self._row(vid_title=long_title))
        assert len(event["title"]) <= 500

    def test_null_vid_id_produces_null_video_url(self) -> None:
        event = row_to_event(self._row(vid_id=None))
        assert event["video_url"] is None

    def test_acs_float_passthrough(self) -> None:
        event = row_to_event(self._row(acs_18_black=0.123, acs_18_hispanic=0.456))
        assert event["acs_18_black"] == pytest.approx(0.123)
        assert event["acs_18_hispanic"] == pytest.approx(0.456)

    def test_loaded_at_is_datetime(self) -> None:
        event = row_to_event(self._row())
        assert isinstance(event["loaded_at"], datetime)


# ---------------------------------------------------------------------------
# _row_to_channel_mapping edge-cases
# ---------------------------------------------------------------------------


class TestRowToChannelMapping:
    def test_valid_row_returns_mapping(self) -> None:
        row = pd.Series({"vid_id": "abc123", "channel_id": "UCxyz", "channel_title": "My TV"})
        m = _row_to_channel_mapping(row)
        assert m is not None
        assert m["video_id"] == "abc123"
        assert m["channel_id"] == "UCxyz"
        assert m["channel_title"] == "My TV"
        assert m["youtube_url"] == "https://www.youtube.com/watch?v=abc123"

    def test_nan_vid_id_returns_none(self) -> None:
        row = pd.Series({"vid_id": float("nan"), "channel_id": "UCxyz", "channel_title": "TV"})
        assert _row_to_channel_mapping(row) is None

    def test_nan_channel_id_returns_none(self) -> None:
        row = pd.Series({"vid_id": "abc123", "channel_id": float("nan"), "channel_title": "TV"})
        assert _row_to_channel_mapping(row) is None

    def test_empty_vid_id_after_strip_returns_none(self) -> None:
        row = pd.Series({"vid_id": "   ", "channel_id": "UCxyz", "channel_title": "TV"})
        assert _row_to_channel_mapping(row) is None

    def test_channel_title_truncated_at_500_chars(self) -> None:
        row = pd.Series({
            "vid_id": "abc",
            "channel_id": "UCxyz",
            "channel_title": "A" * 600,
        })
        m = _row_to_channel_mapping(row)
        assert m is not None
        assert len(m["channel_title"]) == 500

    def test_null_channel_title_is_none_in_mapping(self) -> None:
        row = pd.Series({"vid_id": "abc", "channel_id": "UCxyz", "channel_title": None})
        m = _row_to_channel_mapping(row)
        assert m is not None
        assert m["channel_title"] is None


# ---------------------------------------------------------------------------
# find_parquet_files
# ---------------------------------------------------------------------------


class TestFindParquetFiles:
    def test_raises_when_directory_has_no_parquet(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_ev_module, "CACHE_DIR", tmp_path)
        with pytest.raises(FileNotFoundError):
            find_parquet_files()

    def test_returns_all_parquet_sorted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_ev_module, "CACHE_DIR", tmp_path)
        for yr in (2022, 2023, 2024):
            (tmp_path / f"meetings.{yr}.parquet").write_text("")
        files = find_parquet_files()
        assert [f.name for f in files] == [
            "meetings.2022.parquet",
            "meetings.2023.parquet",
            "meetings.2024.parquet",
        ]

    def test_year_filter_selects_single_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_ev_module, "CACHE_DIR", tmp_path)
        for yr in (2022, 2023):
            (tmp_path / f"meetings.{yr}.parquet").write_text("")
        files = find_parquet_files(year=2023)
        assert [f.name for f in files] == ["meetings.2023.parquet"]

    def test_year_filter_raises_when_no_match(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_ev_module, "CACHE_DIR", tmp_path)
        (tmp_path / "meetings.2022.parquet").write_text("")
        with pytest.raises(FileNotFoundError):
            find_parquet_files(year=2025)


# ---------------------------------------------------------------------------
# LocalviewEventRow schema boundary checks
# ---------------------------------------------------------------------------


class TestLocalviewEventRowSchema:
    def test_rejects_empty_datasource_id(self) -> None:
        with pytest.raises(Exception):
            LocalviewEventRow(
                source="localview_events",
                source_version="v",
                natural_key="x",
                datasource_id="",
            )

    def test_rejects_state_code_over_two_chars(self) -> None:
        with pytest.raises(Exception):
            LocalviewEventRow(
                source="localview_events",
                source_version="v",
                natural_key="x",
                datasource_id="vid1",
                state_code="CAL",  # max_length=2
            )

    def test_accepts_minimal_valid_row(self) -> None:
        r = LocalviewEventRow(
            source="localview_events",
            source_version="meetings.2023",
            natural_key="vid1",
            datasource_id="vid1",
        )
        assert r.datasource_id == "vid1"
        assert r.vid_views is None
        assert r.acs_18_pop is None


# ---------------------------------------------------------------------------
# LocalviewEventsPipeline.extract -- roundtrip and filter
# ---------------------------------------------------------------------------


class TestLocalviewExtract:
    def test_roundtrip_extracts_valid_row_and_validates(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "meetings.2023.parquet"
        _write_parquet(path, [_minimal_row()])
        p = LocalviewEventsPipeline(path=path)

        async def collect():
            return [r async for r in p.extract(_ctx())]

        rows = asyncio.run(collect())
        assert len(rows) == 1
        raw = rows[0]
        assert raw["datasource_id"] == "abc123xyz00"
        assert raw["source"] == "localview_events"
        assert raw["source_version"] == "meetings.2023"  # stem of parquet filename
        assert raw["natural_key"] == "abc123xyz00"
        assert raw["state_code"] == "CA"
        assert raw["channel_id"] == "UCOakland123"  # raw channel_id passed through

        validated = p.validate(raw)
        assert validated is not None
        assert validated.datasource_id == "abc123xyz00"

    def test_rows_missing_vid_id_are_dropped(self, tmp_path: Path) -> None:
        path = tmp_path / "meetings.2024.parquet"
        _write_parquet(path, [
            _minimal_row(),
            _minimal_row(vid_id=None),    # must be dropped
        ])
        p = LocalviewEventsPipeline(path=path)

        async def collect():
            return [r async for r in p.extract(_ctx())]

        rows = asyncio.run(collect())
        assert len(rows) == 1

    def test_rows_missing_meeting_date_are_dropped(self, tmp_path: Path) -> None:
        path = tmp_path / "meetings.2024.parquet"
        _write_parquet(path, [
            _minimal_row(),
            _minimal_row(meeting_date=None),  # must be dropped
        ])
        p = LocalviewEventsPipeline(path=path)

        async def collect():
            return [r async for r in p.extract(_ctx())]

        rows = asyncio.run(collect())
        assert len(rows) == 1

    def test_limit_enforced_within_single_file(self, tmp_path: Path) -> None:
        path = tmp_path / "meetings.2024.parquet"
        records = [_minimal_row(vid_id=f"vid{i:09d}") for i in range(10)]
        _write_parquet(path, records)
        p = LocalviewEventsPipeline(path=path, limit=4)

        async def collect():
            return [r async for r in p.extract(_ctx())]

        rows = asyncio.run(collect())
        assert len(rows) == 4

    def test_acs_columns_passed_through(self, tmp_path: Path) -> None:
        path = tmp_path / "meetings.2023.parquet"
        _write_parquet(path, [_minimal_row(acs_18_black=0.312, acs_18_white=0.521)])
        p = LocalviewEventsPipeline(path=path)

        async def collect():
            return [r async for r in p.extract(_ctx())]

        rows = asyncio.run(collect())
        assert rows[0]["acs_18_black"] == pytest.approx(0.312)
        assert rows[0]["acs_18_white"] == pytest.approx(0.521)

    def test_channel_id_none_when_nan_in_parquet(self, tmp_path: Path) -> None:
        path = tmp_path / "meetings.2023.parquet"
        _write_parquet(path, [_minimal_row(channel_id=None)])
        p = LocalviewEventsPipeline(path=path)

        async def collect():
            return [r async for r in p.extract(_ctx())]

        rows = asyncio.run(collect())
        # _row_to_channel_mapping returns None for NaN channel_id,
        # so channel_id in the extracted dict must also be None.
        assert rows[0]["channel_id"] is None
