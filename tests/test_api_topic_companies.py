"""GET /api/topics/{query_id}/companies (#1052)."""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import httpx
from fastapi import FastAPI

from api.routes import topic_companies as tc


class _Conn:
    def __init__(self, rows=None, error: Exception | None = None):
        self.rows = rows or []
        self.error = error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        return self.rows


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

    monkeypatch.setattr(tc, "get_db_pool", pool)
    app = FastAPI()
    app.include_router(tc.router)

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(path, params=params)

    return asyncio.run(go())


def _row(**kw) -> dict[str, Any]:
    base = {
        "company_key": "soundthinking", "company_name": "SoundThinking", "aliases": ["SoundThinking", "ShotSpotter"],
        "website_url": "https://www.soundthinking.com/", "master_org_id": None, "meetings": 4, "decisions": 1,
        "mention_kind": "meeting", "title": "City Council", "event_date": date(2026, 5, 1),
        "jurisdiction_name": "Montgomery", "state_code": "AL", "url": "https://www.youtube.com/watch?v=x",
        "evidence": "the <mark>ShotSpotter</mark> contract renewal",
    }
    base.update(kw)
    return base


def test_scope_binds_topic_state_and_city(monkeypatch) -> None:
    conn = _Conn(rows=[_row(), _row(company_key="glock", company_name="Glock", aliases=["Glock"], meetings=0,
                                   decisions=0, mention_kind=None, evidence=None)])
    r = _get(monkeypatch, conn, "/api/topics/Guns/companies", {"state": "al", "city": "Montgomery"})
    body = r.json()
    assert r.status_code == 200
    assert body["topic_query_id"] == "guns"
    assert body["scope"] == {"level": "city", "state_code": "AL", "city": "Montgomery"}
    assert conn.calls[0][1] == ("guns", "AL", "%Montgomery%")
    first, second = body["companies"]
    assert first["meetings"] == 4 and first["newest"]["evidence"].count("<mark>") == 1
    assert first["newest"]["date"] == "2026-05-01"
    assert second["meetings"] == 0 and second["newest"] is None  # named nowhere in scope: no invented mention


def test_national_scope_binds_nulls(monkeypatch) -> None:
    conn = _Conn(rows=[])
    body = _get(monkeypatch, conn, "/api/topics/data-centers/companies").json()
    assert body["scope"]["level"] == "national" and body["companies"] == []
    assert conn.calls[0][1] == ("data-centers", None, None)


def test_missing_tables_return_empty_not_error(monkeypatch) -> None:
    import asyncpg

    r = _get(monkeypatch, _Conn(error=asyncpg.exceptions.UndefinedTableError("nope")), "/api/topics/guns/companies")
    assert r.status_code == 200 and r.json()["companies"] == []


def test_other_errors_are_503(monkeypatch) -> None:
    r = _get(monkeypatch, _Conn(error=RuntimeError("boom")), "/api/topics/guns/companies")
    assert r.status_code == 503
