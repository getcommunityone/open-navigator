"""GET /api/topics/{topic}/upcoming (#1302): scheduled meetings, hearings and still-open state bills."""
from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, timezone
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import topic_upcoming


class _Conn:
    """Answers by the SQL constant it is handed; records every call."""

    def __init__(self, counts=None, items=None, pending=None, latest=None, meta=None, up_counts=None, missing=False):
        self.counts = counts or []
        self.items = items or []
        self.pending = pending or []
        self.latest = latest
        self.meta = meta if meta is not None else {"topic_id": 100001, "built_at": datetime(2026, 11, 27, tzinfo=timezone.utc)}
        self.up_counts = up_counts or []
        self.missing = missing
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.missing:
            raise asyncpg.exceptions.UndefinedTableError("missing")
        if sql is topic_upcoming._COUNTS_SQL:
            # The first counts call is the scope's; a second one is the broader scope's.
            n = sum(1 for s, _ in self.calls if s is topic_upcoming._COUNTS_SQL)
            return self.counts if n == 1 else self.up_counts
        if sql is topic_upcoming._ITEMS_SQL:
            return self.items
        if sql is topic_upcoming._PENDING_SQL:
            return self.pending
        return []

    async def fetchrow(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.missing:
            raise asyncpg.exceptions.UndefinedTableError("missing")
        if sql is topic_upcoming._TOPIC_SQL:
            return self.meta
        if sql is topic_upcoming._LATEST_ACTION_SQL:
            return {"latest": self.latest}
        return None


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


def _get(monkeypatch, conn: _Conn, path: str, params: dict | None = None) -> httpx.Response:
    async def pool():
        return _Pool(conn)

    monkeypatch.setattr(topic_upcoming, "get_db_pool", pool)
    app = FastAPI()
    app.include_router(topic_upcoming.router)

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(path, params=params)

    return asyncio.run(go())


def _item(**kw) -> dict[str, Any]:
    base = {
        "topic_upcoming_id": "u1", "topic_id": 100001, "kind": "hearing", "match_basis": "official_notice",
        "item_date": date(2026, 12, 15), "item_time": None, "jurisdiction_name": "Savannah", "state_code": "GA",
        "state": "GA", "body_name": "Metropolitan Planning Commission", "title": "Data center ordinance hearing",
        "location": None, "source_url": "https://savannahga.gov/datacenters", "source_label": "Official notice",
        "matched_text": "the <mark>data center</mark> ordinance", "prior_meeting_date": None, "prior_url": None,
        "tentative": True,
    }
    base.update(kw)
    return base


def _count(kind: str, n: int) -> dict[str, Any]:
    return {"kind": kind, "n": n, "topic_id": 100001, "last_updated": datetime(2026, 11, 25, tzinfo=timezone.utc),
            "built_at": datetime(2026, 11, 27, tzinfo=timezone.utc)}


def test_items_counts_and_evidence(monkeypatch) -> None:
    conn = _Conn(
        counts=[_count("hearing", 1), _count("meeting", 5)],
        items=[
            _item(),
            _item(topic_upcoming_id="u2", kind="meeting", match_basis="place_discussed_before",
                  prior_meeting_date=date(2026, 6, 15), prior_url="https://youtu.be/x", source_label="Livestream"),
            _item(topic_upcoming_id="u3", item_date=None),  # never shown: no date
            _item(topic_upcoming_id="u4", matched_text=None),  # never shown: no evidence
        ],
    )
    r = _get(monkeypatch, conn, "/api/topics/Data-Centers/upcoming", {"state": "ga"})
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True and body["topic_id"] == 100001
    assert body["state_code"] == "GA" and body["state"] == "Georgia"
    assert body["total"] == 6 and body["counts"] == {"meeting": 5, "hearing": 1, "deadline": 0, "bill_action": 0, "event": 0}
    assert [i["upcoming_id"] for i in body["items"]] == ["u1", "u2"]
    assert body["items"][0]["date"] == "2026-12-15" and body["items"][0]["state"] == "Georgia"
    assert body["items"][0]["tentative"] is True
    assert body["items"][1]["prior_meeting_date"] == "2026-06-15"
    assert body["broader"] is None  # the scope has items
    assert body["last_updated"].startswith("2026-11-25")
    _, params = next(c for c in conn.calls if c[0] is topic_upcoming._ITEMS_SQL)
    assert params == ("data-centers", "GA", None, 12)


def test_hosted_by_org_event(monkeypatch) -> None:
    conn = _Conn(
        counts=[_count("event", 1)],
        items=[_item(topic_upcoming_id="e1", kind="event", match_basis="hosted_by_org", source_label="Event page",
                     source_url="https://www.example.org/events/town-hall", body_name=None,
                     title="Town hall on water", matched_text="to improve <mark>oral health</mark>",
                     host_org_name="Georgia Oral Health Coalition", host_master_org_id="m1")],
    )
    body = _get(monkeypatch, conn, "/api/topics/water-fluoridation/upcoming", {"state": "GA"}).json()
    assert body["counts"]["event"] == 1 and body["total"] == 1
    item = body["items"][0]
    assert item["kind"] == "event" and item["match_basis"] == "hosted_by_org"
    assert item["host_org_name"] == "Georgia Oral Health Coalition" and item["host_master_org_id"] == "m1"


def test_empty_state_offers_national(monkeypatch) -> None:
    conn = _Conn(counts=[], up_counts=[_count("meeting", 1)])
    body = _get(monkeypatch, conn, "/api/topics/water-fluoridation/upcoming", {"state": "GA"}).json()
    assert body["total"] == 0 and body["items"] == []
    assert body["broader"] == {"state_code": None, "label": "National", "total": 1}


def test_empty_city_offers_its_state(monkeypatch) -> None:
    conn = _Conn(counts=[], up_counts=[_count("meeting", 2)])
    body = _get(monkeypatch, conn, "/api/topics/data-centers/upcoming", {"state": "AL", "city": "Tuscaloosa"}).json()
    assert body["city"] == "Tuscaloosa"
    assert body["broader"] == {"state_code": "AL", "label": "Alabama", "total": 2}
    scoped = [p for s, p in conn.calls if s is topic_upcoming._COUNTS_SQL]
    assert scoped == [("data-centers", "AL", "Tuscaloosa"), ("data-centers", "AL", None)]


def test_city_without_state_is_ignored(monkeypatch) -> None:
    conn = _Conn(counts=[_count("meeting", 1)])
    body = _get(monkeypatch, conn, "/api/topics/data-centers/upcoming", {"city": "Tuscaloosa"}).json()
    assert body["city"] is None and body["broader"] is None


def test_pending_bills(monkeypatch) -> None:
    pending = [{
        "bill_id": "b1", "identifier": "HB 1", "title": "Data centers; siting.", "state_code": "VA", "state": "VA",
        "status": "passed_chamber", "last_action_description": "Passed House", "last_action_date": date(2026, 2, 10),
        "url": "https://example.test/b1", "total": 24,
    }]
    conn = _Conn(pending=pending, latest=date(2026, 5, 5))
    body = _get(monkeypatch, conn, "/api/topics/data-centers/upcoming", {"state": "VA"}).json()
    pb = body["pending_bills"]
    assert pb["total"] == 24 and pb["latest_action_seen"] == "2026-05-05"
    assert pb["items"][0] == {
        "bill_id": "b1", "identifier": "HB 1", "title": "Data centers; siting.", "state_code": "VA",
        "state": "Virginia", "status": "passed_chamber", "last_action": "Passed House",
        "last_action_date": "2026-02-10", "url": "https://example.test/b1",
    }


def test_missing_relation_is_empty(monkeypatch) -> None:
    r = _get(monkeypatch, _Conn(missing=True), "/api/topics/data-centers/upcoming")
    assert r.status_code == 200
    assert r.json()["available"] is False and r.json()["items"] == []


def test_bad_inputs(monkeypatch) -> None:
    assert _get(monkeypatch, _Conn(), "/api/topics/Bad Topic!/upcoming").status_code == 400
    assert _get(monkeypatch, _Conn(), "/api/topics/data-centers/upcoming", {"state": "Georgia"}).status_code == 400


# --- the live warehouse: the endpoint's counts equal the mart's -------------------------------------------------------

# The local warehouse (CLAUDE.md: localhost:5433), from the same variables the API reads; skipped when unreachable.
_DB = {
    "host": os.environ.get("TOPIC_TEST_DB_HOST", "localhost"),
    "port": int(os.environ.get("TOPIC_TEST_DB_PORT", "5433")),
    "user": os.environ.get("POSTGRES_USER", "postgres"),
    "password": os.environ.get("POSTGRES_PASSWORD", ""),
    "database": "open_navigator",
}


@pytest.mark.parametrize("topic,state", [("data-centers", None), ("data-centers", "GA"), ("water-fluoridation", None),
                                         ("water-fluoridation", "GA"), ("data-centers", "VA")])
def test_live_counts_match_mart(monkeypatch, topic: str, state: str | None) -> None:
    async def run() -> tuple[int, int, dict] | None:
        try:
            pool = await asyncpg.create_pool(**_DB, min_size=1, max_size=2, timeout=3,
                                             server_settings={"search_path": "public"})
        except Exception:
            return None
        try:
            async with pool.acquire() as c:
                try:
                    items = await c.fetchval(
                        "SELECT count(*) FROM public.topic_upcoming WHERE topic_slug = $1"
                        " AND item_date >= current_date AND ($2::text IS NULL OR state_code = $2)", topic, state)
                except asyncpg.exceptions.UndefinedTableError:
                    return None
                bills = await c.fetchval(
                    "SELECT count(*) FROM public.topic_legislation_bill WHERE topic_query_id = $1"
                    " AND status IN ('pending', 'passed_chamber') AND year >= extract(year FROM current_date)::int - 1"
                    " AND coalesce(last_action_description, '') !~* '(chapter|acts of assembly|signed by (the )?governor|approved by (the )?governor|became law)'"
                    " AND ($2::text IS NULL OR state_code = $2)",
                    topic, state)

            async def get_pool():
                return pool

            monkeypatch.setattr(topic_upcoming, "get_db_pool", get_pool)
            app = FastAPI()
            app.include_router(topic_upcoming.router)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
                r = await client.get(f"/api/topics/{topic}/upcoming", params={"state": state} if state else None)
            return int(items), int(bills), r.json()
        finally:
            await pool.close()

    out = asyncio.run(run())
    if out is None:
        pytest.skip("local warehouse or topic_upcoming not reachable")
    want_items, want_bills, body = out
    assert body["total"] == want_items
    assert body["pending_bills"]["total"] == want_bills
    assert all(i["date"] >= body["as_of"] for i in body["items"])
    assert all("<mark>" in i["matched_text"] for i in body["items"])
