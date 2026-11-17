"""GET /api/policy-question (#483): the moratorium outcome family reaches the API."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from api.routes import policy_questions

QID = "f7001f99695ccecb1e8df4ab0ee721fd"


class _Conn:
    """Fake asyncpg connection: returns canned rows."""

    def __init__(self, row: dict[str, Any] | None = None, rows: list[dict[str, Any]] | None = None):
        self.row, self.rows = row, rows or []
        self.calls: list[str] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append(sql)
        return self.rows

    async def fetchrow(self, sql: str, *params: Any):
        self.calls.append(sql)
        return self.row

    async def fetchval(self, sql: str, *params: Any):
        self.calls.append(sql)
        return 0


class _Acquire:
    def __init__(self, conn: _Conn):
        self.conn = conn

    async def __aenter__(self) -> _Conn:
        return self.conn

    async def __aexit__(self, *_: Any) -> None:
        return None


class _Pool:
    def __init__(self, conn: _Conn):
        self.conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self.conn)


@pytest.fixture
def get(monkeypatch):
    def _get(conn: _Conn, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        async def pool():
            return _Pool(conn)

        monkeypatch.setattr(policy_questions, "get_db_pool", pool)
        app = FastAPI()
        app.include_router(policy_questions.router, prefix="/api")

        async def go():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
                return await c.get(path, params=params)

        return asyncio.run(go())

    return _get


def _detail_row(**overrides: Any) -> dict[str, Any]:
    row = dict(
        question_id=QID, canonical_text="Should we allow new data centers?", topic_code=None,
        primary_theme="economic_development", cofog_code=None, scope="local", status="active",
        first_seen=None, instances_total=4, decisions_total=4, bills_total=0, jurisdictions_total=4,
        jurisdictions_approved=1, states_total=2, approved_count=1, denied_count=1, deferred_count=0,
        moratorium_count=2, other_count=0, is_featured=True, display_order=1,
        money_total=0, money_share=0, talk_share=0,
    )
    row.update(overrides)
    return row


def test_list_projects_moratorium_count() -> None:
    assert "moratorium_count" in policy_questions._LIST_COLS


def test_summary_defaults_moratorium_count_to_zero() -> None:
    assert policy_questions.PolicyQuestionSummary(question_id=QID).moratorium_count == 0
    assert policy_questions.RollupOut().moratorium_count == 0


def test_detail_returns_moratorium_in_rollup_and_summary(get) -> None:
    body = get(_Conn(row=_detail_row()), f"/api/policy-question/{QID}").json()
    assert body["moratorium_count"] == 2
    assert body["rollup"]["moratorium_count"] == 2
    assert body["rollup"]["approved_count"] == 1 and body["rollup"]["denied_count"] == 1


def test_detail_without_moratorium_column_reads_zero(get) -> None:
    row = _detail_row()
    row.pop("moratorium_count")
    body = get(_Conn(row=row), f"/api/policy-question/{QID}").json()
    assert body["moratorium_count"] == 0 and body["rollup"]["moratorium_count"] == 0


def test_list_passes_moratorium_count_through(get) -> None:
    rows = [dict(question_id=QID, canonical_text="Should we allow new data centers?", moratorium_count=5,
                 instances_total=25, jurisdictions_total=15, jurisdictions_approved=3,
                 is_featured=True, display_order=1)]
    body = get(_Conn(rows=rows), "/api/policy-question/", {"featured": "true"}).json()
    assert body[0]["moratorium_count"] == 5
