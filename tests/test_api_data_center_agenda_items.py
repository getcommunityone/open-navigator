"""GET /api/data-centers/agenda-items (#250, DC-4.2): data center items on agendas.

The DB layer is mocked: ``get_db_pool`` returns a fake pool that records SQL and
params and returns canned rows (counts for the count query, items otherwise).
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

PATH = "/api/data-centers/agenda-items"


class _Conn:
    def __init__(self, rows=None, counts=None, error: Exception | None = None):
        self.rows = rows or []
        self.counts = counts or []
        self.error = error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        return self.counts if "AS upcoming" in sql and "FROM data_center_agenda_item a WHERE" in sql and "LIMIT" not in sql else self.rows


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


def _item(**kw) -> dict[str, Any]:
    base = dict(
        data_center_agenda_item_id="d1", event_meeting_document_id="d1", jurisdiction_id="tuscaloosa_0177256",
        jurisdiction_name="Tuscaloosa", state_code="AL", state="Alabama", body_name="council",
        meeting_title="Regular Council Meeting", doc_date=date(2026, 12, 1), document_url="https://example.org/a.pdf",
        mentions_zoning_or_utility=True,
        evidence="request to rezone 400 acres for a proposed <mark>data</mark> <mark>center</mark>",
        data_center_site_id=None, site_name=None, is_upcoming=True,
    )
    base.update(kw)
    return base


def test_city_scope_counts_and_evidence(get) -> None:
    conn = _Conn(rows=[_item()], counts=[{"upcoming": 1, "past": 3}])
    resp = get(conn, {"state": "Alabama", "city": "Tuscaloosa"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scope"]["level"] == "city" and body["scope"]["state_code"] == "AL" and body["scope"]["city"] == "Tuscaloosa"
    assert body["counts"] == {"upcoming": 1, "past": 3}
    (item,) = body["items"]
    assert "<mark>data</mark>" in item["evidence"] and item["is_upcoming"] is True
    assert item["doc_date"] == "2026-12-01" and item["mentions_zoning_or_utility"] is True
    items_sql, params = conn.calls[0]
    assert "a.state_code = $1" in items_sql and "a.jurisdiction_name ILIKE $2" in items_sql
    assert params == ("AL", "%Tuscaloosa%", 100)
    counts_sql, counts_params = conn.calls[1]
    assert counts_params == ("AL", "%Tuscaloosa%") and "current_date" in counts_sql


def test_when_filters_items_only() -> None:
    scope = data_centers.build_scope(None, None, None)
    up, p, cnt, cp = data_centers.build_agenda_queries(scope, "upcoming", 5)
    assert "a.doc_date >= current_date" in up.split("ORDER BY")[0] and p == [5] and cp == []
    past, _, _, _ = data_centers.build_agenda_queries(scope, "past", 5)
    assert "a.doc_date < current_date" in past.split("ORDER BY")[0]
    everything, _, _, _ = data_centers.build_agenda_queries(scope, "all", 5)
    assert "current_date" not in everything.split("WHERE")[1].split("ORDER BY")[0]


def test_upcoming_sorts_first_soonest_first() -> None:
    sql, _, _, _ = data_centers.build_agenda_queries(data_centers.build_scope(None, None, None), "all", 5)
    order = sql.split("ORDER BY")[1]
    assert order.index("(a.doc_date >= current_date) DESC") < order.index("THEN a.doc_date END ASC") < order.index("a.doc_date DESC")


def test_bad_when_is_422(get) -> None:
    assert get(_Conn(), {"when": "soon"}).status_code == 422


def test_missing_mart_is_an_empty_list(get) -> None:
    resp = get(_Conn(error=asyncpg.exceptions.UndefinedTableError("no relation")))
    assert resp.status_code == 200 and resp.json()["items"] == []


def test_other_errors_are_500(get) -> None:
    assert get(_Conn(error=RuntimeError("boom"))).status_code == 500
