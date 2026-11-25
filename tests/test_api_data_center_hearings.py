"""GET /api/data-centers/hearings (#955): hearings verified against their official page.

The DB layer is mocked: ``get_db_pool`` returns a fake pool that records SQL and params and
returns canned rows. Which leads are verified is decided in dbt (data_center_hearing).
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import data_centers

PATH = "/api/data-centers/hearings"


class _Conn:
    def __init__(self, items=None, counts=None, error: Exception | None = None):
        self.items, self.counts, self.error = items or [], counts or [], error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        return self.counts if "AS upcoming" in sql and "LIMIT" not in sql else self.items


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


def _hearing(**kw) -> dict[str, Any]:
    base: dict[str, Any] = {
        "data_center_hearing_id": "deer-park-tx-2026-12-01", "jurisdiction_id": "j1",
        "jurisdiction_name": "Deer Park", "state_code": "TX", "state": "Texas",
        "body_name": "City Council and Planning & Zoning Commission", "topic": "Joint public hearing",
        "meeting_date": date(2026, 12, 1), "source_url": "https://cityofdeerpark.legistar.com/x",
        "source_name": "City Legistar", "evidence": "amend the zoning ordinance as it relates to <mark>data</mark> <mark>centers</mark>",
        "checked_at": None, "is_upcoming": True,
    }
    base.update(kw)
    return base


def test_state_scope_serves_verified_hearings_with_their_official_link(get) -> None:
    conn = _Conn(items=[_hearing()], counts=[{"upcoming": 1, "past": 0}])
    resp = get(conn, {"state": "Texas"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scope"]["state_code"] == "TX" and body["available"] is True
    assert body["counts"] == {"upcoming": 1, "past": 0}
    (h,) = body["items"]
    assert h["source_url"].startswith("https://") and "<mark>" in h["evidence"]
    items_sql, params = conn.calls[0]
    assert "h.status = 'verified'" in items_sql and "h.meeting_date >= current_date" in items_sql
    assert params == ("TX", data_centers.HEARINGS_DEFAULT)


def test_only_verified_rows_are_ever_queried() -> None:
    scope = data_centers.build_scope(None, None, None)
    for when in ("upcoming", "past", "all"):
        items_sql, _, counts_sql, _ = data_centers.build_hearing_queries(scope, when, 5)
        assert "h.status = 'verified'" in items_sql and "h.status = 'verified'" in counts_sql


def test_city_scope_and_when(get) -> None:
    conn = _Conn(counts=[{"upcoming": 0, "past": 0}])
    get(conn, {"state": "GA", "city": "Savannah", "when": "past"})
    items_sql, params = conn.calls[0]
    assert "h.jurisdiction_name ILIKE $2" in items_sql and "h.meeting_date < current_date" in items_sql
    assert params[:2] == ("GA", "%Savannah%")


def test_missing_table_is_unavailable_not_zero(get) -> None:
    body = get(_Conn(error=asyncpg.exceptions.UndefinedTableError("no relation")), {"state": "AZ"}).json()
    assert body["available"] is False and body["items"] == []
    assert body["counts"] == {"upcoming": None, "past": None}


def test_bad_when_and_limit_are_rejected(get) -> None:
    assert get(_Conn(), {"when": "soon"}).status_code == 422
    assert get(_Conn(), {"limit": data_centers.HEARINGS_MAX + 1}).status_code == 422


def test_other_errors_are_500(get) -> None:
    assert get(_Conn(error=RuntimeError("boom"))).status_code == 500
