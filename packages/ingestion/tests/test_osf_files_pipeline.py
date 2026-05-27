"""Unit tests for the OSF files pipeline refactor."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


from ingestion.osf.files import (  # noqa: E402
    FileRow,
    OsfFilesPipeline,
    _file_ext,
    _sha256_file,
    find_extract_dir,
)
from core_lib.pipeline.schemas import PipelineContext  # noqa: E402


def _ctx() -> PipelineContext:
    return PipelineContext(run_id="t", started_at=datetime.now(timezone.utc))


def test_file_ext_normalizes_and_handles_no_suffix():
    assert _file_ext(Path("a/b/data.CSV")) == "csv"
    assert _file_ext(Path("a/b/data.json")) == "json"
    assert _file_ext(Path("a/b/README")) is None


def test_sha256_file_hashes_contents(tmp_path):
    f = tmp_path / "blob.bin"
    f.write_bytes(b"hello osf")
    digest = _sha256_file(f)
    assert len(digest) == 64
    # Deterministic for identical contents.
    g = tmp_path / "blob2.bin"
    g.write_bytes(b"hello osf")
    assert _sha256_file(g) == digest


def test_file_row_schema_accepts_valid():
    r = FileRow(
        source="osf_files",
        source_version="osf",
        natural_key="sub/data.csv",
        rel_path="sub/data.csv",
        abs_path="/abs/sub/data.csv",
        file_ext="csv",
        size_bytes=123,
        mtime_utc=datetime(2026, 1, 1),
        sha256="a" * 64,
    )
    assert r.rel_path == "sub/data.csv"
    assert r.size_bytes == 123
    assert r.file_ext == "csv"


def test_file_row_schema_rejects_bad_sha_and_negative_size():
    # sha256 must be exactly 64 chars
    with pytest.raises(Exception):
        FileRow(
            source="osf_files",
            source_version="osf",
            natural_key="x",
            rel_path="x",
            abs_path="/x",
            size_bytes=1,
            sha256="abc",
        )
    # size_bytes must be >= 0
    with pytest.raises(Exception):
        FileRow(
            source="osf_files",
            source_version="osf",
            natural_key="x",
            rel_path="x",
            abs_path="/x",
            size_bytes=-1,
            sha256="a" * 64,
        )


def test_file_row_schema_forbids_extra_fields():
    with pytest.raises(Exception):
        FileRow(
            source="osf_files",
            source_version="osf",
            natural_key="x",
            rel_path="x",
            abs_path="/x",
            size_bytes=1,
            sha256="a" * 64,
            unexpected="nope",
        )


def test_pipeline_metadata():
    p = OsfFilesPipeline()
    assert p.source == "osf_files"
    assert p.batch_size == 1000
    assert p.row_schema is FileRow


def test_find_extract_dir_raises_when_missing(tmp_path, monkeypatch):
    import ingestion.osf.files as fp
    monkeypatch.setattr(fp, "CACHE_DIR", tmp_path / "does_not_exist")
    with pytest.raises(FileNotFoundError):
        find_extract_dir()


def test_find_extract_dir_returns_existing(tmp_path, monkeypatch):
    import ingestion.osf.files as fp
    monkeypatch.setattr(fp, "CACHE_DIR", tmp_path)
    assert find_extract_dir() == tmp_path


def test_extract_yields_validated_rows(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "top.csv").write_text("a,b\n1,2\n")
    (tmp_path / "sub" / "nested.json").write_text('{"k": 1}')

    p = OsfFilesPipeline(path=tmp_path)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2

    by_rel = {r["rel_path"]: r for r in extracted}
    assert "top.csv" in by_rel
    assert "sub/nested.json" in by_rel
    top = by_rel["top.csv"]
    assert top["file_ext"] == "csv"
    assert top["natural_key"] == "top.csv"
    assert top["size_bytes"] > 0
    assert len(top["sha256"]) == 64

    # All extracted rows validate cleanly.
    for raw in extracted:
        assert p.validate(raw) is not None


def test_limit_caps_extracted_rows(tmp_path):
    for i in range(5):
        (tmp_path / f"f{i}.txt").write_text(f"content {i}")
    p = OsfFilesPipeline(path=tmp_path, limit=2)

    async def collect():
        return [r async for r in p.extract(_ctx())]

    extracted = asyncio.run(collect())
    assert len(extracted) == 2


def test_extract_raises_when_dir_missing(tmp_path):
    p = OsfFilesPipeline(path=tmp_path / "nope")

    async def collect():
        return [r async for r in p.extract(_ctx())]

    with pytest.raises(FileNotFoundError):
        asyncio.run(collect())
