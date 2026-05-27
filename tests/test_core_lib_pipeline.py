"""Unit tests for core_lib.pipeline.DataSourcePipeline orchestration."""
from __future__ import annotations

import asyncio
import os
from typing import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db.engine import get_async_engine, get_sync_engine
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


@pytest.fixture(autouse=True)
def _isolate_engines(monkeypatch, tmp_path):
    """Each test gets a clean in-memory(ish) sqlite engine. Caching is reset."""
    db_path = tmp_path / "pipeline_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.delenv("NEON_DATABASE_URL_DEV", raising=False)
    monkeypatch.delenv("NEON_DATABASE_URL", raising=False)
    get_sync_engine.cache_clear()
    get_async_engine.cache_clear()
    # Force re-creation of the session factories that capture the engine
    import core_lib.db.session as s
    s._sync_factory = None
    s._async_factory = None
    yield
    get_sync_engine.cache_clear()
    get_async_engine.cache_clear()
    s._sync_factory = None
    s._async_factory = None


class _Row(RawRow):
    value: int


def _make_pipeline(raws: list[dict], on_load=None):
    class _P(DataSourcePipeline[_Row]):
        source = "test_src"
        batch_size = 2
        row_schema = _Row

        async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
            for r in raws:
                yield r

        async def load_batch(
            self, session: AsyncSession, rows: list[_Row], ctx: PipelineContext
        ) -> None:
            if on_load is not None:
                await on_load(session, rows, ctx)

    return _P()


def _good(i: int) -> dict:
    return {
        "source": "test_src",
        "source_version": "v1",
        "natural_key": f"k:{i}",
        "value": i,
    }


def test_run_extracts_validates_and_loads_all_rows():
    seen_batches: list[list[_Row]] = []

    async def load(session, rows, ctx):
        seen_batches.append(list(rows))

    p = _make_pipeline([_good(i) for i in range(5)], on_load=load)
    run = asyncio.run(p.run())

    assert run.extracted == 5
    assert run.validated == 5
    assert run.rejected == 0
    assert run.loaded == 5
    assert run.finished_at is not None
    assert run.errors == []
    # batch_size=2 → batches of [2, 2, 1]
    assert [len(b) for b in seen_batches] == [2, 2, 1]
    assert seen_batches[0][0].value == 0


def test_validation_rejects_bad_rows_without_failing_run():
    bad = {"source": "test_src", "source_version": "v1", "natural_key": "x", "value": "not-an-int"}
    p = _make_pipeline([_good(0), bad, _good(1)])
    run = asyncio.run(p.run())

    assert run.extracted == 3
    assert run.validated == 2
    assert run.rejected == 1
    assert run.loaded == 2
    assert run.errors == []


def test_load_batch_failure_propagates_and_records_error():
    async def boom(session, rows, ctx):
        raise RuntimeError("intentional load failure")

    p = _make_pipeline([_good(i) for i in range(3)], on_load=boom)
    with pytest.raises(RuntimeError, match="intentional load failure"):
        asyncio.run(p.run())


def test_empty_extract_yields_zero_loaded():
    p = _make_pipeline([])
    run = asyncio.run(p.run())
    assert run.extracted == 0
    assert run.validated == 0
    assert run.loaded == 0
    assert run.errors == []
