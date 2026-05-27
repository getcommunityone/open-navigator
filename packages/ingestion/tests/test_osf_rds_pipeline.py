"""Unit tests for the OSF RDS/CSV registry pipeline refactor."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ingestion.osf.rds import (  # noqa: E402
    OsfRdsPipeline,
    OsfRdsRow,
    bronze_osf_table_name,
    find_data_dir,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def test_bronze_osf_table_name_sanitizes_and_prefixes():
    assert bronze_osf_table_name("LEDB_CandidateLevel") == "bronze_osf_ledb_candidatelevel"
    # non-alnum collapse to single underscore, trim leading/trailing
    assert bronze_osf_table_name("  My Data!! v2  ") == "bronze_osf_my_data_v2"
    # empty / all-symbol stem falls back to unnamed_table
    assert bronze_osf_table_name("!!!") == "bronze_osf_unnamed_table"


def test_bronze_osf_table_name_respects_identifier_limit():
    name = bronze_osf_table_name("x" * 200)
    assert len(name) <= 63
    assert name.startswith("bronze_osf_")


def test_osf_rds_row_schema_accepts_valid():
    r = OsfRdsRow(
        source="osf_rds",
        source_version="Replication",
        natural_key="sub/data.rds",
        rel_path="sub/data.rds",
        abs_path="/abs/sub/data.rds",
        file_format="rds",
        table_name="bronze_osf_data",
        row_count=42,
    )
    assert r.file_format == "rds"
    assert r.row_count == 42
    # row_count is optional
    r2 = OsfRdsRow(
        source="osf_rds",
        source_version="Replication",
        natural_key="b.csv",
        rel_path="b.csv",
        abs_path="/abs/b.csv",
        file_format="csv",
        table_name="bronze_osf_b",
    )
    assert r2.row_count is None


def test_osf_rds_row_schema_rejects_bad_values():
    # empty rel_path
    with pytest.raises(Exception):
        OsfRdsRow(
            source="osf_rds",
            source_version="v",
            natural_key="x",
            rel_path="",
            abs_path="/abs/x",
            file_format="rds",
            table_name="bronze_osf_x",
        )
    # negative row_count
    with pytest.raises(Exception):
        OsfRdsRow(
            source="osf_rds",
            source_version="v",
            natural_key="x",
            rel_path="x.rds",
            abs_path="/abs/x.rds",
            file_format="rds",
            table_name="bronze_osf_x",
            row_count=-1,
        )
    # extra field forbidden (frozen RawRow, extra=forbid)
    with pytest.raises(Exception):
        OsfRdsRow(
            source="osf_rds",
            source_version="v",
            natural_key="x",
            rel_path="x.rds",
            abs_path="/abs/x.rds",
            file_format="rds",
            table_name="bronze_osf_x",
            bogus="nope",
        )


def test_pipeline_metadata():
    p = OsfRdsPipeline()
    assert p.source == "osf_rds"
    assert p.batch_size == 1000
    assert p.row_schema is OsfRdsRow


def test_find_data_dir_raises_when_missing(tmp_path, monkeypatch):
    import ingestion.osf.rds as rp
    monkeypatch.setattr(rp, "CACHE_DIR", tmp_path / "does-not-exist")
    with pytest.raises(FileNotFoundError):
        find_data_dir()


def test_extract_raises_when_no_rds(tmp_path):
    # data dir exists but has no .rds files
    (tmp_path / "only.txt").write_text("hi")
    p = OsfRdsPipeline(path=tmp_path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    with pytest.raises(FileNotFoundError):
        asyncio.run(collect())


def _seed_replication(tmp_path: Path) -> Path:
    """Create a synthetic Replication dir with .rds + .csv fixtures."""
    root = tmp_path / "Replication"
    (root / "sub").mkdir(parents=True)
    # two RDS files (binary contents irrelevant; read_rds is monkeypatched)
    (root / "Alpha Data.rds").write_bytes(b"\x00rds")
    (root / "sub" / "beta.rds").write_bytes(b"\x00rds")
    # csv with same stem as an rds -> must be skipped
    (root / "beta.csv").write_text("a,b\n1,2\n")
    # csv with unique stem -> emitted
    (root / "gamma.csv").write_text("x,y\n1,2\n3,4\n")
    return root


def test_extract_roundtrip_rds_and_csv(tmp_path, monkeypatch):
    import ingestion.osf.rds as rp

    root = _seed_replication(tmp_path)

    # pyreadr is not installed; substitute read_rds with a fake reader that
    # returns an object exposing len() like a DataFrame.
    class _FakeDF(list):
        pass

    def fake_read_rds(path: Path):
        return _FakeDF([1, 2, 3])  # len == 3

    monkeypatch.setattr(rp, "read_rds", fake_read_rds)

    p = OsfRdsPipeline(path=root)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    rows = asyncio.run(collect())

    # 2 rds + 1 unique csv (gamma); beta.csv skipped (beta.rds exists)
    assert len(rows) == 3
    by_table = {r["table_name"]: r for r in rows}

    assert "bronze_osf_alpha_data" in by_table
    assert "bronze_osf_beta" in by_table
    assert "bronze_osf_gamma" in by_table

    alpha = by_table["bronze_osf_alpha_data"]
    assert alpha["file_format"] == "rds"
    assert alpha["row_count"] == 3
    assert alpha["source"] == "osf_rds"
    assert alpha["source_version"] == "Replication"
    assert alpha["natural_key"] == alpha["rel_path"]

    gamma = by_table["bronze_osf_gamma"]
    assert gamma["file_format"] == "csv"
    assert gamma["row_count"] == 2  # 2 data rows

    # every emitted raw row validates against the schema
    for raw in rows:
        assert p.validate(raw) is not None


def test_extract_limit_caps_rows(tmp_path, monkeypatch):
    import ingestion.osf.rds as rp

    root = _seed_replication(tmp_path)
    monkeypatch.setattr(rp, "read_rds", lambda path: [0])  # len == 1

    p = OsfRdsPipeline(path=root, limit=1)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    rows = asyncio.run(collect())
    assert len(rows) == 1
    assert rows[0]["file_format"] == "rds"
