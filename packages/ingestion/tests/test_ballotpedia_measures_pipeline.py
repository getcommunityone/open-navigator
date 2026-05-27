"""Unit tests for the Ballotpedia measures pipeline refactor."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


from ingestion.ballotpedia.measures import (  # noqa: E402
    BallotMeasureRow,
    BallotpediaMeasuresPipeline,
    _parse_int,
    _parse_passed,
    _parse_years,
    find_latest_cache_files,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _write_snapshot(directory: Path, name: str, measures: list[dict]) -> Path:
    path = directory / name
    path.write_text(json.dumps({"measures": measures}), encoding="utf-8")
    return path


def test_parse_years_defaults_and_overrides():
    assert _parse_years(None) == frozenset({"2025", "2026"})
    assert _parse_years("") == frozenset({"2025", "2026"})
    assert _parse_years("2024, 2025 ,") == frozenset({"2024", "2025"})


def test_parse_int_and_passed_helpers():
    assert _parse_int("1,234") == 1234
    assert _parse_int(None) is None
    assert _parse_int("nope") is None
    assert _parse_passed("Measure passed") is True
    assert _parse_passed("Measure failed") is False
    assert _parse_passed(None) is None


def test_row_schema_accepts_valid_row():
    r = BallotMeasureRow(
        source="ballotpedia_measures",
        source_version="batch-1",
        natural_key="m1",
        scrape_batch_id="batch-1",
        measure_id="m1",
        measure_title="Sample Measure 2025",
        state_code="CA",
        election_year="2025",
        yes_votes=10,
        no_votes=5,
        passed=True,
        raw_row={"foo": "bar"},
    )
    assert r.measure_id == "m1"
    assert r.state_code == "CA"
    assert r.raw_row == {"foo": "bar"}


def test_row_schema_rejects_blank_title_and_oversized_state():
    with pytest.raises(Exception):
        BallotMeasureRow(
            source="ballotpedia_measures",
            source_version="v",
            natural_key="m1",
            scrape_batch_id="v",
            measure_id="m1",
            measure_title="",
        )
    with pytest.raises(Exception):
        BallotMeasureRow(
            source="ballotpedia_measures",
            source_version="v",
            natural_key="m1",
            scrape_batch_id="v",
            measure_id="m1",
            measure_title="Title",
            state_code="CAL",
        )


def test_pipeline_metadata():
    p = BallotpediaMeasuresPipeline()
    assert p.source == "ballotpedia_measures"
    assert p.batch_size == 500
    assert p.row_schema is BallotMeasureRow


def test_find_latest_cache_files_raises_when_missing(tmp_path, monkeypatch):
    import ingestion.ballotpedia.measures as mp
    monkeypatch.setattr(mp, "CACHE_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        find_latest_cache_files(tmp_path)


def test_extract_roundtrip_and_year_filter(tmp_path):
    _write_snapshot(
        tmp_path,
        "ca_ballot_measures_20260101T000000.json",
        [
            {
                "measure_id": "ca-1",
                "measure_title": "California Proposition 1",
                "state": "CA",
                "year": "2026",
                "ocd_division_id": "ocd-division/country:us/state:ca",
                "yes_votes": "1,000",
                "no_votes": "500",
            },
            {
                # filtered out: election_year resolves to 2019
                "measure_id": "ca-old",
                "measure_title": "Old Measure",
                "state": "CA",
                "year": "2019",
                "ocd_division_id": "x",
            },
            {
                # dropped: no title
                "measure_id": "ca-blank",
                "state": "CA",
                "year": "2026",
            },
        ],
    )
    p = BallotpediaMeasuresPipeline(path=tmp_path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 1
    row = extracted[0]
    assert row["measure_id"] == "ca-1"
    assert row["state_code"] == "CA"
    assert row["election_year"] == "2026"
    assert row["yes_votes"] == 1000
    assert row["no_votes"] == 500
    assert row["natural_key"] == "ca-1"
    assert row["scrape_batch_id"] == row["source_version"]

    # Extracted dict validates cleanly through the schema
    validated = p.validate(row)
    assert validated is not None
    assert validated.measure_title == "California Proposition 1"


def test_extract_limit_caps_files(tmp_path):
    for i in range(4):
        _write_snapshot(
            tmp_path,
            f"s{i}_ballot_measures_2026010{i}T000000.json",
            [{"measure_id": f"m-{i}", "measure_title": f"Measure {i} 2026",
              "state": "CA", "ocd_division_id": "x"}],
        )
    p = BallotpediaMeasuresPipeline(path=tmp_path, limit=2)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    # Only the 2 oldest-by-mtime files (after newest-first dedupe sort) are read
    assert len(extracted) == 2
