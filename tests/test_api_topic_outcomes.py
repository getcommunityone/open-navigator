"""GET /api/topics/{topic}/outcomes (#1314): the chain from meeting to outcome."""
from __future__ import annotations

import asyncio
import os
from datetime import date
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import topic_outcomes as to


class _Conn:
    """Answers by the SQL it is handed (matched on a marker), recording the calls; missing relations raise."""

    def __init__(self, answers: dict[str, list[dict]] | None = None, missing: tuple[str, ...] = ()):
        self.answers = answers or {}
        self.missing = missing
        self.calls: list[tuple[str, tuple]] = []

    async def fetch(self, sql: str, *args: Any):
        self.calls.append((sql, args))
        for table in self.missing:
            if table in sql:
                raise asyncpg.exceptions.UndefinedTableError(table)
        if sql is to._MEETINGS_SQL or sql is to._MEETINGS_DC_SQL:
            return self.answers.get("meetings", [{"n": 0}])
        if sql is to._MEETINGS_EX_SQL:
            return self.answers.get("meetings_ex", [])
        if "GROUP BY r.lean" in sql:
            return self.answers.get("lean", [])
        if "GROUP BY r.outcome" in sql:
            return self.answers.get("actions", [])
        if "top.lean AS label" in sql:
            return self.answers.get("lean_ex", [])
        if "top.outcome AS label" in sql:
            return self.answers.get("actions_ex", [])
        if sql is to._BILLS_SQL:
            return self.answers.get("bills", [])
        if sql is to._LINKS_SQL:
            return self.answers.get("links", [{"meetings": 0, "bills": 0}])
        if sql is to._LINKS_METHOD_SQL:
            return self.answers.get("link_methods", [])
        if sql is to._UPCOMING_SQL:
            return self.answers.get("upcoming", [{"n": 0}])
        if sql is to._PENDING_SQL:
            return self.answers.get("pending", [])
        return []


class _Acquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *a):
        return False


class _Pool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Acquire(self.conn)


def _get(monkeypatch, conn, path: str, params: dict | None = None) -> httpx.Response:
    async def pool():
        return _Pool(conn)

    monkeypatch.setattr(to, "get_db_pool", pool)
    app = FastAPI()
    app.include_router(to.router)

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(path, params=params)

    return asyncio.run(go())


def test_chain_counts_and_examples(monkeypatch) -> None:
    conn = _Conn({
        "meetings": [{"n": 9}],
        "meetings_ex": [{"video_id": "v1", "event_title": "Council", "event_date": date(2026, 5, 1), "state_code": "GA",
                         "jurisdiction_name": "Macon", "video_url": "https://y/v1", "evidence_passage": "the <mark>fluoride</mark>"}],
        "lean": [{"lean": "mostly_opposed", "n": 3}, {"lean": "mixed", "n": 1}, {"lean": "did_not_speak", "n": 4},
                 {"lean": "mostly_supported", "n": 2}],
        "actions": [{"outcome": "advanced", "n": 2}, {"outcome": "tabled_or_deferred", "n": 1},
                    {"outcome": "discussed_no_action", "n": 5}],
        "actions_ex": [{"video_id": "v2", "state_code": "GA", "jurisdiction_name": "Macon", "meeting_date": date(2026, 4, 1),
                        "label": "advanced", "event_title": None, "video_url": None}],
        "bills": [{"status": "pending", "n": 1}, {"status": "failed", "n": 2}],
        "links": [{"meetings": 2, "bills": 3}],
        "link_methods": [{"match_method": "transcript", "n": 3}, {"match_method": "decision", "n": 1}],
        "upcoming": [{"n": 1}],
        "pending": [{"total": 4}],
    })
    r = _get(monkeypatch, conn, "/api/topics/water-fluoridation/outcomes", {"state": "ga"})
    assert r.status_code == 200
    s = r.json()["steps"]
    assert r.json()["state"] == "Georgia"
    assert s["meetings"]["count"] == 9 and s["meetings"]["examples"][0]["detail"] == "the <mark>fluoride</mark>"
    assert s["public"]["count"] == 6 and s["public"]["silent"] == 4 and s["public"]["read"] == 10
    assert s["public"]["by_lean"] == {"opposed": 3, "mixed": 1, "supportive": 2}
    assert s["actions"]["count"] == 3 and s["actions"]["by_outcome"] == {"advanced": 2, "tabled": 1}
    assert s["actions"]["examples"][0]["url"] == "https://www.youtube.com/watch?v=v2"
    assert s["actions"]["examples"][0]["detail"] == "advanced"
    assert s["bills"]["count"] == 3 and s["bills"]["by_status"] == {"pending": 1, "failed": 2}
    assert s["linked_bills"]["count"] == 2 and s["linked_bills"]["bills"] == 3
    assert s["linked_bills"]["by_method"] == {"transcript": 3, "decision": 1}
    assert s["next"] == {"available": True, "count": 5, "examples": [], "upcoming": 1, "pending_bills": 4}
    # Every query got the same scope.
    assert all(a[:2] == ("water-fluoridation", "GA") for _, a in conn.calls)


def test_data_centers_reads_its_own_reading(monkeypatch) -> None:
    conn = _Conn({"actions": [{"outcome": "approved", "n": 2}, {"outcome": "moratorium", "n": 1}, {"outcome": "denied", "n": 1}]})
    s = _get(monkeypatch, conn, "/api/topics/data-centers/outcomes").json()["steps"]
    assert s["actions"]["by_outcome"] == {"advanced": 2, "moratorium": 1, "blocked": 1}
    assert any("data_center_meeting_lean" in sql for sql, _ in conn.calls)
    assert not any("topic_meeting_lean" in sql for sql, _ in conn.calls)


def test_unpublished_relation_is_unavailable(monkeypatch) -> None:
    s = _get(monkeypatch, _Conn(missing=("meeting_bill_link", "topic_upcoming")), "/api/topics/guns/outcomes").json()["steps"]
    assert s["linked_bills"]["available"] is False and s["linked_bills"]["count"] == 0
    assert s["next"]["available"] is False
    assert s["meetings"]["available"] is True


def test_bad_inputs(monkeypatch) -> None:
    assert _get(monkeypatch, _Conn(), "/api/topics/Bad Topic!/outcomes").status_code == 400
    assert _get(monkeypatch, _Conn(), "/api/topics/guns/outcomes", {"state": "Georgia"}).status_code == 400


# --- the live warehouse: each step equals its mart ------------------------------------------------------------------------

# The local warehouse (CLAUDE.md: localhost:5433), from the same variables the API reads; skipped when unreachable.
_DB = {
    "host": os.environ.get("TOPIC_TEST_DB_HOST", "localhost"),
    "port": int(os.environ.get("TOPIC_TEST_DB_PORT", "5433")),
    "user": os.environ.get("POSTGRES_USER", "postgres"),
    "password": os.environ.get("POSTGRES_PASSWORD", ""),
    "database": "open_navigator",
}


@pytest.mark.parametrize("topic,state", [("water-fluoridation", None), ("water-fluoridation", "GA"),
                                         ("data-centers", "VA"), ("data-centers", None)])
def test_live_counts_match_marts(monkeypatch, topic: str, state: str | None) -> None:
    async def run():
        try:
            pool = await asyncpg.create_pool(**_DB, min_size=1, max_size=2, timeout=3,
                                             server_settings={"search_path": "public"})
        except Exception:
            return None
        try:
            async with pool.acquire() as c:
                try:
                    tid = await c.fetchval("SELECT topic_id FROM civicsearch_topic WHERE query_id = $1", topic)
                    if topic == "data-centers":
                        meetings = await c.fetchval(
                            "SELECT count(DISTINCT video_id) FROM data_center_meeting_mention"
                            " WHERE ($1::text IS NULL OR state_code = $1)", state)
                    else:
                        meetings = await c.fetchval(
                            "SELECT count(DISTINCT video_id) FROM topic_transcript_link WHERE topic_id = $1"
                            " AND ($2::text IS NULL OR state_code = $2)", tid, state)
                    bills = await c.fetchval(
                        "SELECT count(*) FROM topic_legislation_bill WHERE topic_id = $1"
                        " AND ($2::text IS NULL OR state_code = $2)", tid, state)
                    links = await c.fetchval(
                        "SELECT count(DISTINCT m.meeting_key) FROM meeting_bill_link m WHERE ($2::text IS NULL OR m.state_code = $2)"
                        " AND EXISTS (SELECT 1 FROM topic_legislation_bill b WHERE b.topic_id = $1 AND b.bill_id = m.bill_uid)",
                        tid, state)
                    if topic == "data-centers":
                        acted = await c.fetchval(
                            "SELECT count(*) FROM data_center_meeting_lean WHERE NOT coalesce(excluded_no_item, false)"
                            " AND dc_outcome IN ('approved', 'denied', 'moratorium', 'tabled_or_deferred')"
                            " AND ($1::text IS NULL OR state_code = $1)", state)
                    else:
                        acted = await c.fetchval(
                            "SELECT count(*) FROM topic_meeting_lean WHERE topic_id = $1 AND NOT coalesce(excluded_no_item, false)"
                            " AND outcome_group IN ('advanced', 'blocked', 'tabled_or_deferred')"
                            " AND ($2::text IS NULL OR state_code = $2)", tid, state)
                except asyncpg.exceptions.UndefinedTableError:
                    return None

            async def get_pool():
                return pool

            monkeypatch.setattr(to, "get_db_pool", get_pool)
            app = FastAPI()
            app.include_router(to.router)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
                r = await client.get(f"/api/topics/{topic}/outcomes", params={"state": state} if state else None)
            return (int(meetings), int(bills), int(links), int(acted)), r.json()["steps"]
        finally:
            await pool.close()

    out = asyncio.run(run())
    if out is None:
        pytest.skip("local warehouse or the marts are not reachable")
    (meetings, bills, links, acted), s = out
    assert s["meetings"]["count"] == meetings
    assert s["bills"]["count"] == bills
    assert s["linked_bills"]["count"] == links
    assert s["actions"]["count"] == acted
    assert all("<mark>" in (e["detail"] or "") for e in s["linked_bills"]["examples"])
