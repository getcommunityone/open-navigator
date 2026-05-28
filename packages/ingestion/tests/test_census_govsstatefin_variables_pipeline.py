"""Unit tests for the Census govsstatefin variables ingestion pipeline.

Offline-only — no network, no DB. Exercises the JSON melt, the timestamp
snapshot conventions, the pydantic row schema, and an end-to-end extract()
over a fixture snapshot.
"""
from __future__ import annotations

import datetime as dt
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ingestion.census.govsstatefin_variables import (  # noqa: E402
    CensusFinanceVariableRow,
    CensusFinanceVariablesPipeline,
    DEFAULT_DATASET,
    DEFAULT_URL,
    latest_snapshot,
    melt_variables,
    _snapshot_path,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


# ── snapshot file naming + discovery ──────────────────────────────────────


def test_snapshot_path_uses_utc_lexically_sortable_format(tmp_path: Path) -> None:
    fixed = dt.datetime(2026, 5, 28, 14, 30, 45, tzinfo=dt.timezone.utc)
    p = _snapshot_path(tmp_path, now=fixed)
    assert p == tmp_path / "20260528_143045.json"


def test_latest_snapshot_returns_lexically_largest(tmp_path: Path) -> None:
    (tmp_path / "20240101_000000.json").write_text("{}")
    (tmp_path / "20260528_120000.json").write_text("{}")
    (tmp_path / "20250606_120000.json").write_text("{}")
    latest = latest_snapshot(tmp_path)
    assert latest is not None and latest.name == "20260528_120000.json"


def test_latest_snapshot_returns_none_for_empty_dir(tmp_path: Path) -> None:
    assert latest_snapshot(tmp_path / "missing") is None
    (tmp_path / "empty").mkdir()
    assert latest_snapshot(tmp_path / "empty") is None


# ── melt: nested JSON → flat row dicts ────────────────────────────────────


_FIXTURE_BODY: dict = {
    "variables": {
        "for": {
            "label": "Census API FIPS 'for' clause",
            "concept": "Census API Geography Specification",
            "predicateType": "fips-for",
            "group": "N/A",
            "limit": 0,
        },
        "T01": {
            "label": "Property Tax Revenue",
            "concept": "Tax Revenue",
            "predicateType": "int",
            "group": "T01",
            "limit": 0,
            "attributes": "T01_EST,T01_MOE",
            "required": False,
        },
        "T01_EST": {
            "label": "Estimate flag for T01",
            "concept": "Tax Revenue",
            "predicateType": "string",
            "group": "T01",
            "limit": 0,
        },
        # Defensive: list-valued attributes (some endpoints ship arrays).
        "R01": {
            "label": "Intergovernmental Revenue",
            "concept": "Intergovernmental Revenue",
            "predicateType": "int",
            "group": "R01",
            "limit": 0,
            "attributes": ["R01_EST", "R01_MOE"],
            "required": "true",
        },
        # Malformed: non-dict value must be skipped, not raise.
        "BROKEN": ["this", "is", "not", "a", "dict"],
    }
}

_SNAPSHOT_AT = dt.datetime(2026, 5, 28, 14, 30, 45, tzinfo=dt.timezone.utc)


def test_melt_variables_yields_one_row_per_variable_skipping_malformed() -> None:
    rows = melt_variables(
        _FIXTURE_BODY,
        dataset=DEFAULT_DATASET,
        source_url=DEFAULT_URL,
        snapshot_at=_SNAPSHOT_AT,
    )
    # 5 entries, 1 malformed (non-dict) skipped → 4 valid rows
    assert len(rows) == 4
    codes = {r["variable_code"] for r in rows}
    assert codes == {"for", "T01", "T01_EST", "R01"}


def test_melt_handles_attributes_as_list_and_string() -> None:
    rows = melt_variables(
        _FIXTURE_BODY,
        dataset=DEFAULT_DATASET,
        source_url=DEFAULT_URL,
        snapshot_at=_SNAPSHOT_AT,
    )
    by = {r["variable_code"]: r for r in rows}
    # String-valued attributes pass through unchanged.
    assert by["T01"]["attributes"] == "T01_EST,T01_MOE"
    # List-valued attributes get comma-joined.
    assert by["R01"]["attributes"] == "R01_EST,R01_MOE"


def test_melt_coerces_required_bool_and_stringy_true() -> None:
    rows = melt_variables(
        _FIXTURE_BODY,
        dataset=DEFAULT_DATASET,
        source_url=DEFAULT_URL,
        snapshot_at=_SNAPSHOT_AT,
    )
    by = {r["variable_code"]: r for r in rows}
    # Native bool stays bool.
    assert by["T01"]["required"] is False
    # "true" string → True.
    assert by["R01"]["required"] is True
    # Missing 'required' → None (no fabricated value).
    assert by["T01_EST"]["required"] is None


def test_melt_sets_natural_key_with_dataset_prefix() -> None:
    rows = melt_variables(
        _FIXTURE_BODY,
        dataset="govsstatefin",
        source_url=DEFAULT_URL,
        snapshot_at=_SNAPSHOT_AT,
    )
    nk = {r["natural_key"] for r in rows}
    assert "govsstatefin:T01" in nk
    assert "govsstatefin:for" in nk


def test_melt_preserves_full_metadata_in_raw_record() -> None:
    rows = melt_variables(
        _FIXTURE_BODY,
        dataset=DEFAULT_DATASET,
        source_url=DEFAULT_URL,
        snapshot_at=_SNAPSHOT_AT,
    )
    by = {r["variable_code"]: r for r in rows}
    # raw_record carries the full metadata blob verbatim — including fields
    # not surfaced as columns (so staging can recover them without re-fetching).
    assert by["T01"]["raw_record"]["predicateType"] == "int"
    assert by["T01"]["raw_record"]["attributes"] == "T01_EST,T01_MOE"


# ── pydantic row schema ────────────────────────────────────────────────────


def test_row_schema_accepts_valid() -> None:
    r = CensusFinanceVariableRow(
        source="census_govsstatefin_variables",
        source_version="20260528_143045",
        natural_key="govsstatefin:T01",
        dataset="govsstatefin",
        variable_code="T01",
        label="Property Tax Revenue",
        concept="Tax Revenue",
        predicate_type="int",
        var_group="T01",
        var_limit=0,
        attributes="T01_EST,T01_MOE",
        required=False,
        source_url=DEFAULT_URL,
        snapshot_at=_SNAPSHOT_AT,
        raw_record={"label": "Property Tax Revenue"},
    )
    assert r.variable_code == "T01"
    assert r.required is False


def test_row_schema_rejects_oversized_predicate_type() -> None:
    with pytest.raises(Exception):
        CensusFinanceVariableRow(
            source="census_govsstatefin_variables",
            source_version="x",
            natural_key="x",
            dataset="govsstatefin",
            variable_code="T01",
            predicate_type="x" * 33,  # > 32 chars
            source_url=DEFAULT_URL,
            snapshot_at=_SNAPSHOT_AT,
            raw_record={},
        )


# ── end-to-end extract over fixture snapshot ──────────────────────────────


def test_extract_no_fetch_reads_latest_snapshot(tmp_path: Path) -> None:
    # Write two snapshots; the lexically newer one should win.
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "20240101_000000.json").write_text(
        json.dumps({"variables": {"OLD": {"label": "old"}}})
    )
    (cache / "20260528_120000.json").write_text(json.dumps(_FIXTURE_BODY))

    pipe = CensusFinanceVariablesPipeline(
        cache_dir=cache,
        fetch=False,
    )

    async def _collect() -> list[dict]:
        out: list[dict] = []
        async for row in pipe.extract(_ctx()):
            out.append(row)
        return out

    import asyncio

    rows = asyncio.run(_collect())
    # Newer snapshot has 4 valid variables (one malformed entry skipped);
    # the older snapshot's 'OLD' must NOT appear.
    codes = {r["variable_code"] for r in rows}
    assert codes == {"for", "T01", "T01_EST", "R01"}
    assert "OLD" not in codes


def test_extract_no_fetch_with_empty_cache_raises(tmp_path: Path) -> None:
    pipe = CensusFinanceVariablesPipeline(
        cache_dir=tmp_path / "missing",
        fetch=False,
    )

    async def _drain() -> None:
        async for _ in pipe.extract(_ctx()):
            pass

    import asyncio

    with pytest.raises(FileNotFoundError):
        asyncio.run(_drain())


def test_extract_with_explicit_snapshot_overrides_cache_lookup(tmp_path: Path) -> None:
    snap = tmp_path / "manually_supplied.json"
    snap.write_text(json.dumps(_FIXTURE_BODY))
    pipe = CensusFinanceVariablesPipeline(
        cache_dir=tmp_path / "ignored",
        fetch=False,
        snapshot=snap,
    )

    async def _collect() -> list[dict]:
        out: list[dict] = []
        async for row in pipe.extract(_ctx()):
            out.append(row)
        return out

    import asyncio

    rows = asyncio.run(_collect())
    assert len(rows) == 4
