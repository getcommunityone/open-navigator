"""GET /api/local-finance/property-tax-rate returns median_household_income (#137).

The DB layer is mocked (no live database): ``get_db_pool`` is patched with a fake
pool whose connection records the SQL and returns a canned row.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from api.routes import local_finance

PATH = "/api/local-finance/property-tax-rate"


class _FakeConn:
    def __init__(self, row: dict[str, Any] | None):
        self.row = row
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.row


class _Acquire:
    def __init__(self, conn: _FakeConn):
        self.conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self.conn

    async def __aexit__(self, *_exc: object) -> None:
        return None


class _FakePool:
    def __init__(self, conn: _FakeConn):
        self.conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self.conn)


def _get(app: FastAPI, params: dict[str, Any]) -> httpx.Response:
    async def go() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(PATH, params=params)

    return asyncio.run(go())


@pytest.fixture
def make_app(monkeypatch):
    def _make(conn: _FakeConn) -> FastAPI:
        async def _get_pool():
            return _FakePool(conn)

        monkeypatch.setattr(local_finance, "get_db_pool", _get_pool)
        app = FastAPI()
        app.include_router(local_finance.router)
        return app

    return _make


def _row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "Testville city, Alabama",
        "state_code": "AL",
        "state": "Alabama",
        "geography_type": "place",
        "acs_vintage_year": 2023,
        "median_real_estate_taxes_paid": 900,
        "median_home_value": 180000,
        "effective_property_tax_rate": 0.005,
        "median_household_income": 52000,
    }
    base.update(overrides)
    return base


def test_returns_median_household_income(make_app):
    conn = _FakeConn(_row())
    resp = _get(make_app(conn), {"state": "AL", "city": "Testville"})
    assert resp.status_code == 200
    assert resp.json()["median_household_income"] == 52000


def test_missing_income_is_null_not_zero(make_app):
    conn = _FakeConn(_row(median_household_income=None))
    resp = _get(make_app(conn), {"state": "AL", "city": "Testville"})
    assert resp.status_code == 200
    assert resp.json()["median_household_income"] is None


def test_income_is_read_tolerantly_from_the_serving_table(make_app):
    """A serving table synced before the column existed must not break the query."""
    conn = _FakeConn(_row())
    _get(make_app(conn), {"state": "AL", "city": "Testville"})
    sql = conn.calls[0][0]
    assert "to_jsonb(jurisdiction_property_tax_rate) ->> 'median_household_income'" in sql
