"""GET /api/data-centers/meeting-mentions (#445): data centers discussed in meeting transcripts.

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

PATH = "/api/data-centers/meeting-mentions"


class _Conn:
    def __init__(self, rows=None, counts=None, error: Exception | None = None, by_state=None):
        self.rows = rows or []
        self.counts = counts or []
        self.by_state = by_state or []
        self.error = error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        if "GROUP BY m.state_code" in sql:
            return self.by_state
        return self.counts if "AS passages" in sql and "LIMIT" not in sql else self.rows


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
        data_center_meeting_mention_id="m1", video_id="7VghnjHd_1w",
        video_url="https://www.youtube.com/watch?v=7VghnjHd_1w", meeting_title="City Council Business Meeting",
        meeting_date=date(2026, 5, 26), jurisdiction_id="charlotte_3712000", jurisdiction_name="Charlotte",
        state_code="NC", state="North Carolina", passage_index=42, start_seconds=7747.466,
        evidence="we encourage you to adopt a temporary moratorium to pause <mark>data</mark> <mark>center</mark> development",
        match_terms=["data center"], match_strength="data_center", data_center_site_id=None, site_name=None,
        site_match_basis=None,
    )
    base.update(kw)
    return base


def test_city_scope_counts_evidence_and_jump(get) -> None:
    conn = _Conn(rows=[_item()], counts=[{"passages": 30, "meetings": 1, "site_specific": 0}])
    resp = get(conn, {"state": "North Carolina", "city": "Charlotte"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scope"] == {
        "level": "city", "state_code": "NC", "state": "North Carolina", "city": "Charlotte", "jurisdiction_id": None,
    }
    assert body["counts"] == {"passages": 30, "meetings": 1, "site_specific": 0, "by_state": []}
    (item,) = body["items"]
    assert "<mark>data</mark>" in item["evidence"]
    assert item["jump_url"] == "https://www.youtube.com/watch?v=7VghnjHd_1w&t=7747s"
    items_sql, params = conn.calls[0]
    assert "m.state_code = $1" in items_sql and "m.jurisdiction_name ILIKE $2" in items_sql
    assert params == ("NC", "%Charlotte%", 100)
    counts_sql, counts_params = conn.calls[1]
    assert counts_params == ("NC", "%Charlotte%") and "LIMIT" not in counts_sql


def test_untimed_passage_has_no_jump(get) -> None:
    conn = _Conn(rows=[_item(start_seconds=None)], counts=[{"passages": 1, "meetings": 1, "site_specific": 0}])
    (item,) = get(conn).json()["items"]
    assert item["start_seconds"] is None and item["jump_url"] is None


def test_national_scope_binds_only_limit() -> None:
    scope = data_centers.build_scope(None, None, None)
    sql, params, counts_sql, counts_params = data_centers.build_mention_queries(scope, None, None, 7)
    assert "WHERE TRUE" in sql and params == [7] and counts_params == []
    assert sql.index("m.meeting_date DESC NULLS LAST") < sql.index("LIMIT $1")


def test_site_and_strength_filters_are_bound() -> None:
    scope = data_centers.build_scope("TX", None, None)
    sql, params, counts_sql, counts_params = data_centers.build_mention_queries(scope, "abc", "site_specific", 5)
    assert "m.data_center_site_id = $2" in sql and "m.match_strength = $3" in sql
    assert params == ["TX", "abc", "site_specific", 5] and counts_params == ["TX", "abc", "site_specific"]


def test_bad_strength_is_422(get) -> None:
    assert get(_Conn(), {"strength": "maybe"}).status_code == 422


def test_missing_mart_is_an_empty_list(get) -> None:
    resp = get(_Conn(error=asyncpg.exceptions.UndefinedTableError("no relation")))
    assert resp.status_code == 200 and resp.json()["items"] == [] and resp.json()["counts"]["passages"] == 0


def test_other_errors_are_500(get) -> None:
    assert get(_Conn(error=RuntimeError("boom"))).status_code == 500


def test_counts_by_state_are_real_distinct_meetings_in_scope(get) -> None:
    """#970: the Overview dot map shades each state by its own count; same filters as the list."""
    conn = _Conn(
        counts=[{"passages": 9, "meetings": 5, "site_specific": 1}],
        by_state=[
            {"state_code": "TX", "state": "Texas", "meetings": 3},
            {"state_code": "NC", "state": "North Carolina", "meetings": 2},
        ],
    )
    body = get(conn).json()
    assert body["counts"]["by_state"] == [
        {"state_code": "TX", "state": "Texas", "meetings": 3},
        {"state_code": "NC", "state": "North Carolina", "meetings": 2},
    ]
    sql, params = next(c for c in conn.calls if "GROUP BY m.state_code" in c[0])
    assert "count(DISTINCT m.video_id)" in sql and "m.state_code IS NOT NULL" in sql and params == ()

    conn = _Conn(counts=[{"passages": 1, "meetings": 1, "site_specific": 0}])
    get(conn, {"state": "NC", "city": "Charlotte"})
    sql, params = next(c for c in conn.calls if "GROUP BY m.state_code" in c[0])
    assert "m.state_code = $1" in sql and "m.jurisdiction_name ILIKE $2" in sql
    assert params == ("NC", "%Charlotte%")


def test_by_state_is_empty_not_missing_when_none(get) -> None:
    body = get(_Conn(counts=[{"passages": 0, "meetings": 0, "site_specific": 0}])).json()
    assert body["counts"]["by_state"] == []
