"""Unit tests for the USCM mayors pipeline refactor."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_USCM_DIR = Path(__file__).resolve().parents[1] / "scripts" / "datasources" / "uscm"
sys.path.insert(0, str(_USCM_DIR))

from mayors_pipeline import (  # noqa: E402
    MayorRow,
    UscmMayorsPipeline,
    _int,
    _str,
    find_latest_cache,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def test_str_helper_trims_and_truncates():
    assert _str("  hello  ") == "hello"
    assert _str("", 5) is None
    assert _str(None) is None
    assert _str("longertext", 4) == "long"


def test_int_helper_returns_none_for_invalid():
    assert _int("42") == 42
    assert _int(42) == 42
    assert _int(None) is None
    assert _int("garbage") is None
    assert _int("") is None


def test_mayor_row_requires_state_and_municipality():
    base = dict(source="uscm_mayors", source_version="v", natural_key="x")
    MayorRow(**base, state_code="CA", municipality_name="Anaheim")
    with pytest.raises(Exception):
        MayorRow(**base, state_code="CAL", municipality_name="X")
    with pytest.raises(Exception):
        MayorRow(**base, state_code="CA", municipality_name="")


def test_find_latest_cache_returns_newest(tmp_path, monkeypatch):
    import mayors_pipeline as mp
    monkeypatch.setattr(mp, "CACHE_DIR", tmp_path)
    older = tmp_path / "meet_the_mayors_us_20250101.json"
    newer = tmp_path / "meet_the_mayors_us_20260101.json"
    older.write_text("{}")
    newer.write_text("{}")
    # Touch to ensure mtime ordering
    import os, time
    os.utime(older, (older.stat().st_atime, time.time() - 1000))
    os.utime(newer, (newer.stat().st_atime, time.time()))
    assert find_latest_cache() == newer


def test_find_latest_cache_none_when_missing(tmp_path, monkeypatch):
    import mayors_pipeline as mp
    monkeypatch.setattr(mp, "CACHE_DIR", tmp_path)
    assert find_latest_cache() is None


def test_pipeline_metadata():
    p = UscmMayorsPipeline()
    assert p.source == "uscm_mayors"
    assert p.batch_size == 2000
    assert p.row_schema is MayorRow


def test_extract_reads_json_and_yields_validated_rows(tmp_path):
    payload = {
        "scraped_at": "2026-05-10T12:00:00Z",
        "source_url": "https://uscm.example/meet-the-mayors",
        "mayor_count": 2,
        "mayors": [
            {
                "state_code": "ca",
                "municipality_name": "Anaheim",
                "mayor_name": "Mayor A",
                "population": "350000",
                "raw_card_html": "<div>...</div>",  # should be dropped from raw_json
            },
            {
                "state_code": "TX",
                "municipality_name": "Austin",
                "mayor_name": "Mayor B",
                "phone": "512-555-0100",
            },
            {"municipality_name": "OrphanCity"},  # missing state_code → skipped
            "not-a-dict",                          # skipped
        ],
    }
    json_path = tmp_path / "meet_the_mayors_us_20260510.json"
    json_path.write_text(json.dumps(payload), encoding="utf-8")

    p = UscmMayorsPipeline(json_path=json_path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2
    a, b = extracted
    assert a["state_code"] == "CA"  # uppercased
    assert a["municipality_name"] == "Anaheim"
    assert a["population"] == 350000
    assert "raw_card_html" not in a["raw_json"]
    assert b["state_code"] == "TX"
    assert b["phone"] == "512-555-0100"
    # All validate
    for raw in extracted:
        row = p.validate(raw)
        assert row is not None


def test_extract_raises_when_no_file(tmp_path, monkeypatch):
    import mayors_pipeline as mp
    monkeypatch.setattr(mp, "CACHE_DIR", tmp_path)
    p = UscmMayorsPipeline()

    async def go():
        async for _ in p.extract(_ctx()):
            pass

    with pytest.raises(FileNotFoundError):
        asyncio.run(go())
