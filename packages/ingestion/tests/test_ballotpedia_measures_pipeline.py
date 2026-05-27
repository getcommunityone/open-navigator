"""Unit tests for the Ballotpedia measures pipeline refactor (dbt-slimmed)."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


from ingestion.ballotpedia.measures import (  # noqa: E402
    BallotMeasureRow,
    BallotpediaMeasuresPipeline,
    _natural_key_for,
    _stable_id,
    _stable_key,
    _title_of,
    find_latest_cache_files,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def _write_snapshot(directory: Path, name: str, measures: list[dict]) -> Path:
    path = directory / name
    path.write_text(json.dumps({"measures": measures}), encoding="utf-8")
    return path


def test_title_of_coalesces_aliases():
    assert _title_of({"measure_title": "T1"}) == "T1"
    assert _title_of({"measure_name": "T2"}) == "T2"
    assert _title_of({"title": "T3"}) == "T3"
    assert _title_of({"foo": "bar"}) == ""
    # earlier empty alias falls through to a populated later one
    assert _title_of({"measure_title": "", "title": "T4"}) == "T4"


def test_natural_key_prefers_explicit_and_drops_titleless():
    # explicit measure_id wins verbatim
    assert _natural_key_for(
        {"measure_id": "m-explicit", "measure_title": "X"}, envelope={}
    ) == "m-explicit"
    # no title -> no usable key (dropped, as the legacy loader did)
    assert _natural_key_for({"state": "CA"}, envelope={}) is None
    # derived key is stable and deterministic for the same inputs
    k1 = _natural_key_for(
        {"measure_title": "Prop 1", "state": "CA", "year": "2026"}, envelope={}
    )
    k2 = _natural_key_for(
        {"measure_title": "Prop 1", "state": "CA", "year": "2026"}, envelope={}
    )
    assert k1 == k2
    assert k1.startswith("ocd-ballotmeasure/")


def test_stable_id_and_key_helpers():
    assert _stable_key("Ballotpedia", " CA ", None) == "ballotpedia|ca|"
    sid = _stable_id("ballotmeasure", "a|b|c")
    assert sid.startswith("ocd-ballotmeasure/")


def test_row_schema_accepts_raw_shape():
    r = BallotMeasureRow(
        source="ballotpedia_measures",
        source_version="batch-1",
        natural_key="m1",
        scrape_batch_id="batch-1",
        measure_id="m1",
        raw_row={"measure_title": "Sample Measure 2025", "state": "CA"},
        source_json_path="/tmp/x.json",
    )
    assert r.measure_id == "m1"
    assert r.raw_row["state"] == "CA"


def test_row_schema_rejects_blank_measure_id():
    with pytest.raises(Exception):
        BallotMeasureRow(
            source="ballotpedia_measures",
            source_version="v",
            natural_key="m1",
            scrape_batch_id="v",
            measure_id="",
            raw_row={"measure_title": "Title"},
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


def test_extract_lands_raw_and_drops_titleless(tmp_path):
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
                # year 2019 is NOT filtered in Python anymore — it still lands;
                # the election-year filter now lives in dbt (int/mart WHERE).
                "measure_id": "ca-old",
                "measure_title": "Old Measure",
                "state": "CA",
                "year": "2019",
            },
            {
                # dropped: no title -> no natural key
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
    # Both titled rows land (no year filter in Python); the title-less one is dropped.
    assert len(extracted) == 2
    by_id = {r["measure_id"]: r for r in extracted}
    assert set(by_id) == {"ca-1", "ca-old"}

    row = by_id["ca-1"]
    # Only the slimmed keys + raw_row + source_json_path are emitted.
    assert set(row) == {
        "source", "source_version", "natural_key",
        "scrape_batch_id", "measure_id", "raw_row", "source_json_path",
    }
    assert row["natural_key"] == "ca-1"
    assert row["scrape_batch_id"] == row["source_version"]
    # RAW values ride along verbatim — no Python parsing/coalescing/casting.
    assert row["raw_row"]["yes_votes"] == "1,000"
    assert row["raw_row"]["no_votes"] == "500"
    assert row["raw_row"]["state"] == "CA"
    assert row["raw_row"]["year"] == "2026"

    # Extracted dict validates cleanly through the schema
    validated = p.validate(row)
    assert validated is not None
    assert validated.measure_id == "ca-1"


def test_extract_merges_envelope_into_raw_row(tmp_path):
    # Envelope-level context (state_code/scope/jurisdiction) is merged into
    # raw_row so dbt can read it; per-measure keys override envelope keys.
    path = tmp_path / "tx_ballot_measures_20260101T000000.json"
    path.write_text(
        json.dumps({
            "state_code": "TX",
            "scope": "state",
            "jurisdiction_name": "Texas",
            "measures": [
                {"measure_id": "tx-1", "measure_title": "Texas Amendment 1"},
            ],
        }),
        encoding="utf-8",
    )
    p = BallotpediaMeasuresPipeline(path=tmp_path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 1
    raw = extracted[0]["raw_row"]
    assert raw["state_code"] == "TX"
    assert raw["scope"] == "state"
    assert raw["jurisdiction_name"] == "Texas"
    assert raw["measure_title"] == "Texas Amendment 1"
    # the nested measures list is not carried into raw_row
    assert "measures" not in raw


def test_extract_limit_caps_files(tmp_path):
    for i in range(4):
        _write_snapshot(
            tmp_path,
            f"s{i}_ballot_measures_2026010{i}T000000.json",
            [{"measure_id": f"m-{i}", "measure_title": f"Measure {i} 2026",
              "state": "CA"}],
        )
    p = BallotpediaMeasuresPipeline(path=tmp_path, limit=2)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    # Only the 2 oldest-by-mtime files (after newest-first dedupe sort) are read
    assert len(extracted) == 2
