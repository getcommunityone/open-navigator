"""Unit tests for the census states pipeline reference migration."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import pytest

_CENSUS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "datasources" / "census"
sys.path.insert(0, str(_CENSUS_DIR))

from states_pipeline import (  # noqa: E402
    US_STATES,
    CensusStatesPipeline,
    StateRow,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def test_extract_yields_one_dict_per_state():
    p = CensusStatesPipeline()

    async def collect() -> list[dict]:
        return [r async for r in p.extract(_ctx())]

    rows = asyncio.run(collect())
    assert len(rows) == len(US_STATES) == 52
    state_codes = {r["state_code"] for r in rows}
    assert {"AL", "AK", "CA", "DC", "PR", "WY"} <= state_codes


def test_extracted_rows_validate_under_state_row_schema():
    p = CensusStatesPipeline()

    async def collect() -> list[StateRow]:
        out: list[StateRow] = []
        async for raw in p.extract(_ctx()):
            row = p.validate(raw)
            assert row is not None, f"validation rejected: {raw}"
            out.append(row)
        return out

    rows = asyncio.run(collect())
    assert len(rows) == 52
    assert all(isinstance(r, StateRow) for r in rows)
    # Spot-check a deterministic row
    alabama = next(r for r in rows if r.state_code == "AL")
    assert alabama.state_name == "Alabama"
    assert alabama.fips_code == "01"
    assert alabama.geoid == "01"
    assert alabama.natural_key == "state:AL"
    assert alabama.source == "census_states"


def test_state_row_schema_rejects_wrong_length_codes():
    bad_state_code = {
        "source": "census_states",
        "source_version": "2024",
        "natural_key": "x",
        "state_code": "ABC",            # 3 chars — must be 2
        "state_name": "X",
        "fips_code": "01",
        "geoid": "01",
    }
    with pytest.raises(Exception):
        StateRow.model_validate(bad_state_code)

    bad_fips = {**bad_state_code, "state_code": "AB", "fips_code": "1"}
    with pytest.raises(Exception):
        StateRow.model_validate(bad_fips)
