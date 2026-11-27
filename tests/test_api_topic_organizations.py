"""GET /api/topics/{topic}/organizations (#1345): the nonprofits tied to a topic, ranked by evidence."""
from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, timezone
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import topic_organizations as mod


class _Conn:
    def __init__(self, counts=None, items=None, up_counts=None, missing=False, city_counts=None, served=20):
        self.served = served
        self.counts = counts or []
        self.city_counts = city_counts or []
        self.items = items or []
        self.up_counts = up_counts or []
        self.missing = missing
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.missing:
            raise asyncpg.exceptions.UndefinedTableError("missing")
        if sql is mod._CITY_COUNTS_SQL:
            return self.city_counts
        if sql is mod._COUNTS_SQL:
            n = sum(1 for s, _ in self.calls if s is mod._COUNTS_SQL)
            return self.counts if n == 1 else self.up_counts
        if sql is mod._ITEMS_SQL:
            return self.items
        return []

    async def fetchrow(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if sql is mod._SERVED_SQL:
            return {"n": self.served}
        return None


class _ConnRow(_Conn):
    pass


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
        return conn if isinstance(conn, _RealPool) else _Pool(conn)

    monkeypatch.setattr(mod, "get_db_pool", pool)
    app = FastAPI()
    app.include_router(mod.router)

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(path, params=params)

    return asyncio.run(go())


class _RealPool:  # marker for the live test
    pass


BUILT = datetime(2026, 11, 27, tzinfo=timezone.utc)


def _count(method: str, n: int) -> dict[str, Any]:
    return {"match_method": method, "n": n, "topic_id": 100005, "built_at": BUILT}


def _item(**kw) -> dict[str, Any]:
    base = {
        "master_org_id": "o1", "org_name": "Alabama Gun Owners Association", "city": "tuscaloosa", "state_code": "AL",
        "state": "Alabama", "match_method": "named_in_meeting", "match_methods": ["keyword_in_name", "named_in_meeting"],
        "match_text": "the <mark>alabama gun owners association</mark> spoke on <mark>firearms</mark>",
        "match_source_url": "https://youtu.be/x", "match_date": date(2026, 3, 2), "match_place": "Tuscaloosa",
        "mission": None, "side": "gun rights", "ntee_code": "R60", "revenue": 125000, "revenue_tax_year": 2023,
        "website_url": None,
    }
    base.update(kw)
    return base


def test_items_ranked_with_evidence(monkeypatch) -> None:
    conn = _Conn(
        counts=[_count("named_in_meeting", 1), _count("keyword_in_name", 7)],
        items=[_item(), _item(master_org_id="o2", org_name="Tuscaloosa Rifle Club", match_method="keyword_in_name",
                              match_methods=["keyword_in_name"], match_source_url=None, match_date=None, side=None,
                              revenue=None, revenue_tax_year=None),
               _item(master_org_id=None)],  # never shown without an id
    )
    r = _get(monkeypatch, conn, "/api/topics/Guns/organizations", {"state": "al"})
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True and body["topic_id"] == 100005
    assert body["state_code"] == "AL" and body["state"] == "Alabama"
    assert body["total"] == 8
    assert body["counts"]["named_in_meeting"] == 1 and body["counts"]["keyword_in_name"] == 7
    assert [i["master_org_id"] for i in body["items"]] == ["o1", "o2"]
    first = body["items"][0]
    assert first["city"] == "Tuscaloosa"
    assert first["match_date"] == "2026-03-02"
    assert first["revenue"] == 125000 and first["revenue_tax_year"] == "2023"  # years on the wire as strings
    assert first["side"] == "gun rights"
    assert body["items"][1]["side"] is None and body["items"][1]["revenue_tax_year"] is None
    assert first["match_methods"] == ["named_in_meeting"]
    assert body["broader"] is None and body["partial"] is False
    _, params = next(c for c in conn.calls if c[0] is mod._ITEMS_SQL)
    assert params == ("guns", "AL", None, 12)


def test_ranking_sql_orders_by_evidence_then_revenue() -> None:
    sql = " ".join(mod._ITEMS_SQL.split())
    assert "ORDER BY o.evidence_rank, o.revenue DESC NULLS LAST" in sql


def test_empty_state_offers_national(monkeypatch) -> None:
    conn = _Conn(counts=[], up_counts=[_count("keyword_in_name", 3)])
    body = _get(monkeypatch, conn, "/api/topics/pickleball/organizations", {"state": "WY"}).json()
    assert body["total"] == 0 and body["items"] == []
    assert body["broader"] == {"state_code": None, "label": "National", "total": 3}
    assert body["available"] is True


def test_empty_city_offers_its_state(monkeypatch) -> None:
    conn = _Conn(counts=[_count("ntee_code", 2)], up_counts=[_count("ntee_code", 2)], city_counts=[])
    body = _get(monkeypatch, conn, "/api/topics/guns/organizations", {"state": "AL", "city": "Tuscaloosa"}).json()
    assert body["broader"] == {"state_code": "AL", "label": "Alabama", "total": 2}
    assert [p for s, p in conn.calls if s is mod._CITY_COUNTS_SQL] == [("guns", "AL", "Tuscaloosa")]
    assert body["partial"] is False  # every one of the state's 2 is served, so the city's none is real


def test_city_with_none_served_is_partial_not_a_confident_zero(monkeypatch) -> None:
    conn = _Conn(counts=[_count("ntee_code", 300)], up_counts=[_count("ntee_code", 300)], city_counts=[], served=21)
    body = _get(monkeypatch, conn, "/api/topics/guns/organizations", {"state": "AL", "city": "Dothan"}).json()
    assert body["total"] == 0 and body["partial"] is True
    assert body["broader"]["total"] == 300


def test_city_counts_are_partial_when_the_state_has_more(monkeypatch) -> None:
    conn = _Conn(counts=[_count("keyword_in_name", 60)], city_counts=[_count("keyword_in_name", 3)], items=[_item()], served=21)
    body = _get(monkeypatch, conn, "/api/topics/guns/organizations", {"state": "AL", "city": "Mobile"}).json()
    assert body["total"] == 3 and body["partial"] is True


def test_missing_relation_is_empty(monkeypatch) -> None:
    r = _get(monkeypatch, _Conn(missing=True), "/api/topics/guns/organizations")
    assert r.status_code == 200 and r.json()["available"] is False


def test_bad_inputs(monkeypatch) -> None:
    assert _get(monkeypatch, _Conn(), "/api/topics/Bad Topic!/organizations").status_code == 400
    assert _get(monkeypatch, _Conn(), "/api/topics/guns/organizations", {"state": "Alabama"}).status_code == 400


_DB = {
    "host": os.environ.get("TOPIC_TEST_DB_HOST", "localhost"),
    "port": int(os.environ.get("TOPIC_TEST_DB_PORT", "5433")),
    "user": os.environ.get("POSTGRES_USER", "postgres"),
    "password": os.environ.get("POSTGRES_PASSWORD", ""),
    "database": "open_navigator",
}


@pytest.mark.parametrize("topic,state", [("water-fluoridation", "GA"), ("data-centers", "VA"), ("guns", "AL")])
def test_live_counts_match_mart(monkeypatch, topic: str, state: str) -> None:
    async def run():
        try:
            pool = await asyncpg.create_pool(**_DB, min_size=1, max_size=2, timeout=3,
                                             server_settings={"search_path": "public"})
        except Exception:
            return None
        try:
            async with pool.acquire() as c:
                try:
                    want = await c.fetchval(
                        "SELECT coalesce(sum(n), 0) FROM public.topic_organization_count WHERE topic_slug = $1 AND state_code = $2",
                        topic, state)
                except asyncpg.exceptions.UndefinedTableError:
                    return None

            async def get_pool():
                return pool

            monkeypatch.setattr(mod, "get_db_pool", get_pool)
            app = FastAPI()
            app.include_router(mod.router)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
                r = await client.get(f"/api/topics/{topic}/organizations", params={"state": state, "limit": 50})
            return int(want), r.json()
        finally:
            await pool.close()

    out = asyncio.run(run())
    if out is None:
        pytest.skip("local warehouse or topic_organization not reachable")
    want, body = out
    assert body["total"] == want
    ranks = [mod.METHODS.index(i["match_method"]) for i in body["items"]]
    assert ranks == sorted(ranks)  # strongest evidence first
    assert all(i["state_code"] == state for i in body["items"])
