"""GET /api/data-centers/concerns (#251, DC-4.3): what residents object to, by area."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import data_centers

PATH = "/api/data-centers/concerns"


class _Conn:
    def __init__(self, area=None, national=None, error: Exception | None = None):
        self.area, self.national, self.error = area or [], national or [], error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        return self.national if "area_level = 'national'" in sql else self.area


class _Acquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_):
        return None


class _Pool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Acquire(self.conn)


@pytest.fixture
def get(monkeypatch):
    def _get(conn: _Conn, params: dict[str, Any] | None = None) -> httpx.Response:
        async def pool():
            return _Pool(conn)

        monkeypatch.setattr(data_centers, "get_db_pool", pool)
        app = FastAPI()
        app.include_router(data_centers.router, prefix="/api")

        async def go():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
                return await c.get(PATH, params=params)

        return asyncio.run(go())

    return _get


def _row(concern: str, n: int, total: int, rank: int, dominant: bool, j: str | None = "Tuscaloosa",
         towns: list[str] | None = None) -> dict:
    if towns is None:
        towns = [j] if j else []
    return dict(concern=concern, mention_count=n, objection_count=total, share=n / total, concern_rank=rank,
                is_dominant=dominant, jurisdiction_name=j, last_meeting_on=date(2026, 6, 10), jurisdictions=towns)


def test_city_returns_area_and_national(get) -> None:
    conn = _Conn(area=[_row("water", 3, 4, 1, True), _row("noise", 1, 4, 2, False)],
                 national=[_row("water", 3, 6, 1, True, None)])
    body = get(conn, {"state": "AL", "city": "Tuscaloosa"}).json()
    assert body["scope"]["level"] == "city"
    assert [i["concern"] for i in body["items"]] == ["water", "noise"]
    assert body["items"][0]["is_dominant"] and body["items"][0]["share"] == 0.75
    assert body["national"][0]["share"] == 0.5
    area_sql, area_params = conn.calls[1]
    assert "area_level = 'jurisdiction'" in area_sql and area_params == ("AL", "%Tuscaloosa%")
    assert body["items"][0]["jurisdictions"] == ["Tuscaloosa"]
    assert body["national"][0]["jurisdictions"] == []


def test_national_scope_reuses_the_national_rows(get) -> None:
    conn = _Conn(national=[_row("water", 3, 6, 1, True, None)])
    body = get(conn).json()
    assert body["scope"]["level"] == "national" and body["items"] == body["national"]
    assert len(conn.calls) == 1


def test_no_concern_data_is_empty_not_invented(get) -> None:
    body = get(_Conn(), {"state": "WY"}).json()
    assert body["items"] == [] and body["national"] == []


def test_missing_mart_and_errors(get) -> None:
    assert get(_Conn(error=asyncpg.exceptions.UndefinedTableError("x"))).json()["items"] == []
    assert get(_Conn(error=RuntimeError("boom"))).status_code == 500


# --- #1139: a state or city scope is one row per concern, not one per town ---------------


def _norm(sql: str) -> str:
    return " ".join(sql.split())


def test_state_sql_aggregates_by_concern_across_towns() -> None:
    scope = data_centers.JobClaimScope(level="state", state_code="TX", state="Texas")
    area_sql, params, national_sql = data_centers.build_concerns_queries(scope)
    sql = _norm(area_sql)
    assert params == ["TX"] and "state_code = $1" in sql
    assert "GROUP BY concern" in sql and "sum(mention_count)" in sql
    # share over the scope's own mentions, re-ranked, towns listed once each and sorted
    assert "sum(c.mention_count) OVER ()" in sql
    assert "rank() OVER (ORDER BY c.mention_count DESC)" in sql
    assert "array_agg(DISTINCT jurisdiction_name ORDER BY jurisdiction_name)" in sql
    # each town's objection total counted once, not once per concern
    assert "SELECT DISTINCT state_code, jurisdiction_name, objection_count" in sql
    assert sql.endswith("ORDER BY concern_rank, concern")
    assert "ARRAY[]::text[] AS jurisdictions" in national_sql


def test_city_sql_aggregates_too() -> None:
    scope = data_centers.JobClaimScope(level="city", state_code="AL", state="Alabama", city="Tuscaloosa")
    area_sql, params, _ = data_centers.build_concerns_queries(scope)
    sql = _norm(area_sql)
    assert params == ["AL", "%Tuscaloosa%"]
    assert "jurisdiction_name ILIKE $2" in sql and "GROUP BY concern" in sql


def test_national_scope_has_no_area_sql() -> None:
    area_sql, params, _ = data_centers.build_concerns_queries(data_centers.JobClaimScope(level="national"))
    assert area_sql is None and params == []


def test_state_single_concern_lists_its_towns(get) -> None:
    # Texas: water in Denison and in Odessa, 1 mention each, comes back as ONE water row.
    water = _row("water", 2, 2, 1, False, None, towns=["Denison", "Odessa"])
    water["share"] = 1.0
    conn = _Conn(area=[water], national=[_row("traffic", 406, 5221, 1, True, None)])
    body = get(conn, {"state": "TX"}).json()
    assert body["scope"]["level"] == "state"
    assert [i["concern"] for i in body["items"]] == ["water"]
    item = body["items"][0]
    assert item["mention_count"] == 2 and item["share"] == 1.0
    assert item["jurisdictions"] == ["Denison", "Odessa"] and item["jurisdiction_name"] is None
