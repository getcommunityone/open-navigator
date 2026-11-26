"""#1032: GET /api/policy-question/{id}/jev, Jev's reading of meetings for a question (DB mocked)."""

import asyncio
from typing import Any

import httpx
from fastapi import FastAPI

from api.routes import policy_questions

QID = "f7001f99695ccecb1e8df4ab0ee721fd"


class _Conn:
    def __init__(self, exists: bool = True, counts: dict[str, Any] | None = None, rows: list[dict[str, Any]] | None = None):
        self.exists, self.counts, self.rows = exists, counts, rows or []
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchval(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.exists if "to_regclass" in sql else bool(self.counts)

    async def fetchrow(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.counts

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.rows


class _Acq:
    def __init__(self, c: _Conn):
        self.c = c

    async def __aenter__(self) -> _Conn:
        return self.c

    async def __aexit__(self, *_: Any) -> None:
        return None


class _Pool:
    def __init__(self, c: _Conn):
        self.c = c

    def acquire(self) -> _Acq:
        return _Acq(self.c)


def _get(monkeypatch, conn: _Conn, params: dict[str, Any] | None = None) -> httpx.Response:
    async def pool():
        return _Pool(conn)

    monkeypatch.setattr(policy_questions, "get_db_pool", pool)
    app = FastAPI()
    app.include_router(policy_questions.router, prefix="/api")

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(f"/api/policy-question/{QID}/jev", params=params)

    return asyncio.run(go())


def test_counts_and_items_with_passage(monkeypatch) -> None:
    conn = _Conn(
        counts=dict(meetings=30, debated=24, approved=17, denied=0, tabled_or_deferred=4, moratorium=5, discussed_no_action=4),
        rows=[dict(video_id="v1", meeting_title="Council", meeting_date=None, jurisdiction_name="Anniston", state_code="AL",
                   outcome="approved", outcome_p=0.9, debated_p=0.8, evidence="the <mark>data</mark> <mark>center</mark>",
                   video_url="https://www.youtube.com/watch?v=v1", start_seconds=12.0)],
    )
    body = _get(monkeypatch, conn, {"state": "AL"}).json()
    assert body["available"] is True and body["meetings"] == 30
    assert body["outcomes"]["approved"] == 17 and body["outcomes"]["moratorium"] == 5
    assert body["items"][0]["evidence"].count("<mark>") == 2
    assert "t=12" in body["items"][0]["jump_url"]


def test_missing_table_is_unavailable_not_zero(monkeypatch) -> None:
    body = _get(monkeypatch, _Conn(exists=False)).json()
    assert body == {"available": False, "scope": body["scope"], "meetings": 0, "debated": 0, "outcomes": {}, "items": []}


def test_bad_outcome_is_422(monkeypatch) -> None:
    assert _get(monkeypatch, _Conn(), {"outcome": "nope"}).status_code == 422
