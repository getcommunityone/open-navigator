"""GET /api/data-centers/decisions (#933): data center decisions, debated or passed without debate.

The DB layer is mocked: ``get_db_pool`` returns a fake pool that records SQL and params and
returns canned rows (counts for the counts query, items otherwise). The rows are test
stand-ins; which decisions are about a data center is decided in dbt (data_center_decision).
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

PATH = "/api/data-centers/decisions"


class _Conn:
    def __init__(self, counts=None, items=None, error: Exception | None = None):
        self.counts = counts or []
        self.items = items or []
        self.error = error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        return self.counts if "count(DISTINCT" in sql else self.items


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
    base: dict[str, Any] = {
        "data_center_decision_id": "d1", "contested": True, "headline": "Rezoning for a data center campus",
        "outcome": "Approved", "votes_for": None, "votes_against": None, "vote_text": None,
        "meeting_date": date(2026, 3, 2), "jurisdiction_name": "Testville", "state_code": "AL",
        "video_url": "https://www.youtube.com/watch?v=vidA", "decision_url": "/decisions/d1",
    }
    base.update(kw)
    return base


def test_state_scope_counts_items_and_bound_params(get) -> None:
    conn = _Conn(
        counts=[{"contested": 1, "uncontested": 1, "meetings": 2}],
        items=[
            _item(),
            _item(data_center_decision_id="u1", contested=False, headline="Approve Data Center Ordinance",
                  vote_text="voice vote", decision_url=None),
        ],
    )
    resp = get(conn, {"state": "Alabama"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scope"]["level"] == "state" and body["scope"]["state_code"] == "AL"
    assert body["available"] is True
    # on_topic / in_passing (#1293) classify every headline in scope: here the two items (the headline query reads them).
    assert body["counts"] == {"contested": 1, "uncontested": 1, "meetings": 2, "on_topic": 2, "in_passing": 0}
    assert {i["relevance"] for i in body["items"]} == {"on_topic"}
    debated, consent = body["items"]
    assert debated["contested"] is True and debated["decision_url"] == "/decisions/d1"
    assert consent["contested"] is False and consent["vote_text"] == "voice vote"
    # an uncontested item's vote is never turned into numbers, and it has no detail page
    assert consent["votes_for"] is None and consent["votes_against"] is None and consent["decision_url"] is None
    counts_sql, params = conn.calls[0]
    assert "d.state_code = $1" in counts_sql and params == ("AL",)
    items_sql, item_params = conn.calls[1]
    assert item_params == ("AL", data_centers.DECISIONS_DEFAULT) and "LIMIT $2" in items_sql


def test_city_scope_filters_by_jurisdiction(get) -> None:
    conn = _Conn(counts=[{"contested": 0, "uncontested": 0, "meetings": 0}])
    body = get(conn, {"state": "GA", "city": "Fayetteville"}).json()
    assert body["scope"]["level"] == "city" and body["scope"]["city"] == "Fayetteville"
    sql, params = conn.calls[0]
    assert "d.jurisdiction_name ILIKE $2" in sql and params == ("GA", "%Fayetteville%")


def test_route_reads_the_mart_only() -> None:
    scope = data_centers.build_scope(None, None, None)
    counts_sql, params, items_sql, item_params = data_centers.build_decision_queries(scope, 5)
    assert "FROM data_center_decision d WHERE TRUE" in counts_sql and params == [] and item_params == [5]
    # the rule for "about a data center" lives in dbt, not here
    assert "~*" not in counts_sql + items_sql and "event_decision" not in counts_sql + items_sql


def test_missing_mart_is_unavailable_not_zero(get) -> None:
    resp = get(_Conn(error=asyncpg.exceptions.UndefinedTableError("no relation")), {"state": "AL"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False and body["scope"]["state_code"] == "AL"
    assert all(v is None for v in body["counts"].values())
    assert body["items"] == []


def test_limit_is_bounded(get) -> None:
    assert get(_Conn(), {"limit": data_centers.DECISIONS_MAX + 1}).status_code == 422


def test_other_errors_are_500(get) -> None:
    assert get(_Conn(error=RuntimeError("boom"))).status_code == 500


def test_relevance_marks_a_procedural_item_in_passing(get) -> None:
    """#1293: a decision whose headline only reshuffles the agenda is "in passing", never a decision on data centers."""
    conn = _Conn(
        counts=[{"contested": 1, "uncontested": 1, "meetings": 1}],
        items=[
            _item(),
            _item(data_center_decision_id="u2", contested=False,
                  headline="Agenda order changed: data center and accessory structure items swapped"),
        ],
    )
    body = get(conn, {"state": "AL"}).json()
    by = {i["data_center_decision_id"]: i for i in body["items"]}
    assert by["d1"]["relevance"] == "on_topic"
    assert by["u2"]["relevance"] == "in_passing"
    assert body["counts"]["on_topic"] == 1 and body["counts"]["in_passing"] == 1
