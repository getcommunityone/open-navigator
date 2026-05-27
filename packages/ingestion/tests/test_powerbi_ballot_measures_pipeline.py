"""Unit tests for the Power BI ballot-measures pipeline refactor."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


from ingestion.powerbi.ballot_measures import (  # noqa: E402
    BallotMeasureRow,
    PowerbiBallotMeasuresPipeline,
    _build_column_map,
    _coerce_float,
    _coerce_int,
    _coerce_year,
    _ocd_id_for_state,
    find_latest_csv,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


# -- pure helpers ----------------------------------------------------------

def test_coerce_int_handles_commas_and_invalid():
    assert _coerce_int("1,234") == 1234
    assert _coerce_int("42") == 42
    assert _coerce_int("3.0") == 3
    assert _coerce_int("") is None
    assert _coerce_int(None) is None
    assert _coerce_int("not-a-number") is None


def test_coerce_float_strips_percent_and_commas():
    assert _coerce_float("12.5%") == 12.5
    assert _coerce_float("1,000.5") == 1000.5
    assert _coerce_float("") is None
    assert _coerce_float(None) is None
    assert _coerce_float("bad") is None


def test_coerce_year_extracts_four_digits():
    assert _coerce_year("November 2024") == "2024"
    assert _coerce_year("2020") == "2020"
    assert _coerce_year("") is None
    assert _coerce_year("no year here") is None


def test_build_column_map_matches_aliases_case_insensitively():
    cols = ["Measure Title", "STATE", "Election Year", "Unknown Col"]
    mapping = _build_column_map(cols)
    assert mapping["measure_title"] == "Measure Title"
    assert mapping["state"] == "STATE"
    assert mapping["election_year"] == "Election Year"
    assert mapping["yes_count"] is None


def test_ocd_id_for_state_prefers_open_states_id():
    assert _ocd_id_for_state("ca", "ocd-division/country:us/state:ca") == "ocd-division/country:us/state:ca"
    assert _ocd_id_for_state("TX", None) == "ocd-division/country:us/state:tx"
    assert _ocd_id_for_state("ny", "garbage") == "ocd-division/country:us/state:ny"


# -- schema accept / reject -----------------------------------------------

def test_ballot_measure_row_accepts_valid_row():
    r = BallotMeasureRow(
        source="powerbi_ballot_measures",
        source_version="abc-batch",
        natural_key="abc-batch:0",
        scrape_batch_id="abc-batch",
        measure_title="Prop 1",
        state_code="CA",
        state="California",
        election_year="2024",
        yes_count=100,
        no_count=50,
        yes_percent=66.6,
        raw_row={"col": "val"},
        source_csv_path="/tmp/x.csv",
    )
    assert r.scrape_batch_id == "abc-batch"
    assert r.state_code == "CA"
    assert r.raw_row == {"col": "val"}


def test_ballot_measure_row_rejects_overlong_state_code():
    with pytest.raises(Exception):
        BallotMeasureRow(
            source="powerbi_ballot_measures",
            source_version="v",
            natural_key="v:0",
            scrape_batch_id="v",
            state_code="CAL",  # > 2 chars
        )


def test_ballot_measure_row_rejects_extra_field():
    with pytest.raises(Exception):
        BallotMeasureRow(
            source="powerbi_ballot_measures",
            source_version="v",
            natural_key="v:0",
            scrape_batch_id="v",
            bogus_field="nope",  # extra="forbid"
        )


# -- pipeline metadata -----------------------------------------------------

def test_pipeline_metadata():
    p = PowerbiBallotMeasuresPipeline()
    assert p.source == "powerbi_ballot_measures"
    assert p.batch_size == 2000
    assert p.row_schema is BallotMeasureRow


# -- discovery -------------------------------------------------------------

def test_find_latest_csv_raises_when_no_files(tmp_path, monkeypatch):
    import ingestion.powerbi.ballot_measures as bmp
    monkeypatch.setattr(bmp, "CACHE_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        find_latest_csv()


def test_find_latest_csv_returns_most_recent(tmp_path, monkeypatch):
    import ingestion.powerbi.ballot_measures as bmp
    monkeypatch.setattr(bmp, "CACHE_DIR", tmp_path)
    (tmp_path / "ballot_measures_20260101T000000Z.csv").write_text("")
    (tmp_path / "ballot_measures_20260524T200000Z.csv").write_text("")
    (tmp_path / "ballot_measures_20240101T000000Z.csv").write_text("")
    latest = find_latest_csv()
    assert latest.name == "ballot_measures_20260524T200000Z.csv"


# -- extract roundtrip -----------------------------------------------------

def test_extract_roundtrip_builds_validated_rows(tmp_path, monkeypatch):
    import ingestion.powerbi.ballot_measures as bmp

    # Stub out the DB-backed state index so extract() needs no live DB.
    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(bmp, "async_session", lambda: _FakeSession())

    async def _fake_index(session):
        return {}

    monkeypatch.setattr(bmp, "load_state_jurisdiction_index", _fake_index)
    # _state_code_from_name lazily imports bs4 (optional scraping dep); stub it.
    _stub = {"california": "CA", "texas": "TX"}
    monkeypatch.setattr(
        bmp, "_state_code_from_name",
        lambda s: (_stub.get(s.strip().lower()) if s else None),
    )

    csv_path = tmp_path / "ballot_measures_20260524T200000Z.csv"
    csv_path.write_text(
        "Measure Title,State,Election Year,Outcome,Yes Count,No Count,Yes Percent\n"
        "Prop 1,California,2024,Passed,1000,500,66.6\n"
        "Prop 2,Texas,2024,Failed,300,700,30.0\n"
    )
    p = PowerbiBallotMeasuresPipeline(path=csv_path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2
    assert extracted[0]["measure_title"] == "Prop 1"
    assert extracted[0]["state"] == "California"
    assert extracted[0]["election_year"] == "2024"
    assert extracted[0]["yes_count"] == 1000
    assert extracted[0]["yes_percent"] == 66.6
    # state_code falls back to the 2-letter abbreviation derived from the name
    assert extracted[0]["state_code"] == "CA"
    assert extracted[1]["state_code"] == "TX"
    # full source row preserved as raw_row dict
    assert extracted[0]["raw_row"]["Measure Title"] == "Prop 1"

    # every extracted dict validates cleanly through the row schema
    for raw in extracted:
        assert p.validate(raw) is not None


def test_extract_limit_caps_rows(tmp_path, monkeypatch):
    import ingestion.powerbi.ballot_measures as bmp

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(bmp, "async_session", lambda: _FakeSession())

    async def _fake_index(session):
        return {}

    monkeypatch.setattr(bmp, "load_state_jurisdiction_index", _fake_index)
    monkeypatch.setattr(bmp, "_state_code_from_name", lambda s: ("CA" if s else None))

    lines = ["Measure Title,State,Election Year"]
    for i in range(10):
        lines.append(f"Prop {i},California,2024")
    csv_path = tmp_path / "ballot_measures_test.csv"
    csv_path.write_text("\n".join(lines) + "\n")

    p = PowerbiBallotMeasuresPipeline(path=csv_path, limit=3)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 3
