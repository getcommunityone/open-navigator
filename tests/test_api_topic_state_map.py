"""GET /api/topics/{topic_id}/state-map (#1127): meetings per state plus the AI reading behind a topic's box map.

The DB layer is mocked: ``get_db_pool`` returns a fake pool that routes each SQL to canned rows. The rows are test
stand-ins for the shapes the marts return, not warehouse figures.
"""

from __future__ import annotations

import asyncio
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import topics

PATH = "/api/topics/{}/state-map"

MEETINGS = [
    {"state_code": "TX", "state": "Texas", "meetings": 12},
    {"state_code": "WI", "state": "Wisconsin", "meetings": 5},
]
LEAN = [
    {
        "state_code": "TX",
        "lean_meetings": 6,
        "public_against_meetings": 3,
        "public_for_meetings": 1,
        "no_side_meetings": 2,
        "disagreement_meetings": 1,
    }
]


class _Conn:
    def __init__(self, lean: list[dict[str, Any]] | None, lean_error: bool = False):
        self.lean = lean
        self.lean_error = lean_error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if "topic_meeting_lean" in sql:
            if self.lean_error:
                raise asyncpg.exceptions.UndefinedTableError('relation "topic_meeting_lean" does not exist')
            return self.lean or []
        if "topic_transcript_link" in sql:
            return [m for m in MEETINGS if params[1] is None or m["state_code"] == params[1]]
        return []


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
    def _get(conn: _Conn, topic_id: int, params: dict[str, Any] | None = None) -> httpx.Response:
        async def pool():
            return _Pool(conn)

        monkeypatch.setattr(topics, "get_db_pool", pool)
        app = FastAPI()
        app.include_router(topics.router)

        async def go():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
                return await c.get(PATH.format(topic_id), params=params or {})

        return asyncio.run(go())

    return _get


def test_merges_the_ai_reading_into_each_state(get):
    r = get(_Conn(LEAN), 100006)
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    tx, wi = body["by_state"]
    assert tx == {
        "state_code": "TX",
        "state": "Texas",
        "meetings": 12,
        "lean_meetings": 6,
        "public_against_meetings": 3,
        "public_for_meetings": 1,
        "no_side_meetings": 2,
        "disagreement_meetings": 1,
    }
    # A state with meetings but no reading keeps its meetings and reads 0, not missing.
    assert wi["meetings"] == 5 and wi["lean_meetings"] == 0 and wi["public_against_meetings"] == 0


def test_missing_lean_table_means_meetings_only_not_an_error(get):
    r = get(_Conn(None, lean_error=True), 100006)
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert [s["meetings"] for s in body["by_state"]] == [12, 5]
    assert all(s["lean_meetings"] == 0 for s in body["by_state"])


def test_no_reading_for_the_topic_is_not_available(get):
    r = get(_Conn([]), 100006)
    assert r.json()["available"] is False


def test_state_scope_is_passed_to_both_queries(get):
    conn = _Conn(LEAN)
    r = get(conn, 100006, {"state": " tx "})
    assert r.status_code == 200
    assert [s["state_code"] for s in r.json()["by_state"]] == ["TX"]
    assert all(params == (100006, "TX") for _, params in conn.calls)


def test_lean_sql_reads_the_topic_and_counts_meetings():
    sql = topics._TOPIC_LEAN_BY_STATE_SQL
    assert "FROM topic_meeting_lean l" in sql
    assert "l.topic_id = $1" in sql
    assert "officials_sided_against_public" in sql
