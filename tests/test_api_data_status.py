"""GET /data/status serves real warehouse counts or null — never hard-coded numbers.

The national aggregate fetch and the asyncpg pool are patched (no database).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from api.routes import stats_neon

FABRICATED = {90000, 3144, 19500, 13000, 3000000, 1366, "100-500", "50+"}


@pytest.fixture(autouse=True)
def _clear_cache():
    stats_neon._REFERENCE_COUNTS_CACHE.clear()
    yield
    stats_neon._REFERENCE_COUNTS_CACHE.clear()


class _FakeConn:
    def __init__(self, rows: list[dict[str, Any]] | None):
        self._rows = rows

    async def fetchrow(self, *_args):  # used by _resolve_relation
        return None if self._rows is None else {"schema_name": "public", "rel_name": "civic_jurisdiction"}

    async def fetch(self, *_args):
        return self._rows or []


class _FakePool:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self):
                return pool._conn

            async def __aexit__(self, *exc):
                return False

        return _Ctx()


def _status(monkeypatch, agg_row, jur_rows) -> dict[str, Any]:
    async def fake_fetch(level, state=None, county=None, city=None):
        return agg_row

    async def fake_pool():
        return _FakePool(_FakeConn(jur_rows))

    monkeypatch.setattr(stats_neon, "fetch_stats_from_neon", fake_fetch)
    monkeypatch.setattr(stats_neon, "get_db_pool", fake_pool)

    from api.main import get_data_ingestion_status

    return asyncio.run(get_data_ingestion_status())


def _counts(out: dict[str, Any]) -> list[Any]:
    return [
        out["census"]["jurisdictions"],
        out["census"]["counties"],
        out["census"]["municipalities"],
        out["nces"]["school_districts"],
        out["nonprofits"]["total_available"],
        *out["meetings"].values(),
    ]


def test_counts_come_from_the_warehouse(monkeypatch):
    out = _status(
        monkeypatch,
        {"jurisdictions_count": 71, "school_districts_count": 12, "nonprofits_count": 345},
        [{"classification": "county", "count": 7}, {"classification": "city", "count": 40}],
    )
    assert set(out) == {"census", "nces", "nonprofits", "meetings"}
    assert out["census"]["jurisdictions"] == 71
    assert out["census"]["counties"] == 7
    assert out["census"]["municipalities"] == 40
    assert out["nces"]["school_districts"] == 12
    assert out["nonprofits"]["total_available"] == 345
    assert all(v is None for v in out["meetings"].values())


def test_missing_data_is_null_not_fabricated(monkeypatch):
    out = _status(monkeypatch, None, None)
    values = _counts(out)
    assert all(v is None for v in values)
    assert not FABRICATED.intersection(v for v in values if v is not None)


def test_db_error_yields_nulls(monkeypatch):
    async def boom(*_a, **_k):
        raise RuntimeError("db down")

    monkeypatch.setattr(stats_neon, "fetch_stats_from_neon", boom)
    monkeypatch.setattr(stats_neon, "get_db_pool", boom)
    from api.main import get_data_ingestion_status

    out = asyncio.run(get_data_ingestion_status())
    for v in _counts(out):
        assert v is None or isinstance(v, int)
        assert v not in FABRICATED
    assert stats_neon._REFERENCE_COUNTS_CACHE == {}


# --- GET /api/data/status (twin route in api/app.py) -------------------------


def _api_status(monkeypatch, agg_row, jur_rows) -> dict[str, Any]:
    async def fake_fetch(level, state=None, county=None, city=None):
        return agg_row

    async def fake_pool():
        return _FakePool(_FakeConn(jur_rows))

    monkeypatch.setattr(stats_neon, "fetch_stats_from_neon", fake_fetch)
    monkeypatch.setattr(stats_neon, "get_db_pool", fake_pool)

    from api.app import get_data_status

    return asyncio.run(get_data_status())


def _api_counts(out: dict[str, Any]) -> list[Any]:
    return [
        out["census_jurisdictions"]["count"],
        out["nces_school_districts"]["count"],
        out["nonprofits"]["count"],
        *(m["count"] for m in out["meeting_datasets"].values()),
    ]


def test_api_route_counts_come_from_the_warehouse(monkeypatch):
    out = _api_status(
        monkeypatch,
        {
            "jurisdictions_count": 71,
            "school_districts_count": 12,
            "nonprofits_count": 345,
            "last_updated": "2026-06-05T18:16:09",
        },
        [],
    )
    assert set(out) == {
        "census_jurisdictions",
        "nces_school_districts",
        "nonprofits",
        "meeting_datasets",
    }
    for key in ("census_jurisdictions", "nces_school_districts", "nonprofits"):
        assert set(out[key]) == {"path", "status", "count", "last_updated"}
        assert out[key]["status"] == "available"
        assert out[key]["last_updated"] == "2026-06-05T18:16:09"
        assert "data/bronze" not in out[key]["path"]
    assert out["census_jurisdictions"]["count"] == 71
    assert out["nces_school_districts"]["count"] == 12
    assert out["nonprofits"]["count"] == 345
    assert set(out["meeting_datasets"]) == {"meetingbank", "city_scrapers", "open_states"}
    assert all(m["count"] is None for m in out["meeting_datasets"].values())


def test_api_route_missing_data_is_null_not_fabricated(monkeypatch):
    out = _api_status(monkeypatch, None, None)
    values = _api_counts(out)
    assert all(v is None for v in values)
    assert not FABRICATED.intersection(v for v in values if v is not None)
    for key in ("census_jurisdictions", "nces_school_districts", "nonprofits"):
        assert out[key]["status"] == "unavailable"
        assert out[key]["last_updated"] is None
