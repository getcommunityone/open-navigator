"""Unit tests for the Power BI ballot-measures pipeline refactor (RAW shape).

The loader is dbt-slimmed: it lands the full raw CSV row as ``raw_row`` JSONB
plus a ``scrape_batch_id`` only. Column-alias mapping, parsing, and
state/jurisdiction/OCD resolution now live in dbt
(stg_powerbi__ballot_measure + int_powerbi__measure_with_jurisdiction), so the
Python helpers (_build_column_map / _coerce_* / _ocd_id_for_state / the
int_jurisdictions query) no longer exist and are no longer tested here.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest


from ingestion.powerbi.ballot_measures import (  # noqa: E402
    BallotMeasureRow,
    PowerbiBallotMeasuresPipeline,
    find_latest_csv,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


# -- schema accept / reject -----------------------------------------------

def test_ballot_measure_row_accepts_valid_raw_row():
    r = BallotMeasureRow(
        source="powerbi_ballot_measures",
        source_version="abc-batch",
        natural_key="abc-batch:0",
        scrape_batch_id="abc-batch",
        raw_row={"Measure Title": "Prop 1", "State": "California"},
        source_csv_path="/tmp/x.csv",
    )
    assert r.scrape_batch_id == "abc-batch"
    assert r.raw_row == {"Measure Title": "Prop 1", "State": "California"}
    assert r.source_csv_path == "/tmp/x.csv"


def test_ballot_measure_row_rejects_extra_field():
    # extra="forbid": derived columns no longer ride on the row schema.
    with pytest.raises(Exception):
        BallotMeasureRow(
            source="powerbi_ballot_measures",
            source_version="v",
            natural_key="v:0",
            scrape_batch_id="v",
            state_code="CA",  # removed from the slimmed raw shape
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

def test_extract_roundtrip_lands_raw_rows(tmp_path):
    # No DB needed anymore: extract() no longer queries int_jurisdictions.
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

    # Only the RAW envelope columns are emitted (slimmed shape) — no parsed
    # measure_title / state_code / election_year etc. live in Python anymore.
    assert set(extracted[0]) == {
        "source", "source_version", "natural_key",
        "scrape_batch_id", "raw_row", "source_csv_path",
    }
    assert extracted[0]["source"] == "powerbi_ballot_measures"
    assert extracted[0]["source_csv_path"] == str(csv_path)

    # Full source row preserved verbatim inside raw_row for dbt to map/parse.
    assert extracted[0]["raw_row"]["Measure Title"] == "Prop 1"
    assert extracted[0]["raw_row"]["State"] == "California"
    assert extracted[0]["raw_row"]["Election Year"] == "2024"
    assert extracted[0]["raw_row"]["Yes Count"] == "1000"  # str, raw
    assert extracted[1]["raw_row"]["State"] == "Texas"

    # scrape_batch_id is stable per run, and is the source_version + natural_key prefix.
    batch_id = extracted[0]["scrape_batch_id"]
    assert extracted[1]["scrape_batch_id"] == batch_id
    assert extracted[0]["source_version"] == batch_id
    assert extracted[0]["natural_key"].startswith(f"{batch_id}:")

    # every extracted dict validates cleanly through the row schema
    for raw in extracted:
        assert p.validate(raw) is not None


def test_extract_limit_caps_rows(tmp_path):
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
