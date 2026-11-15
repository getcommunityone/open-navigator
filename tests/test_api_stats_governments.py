"""GET /api/stats serves `governments` from governments_count (#351).

`fetch_stats_from_neon` is patched with canned aggregate rows (no database).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from api.routes import stats_neon


@pytest.fixture(autouse=True)
def _clear_cache():
    stats_neon.STATS_CACHE.clear()
    yield
    stats_neon.STATS_CACHE.clear()


def _stats(monkeypatch, row: dict[str, Any] | None) -> dict[str, Any]:
    async def fake_fetch(level, state=None, county=None, city=None):
        return row

    monkeypatch.setattr(stats_neon, "fetch_stats_from_neon", fake_fetch)
    return asyncio.run(stats_neon.get_stats(state=None, county=None, city=None))


def test_governments_comes_from_governments_count(monkeypatch):
    out = _stats(
        monkeypatch,
        {"jurisdictions_count": 70, "school_districts_count": 10, "governments_count": 40},
    )
    assert out["governments"] == 40
    assert out["jurisdictions"] == 70


def test_governments_is_null_when_the_serving_table_predates_the_column(monkeypatch):
    out = _stats(monkeypatch, {"jurisdictions_count": 70, "school_districts_count": 10})
    assert out["governments"] is None


def test_governments_is_null_when_no_row(monkeypatch):
    assert _stats(monkeypatch, None)["governments"] is None
