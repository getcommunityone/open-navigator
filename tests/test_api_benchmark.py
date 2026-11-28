"""Tests for api/routes/benchmark.py (#1393): peer selection, ranking, endpoint with a fake DB."""
from __future__ import annotations

import math

import pytest
from fastapi import HTTPException

from api.routes import benchmark


def _c(i, state, has, pop_ratio):
    return {"jurisdiction_id": i, "state_code": state, "has_data": has, "pop_distance": abs(math.log(pop_ratio))}


def test_select_peers_prefers_same_state_then_data_then_closeness():
    cands = [
        _c("a", "GA", True, 1.0),
        _c("b", "AL", False, 1.5),
        _c("c", "AL", True, 1.8),
        _c("d", "AL", True, 1.1),
        _c("e", "MS", True, 1.0),
    ]
    got = [c["jurisdiction_id"] for c in benchmark.select_peers(cands, "AL", 4)]
    assert got == ["d", "c", "b", "a"]


def test_rank_among_ignores_null_and_missing_target():
    vals = {"t": 5.0, "a": 9.0, "b": None, "c": 1.0}
    assert benchmark.rank_among(vals, "t") == {"rank": 2, "of": 3}
    assert benchmark.rank_among(vals, "b") is None


def test_region_of():
    assert benchmark.region_of("AL") == "South"
    assert benchmark.region_of("MA") == "Northeast"
    assert benchmark.region_of("ZZ") is None


def test_every_metric_has_required_sql_params():
    for spec in benchmark.METRICS.values():
        assert "$1" in spec.values_sql and "$2" in spec.values_sql
        assert spec.source


class FakeConn:
    def __init__(self):
        self.jur = {
            "T": {"jurisdiction_id": "T", "name": "Town", "jurisdiction_type": "city", "state_code": "AL",
                  "state_name": "Alabama", "population": 100000},
            "P1": {"jurisdiction_id": "P1", "name": "Peer One", "jurisdiction_type": "city", "state_code": "AL",
                   "state_name": "Alabama", "population": 90000},
            "P2": {"jurisdiction_id": "P2", "name": "Peer Two", "jurisdiction_type": "city", "state_code": "GA",
                   "state_name": "Georgia", "population": 120000},
        }

    async def execute(self, *a):
        return None

    async def fetchrow(self, sql, jid):
        return self.jur.get(jid)

    async def fetch(self, sql, *args):
        if "FROM jurisdictions" in sql:
            if isinstance(args[0], list):
                return [self.jur[i] for i in args[0] if i in self.jur]
            return [self.jur["P1"], self.jur["P2"]]
        ids = args[0]
        vals = {"T": 1_000_000.0, "P1": 450_000.0}
        return [{"jurisdiction_id": i, "value": v, "as_of": None} for i, v in vals.items() if i in ids]


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        conn = self.conn

        class _Ctx:
            async def __aenter__(self_):
                return conn

            async def __aexit__(self_, *a):
                return False

        return _Ctx()


@pytest.fixture
def fake_pool(monkeypatch):
    async def _get():
        return FakePool(FakeConn())
    monkeypatch.setattr(benchmark, "get_db_pool", _get)


@pytest.mark.asyncio
async def test_endpoint_auto_peers_null_for_missing_data(fake_pool):
    res = await benchmark.benchmark("federal_cdbg", jurisdiction_id="T", peers="auto", n=5, fiscal_year=None)
    assert res.jurisdiction.per_capita == 10.0
    by = {p.jurisdiction_id: p for p in res.peers}
    assert by["P1"].per_capita == 5.0
    assert by["P2"].value is None and by["P2"].per_capita is None  # never 0
    assert res.rank_per_capita == {"rank": 1, "of": 2}
    assert res.peer_median_per_capita == 5.0
    assert res.fiscal_year is None


@pytest.mark.asyncio
async def test_endpoint_explicit_peers_and_year_is_string(fake_pool):
    res = await benchmark.benchmark("federal_total", jurisdiction_id="T", peers="P1", n=5, fiscal_year=2023)
    assert [p.jurisdiction_id for p in res.peers] == ["P1"]
    assert res.fiscal_year == "2023"


@pytest.mark.asyncio
async def test_unknown_metric_and_jurisdiction(fake_pool):
    with pytest.raises(HTTPException) as e1:
        await benchmark.benchmark("nope", jurisdiction_id="T", peers="auto", n=5, fiscal_year=None)
    assert e1.value.status_code == 404
    with pytest.raises(HTTPException) as e2:
        await benchmark.benchmark("federal_cdbg", jurisdiction_id="ZZ", peers="auto", n=5, fiscal_year=None)
    assert e2.value.status_code == 404
