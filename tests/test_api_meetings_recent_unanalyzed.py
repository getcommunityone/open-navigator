"""GET /api/meetings?sort=recent (#509): recent transcribed-but-unanalyzed meetings.

The DB layer is mocked: ``get_db_pool`` returns a fake pool that records SQL and
params and returns canned rows.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import meeting_browse

PATH = "/api/meetings"


class _Row(dict):
    """asyncpg.Record stand-in: mapping access plus keys()."""


class _Conn:
    def __init__(self, rows=None, total=0, union_error: Exception | None = None):
        self.rows = [_Row(r) for r in (rows or [])]
        self.total = total
        self.union_error = union_error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def _maybe_fail(self, sql: str) -> None:
        if self.union_error and "recent_transcribed_meeting" in sql:
            raise self.union_error

    async def fetchval(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        self._maybe_fail(sql)
        return self.total

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        self._maybe_fail(sql)
        return self.rows


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

        monkeypatch.setattr(meeting_browse, "get_db_pool", pool)
        app = FastAPI()
        app.include_router(meeting_browse.router, prefix="/api")

        async def go():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
                return await c.get(PATH, params=params)

        return asyncio.run(go())

    return _get


def _analyzed(**kw) -> dict[str, Any]:
    base = dict(
        analyzed=True, event_meeting_id=4021, meeting_title="City Council Regular Meeting",
        jurisdiction_name="Tuscaloosa", city="Tuscaloosa", state_code="AL", state="Alabama",
        meeting_date=date(2026, 6, 2), decision_count=3, question_count=1, video_id="abc123",
        video_url=None, evidence=None, evidence_label=None, evidence_start_seconds=None,
    )
    base.update(kw)
    return base


def _unanalyzed(**kw) -> dict[str, Any]:
    base = dict(
        analyzed=False, event_meeting_id=None, meeting_title="Bartow Community Redevelopment Agency Work Session",
        jurisdiction_name="Bartow County", city=None, state_code="GA", state="Georgia",
        meeting_date=date(2026, 11, 12), decision_count=0, question_count=0, video_id="yK-6oDfAGH8",
        video_url="https://www.youtube.com/watch?v=yK-6oDfAGH8",
        evidence="Do we do <mark>rental</mark> property and <mark>Airbnb</mark> type thing?",
        evidence_label="Should short term rentals be restricted or taxed?",
        evidence_start_seconds=2932.4,
    )
    base.update(kw)
    return base


def test_recent_mixes_unanalyzed_meetings_honestly(get) -> None:
    conn = _Conn(rows=[_unanalyzed(), _analyzed()], total=2)
    r = get(conn, {"sort": "recent", "state": "GA", "limit": 6})
    assert r.status_code == 200
    body = r.json()
    assert body["pagination"] == {"total": 2, "limit": 6, "offset": 0}
    new, old = body["items"]

    assert new["analyzed"] is False
    assert new["meeting_id"] is None
    assert new["decision_count"] == 0 and new["question_count"] == 0
    assert new["has_decisions"] is False
    assert new["date"] == "2026-11-12"
    assert new["video_url"] == "https://www.youtube.com/watch?v=yK-6oDfAGH8"
    assert "<mark>rental</mark>" in new["evidence"]
    assert new["evidence_label"] == "Should short term rentals be restricted or taxed?"
    assert new["jump_url"] == "https://www.youtube.com/watch?v=yK-6oDfAGH8&t=2932s"

    assert old["analyzed"] is True
    assert old["meeting_id"] == 4021
    assert old["decision_count"] == 3
    assert old["evidence"] is None and old["jump_url"] is None

    count_sql, count_params = conn.calls[0]
    list_sql, list_params = conn.calls[1]
    for sql in (count_sql, list_sql):
        assert "recent_transcribed_meeting" in sql
        assert "UNION ALL" in sql
        # same scope on both legs, future dates out, no duplicate of an analyzed video
        assert "mb.state_code = $1" in sql and "r.state_code = $1" in sql
        assert "r.meeting_date <= current_date" in sql
        assert "mb2.video_id = r.video_id" in sql
        # never transcript text at request time (#496)
        assert "event_documents" not in sql and "content" not in sql
    assert count_params == ("GA",)
    assert list_params == ("GA", 6, 0)
    assert "ORDER BY cards.meeting_date DESC NULLS LAST" in list_sql


def test_untimed_evidence_has_no_jump(get) -> None:
    conn = _Conn(rows=[_unanalyzed(evidence_start_seconds=None)], total=1)
    item = get(conn, {"sort": "recent"}).json()["items"][0]
    assert item["evidence"] and item["jump_url"] is None


def test_no_evidence_means_no_label(get) -> None:
    conn = _Conn(rows=[_unanalyzed(evidence=None, evidence_label="stale", evidence_start_seconds=None)], total=1)
    item = get(conn, {"sort": "recent"}).json()["items"][0]
    assert item["evidence"] is None and item["evidence_label"] is None and item["jump_url"] is None


def test_city_and_q_filter_both_legs(get) -> None:
    conn = _Conn(rows=[], total=0)
    r = get(conn, {"sort": "recent", "city": "Tuscaloosa", "q": "council"})
    assert r.status_code == 200
    sql, params = conn.calls[1]
    assert "(r.city ILIKE $1 OR r.jurisdiction_name ILIKE $1)" in sql
    assert "(r.meeting_title ILIKE $2 OR r.jurisdiction_name ILIKE $2)" in sql
    assert params == ("%Tuscaloosa%", "%council%", 24, 0)


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "recent", "topic_id": 100000},
        {"sort": "recent", "theme": "housing"},
        {"sort": "recent", "question_id": "q1"},
        {"sort": "interesting"},
        {"sort": "decisions"},
    ],
)
def test_content_filters_and_other_sorts_stay_analyzed_only(get, params) -> None:
    conn = _Conn(rows=[_analyzed()], total=1)
    r = get(conn, params)
    assert r.status_code == 200
    assert all("recent_transcribed_meeting" not in sql for sql, _ in conn.calls)
    assert r.json()["items"][0]["analyzed"] is True


def test_recent_analyzed_only_path_drops_future_dates(get) -> None:
    conn = _Conn(rows=[_analyzed()], total=1)
    get(conn, {"sort": "recent", "topic_id": 100000})
    assert all("<= current_date" in sql for sql, _ in conn.calls)


def test_missing_serving_table_falls_back_to_analyzed(get) -> None:
    conn = _Conn(
        rows=[_analyzed()], total=1,
        union_error=asyncpg.exceptions.UndefinedTableError('relation "recent_transcribed_meeting" does not exist'),
    )
    r = get(conn, {"sort": "recent"})
    assert r.status_code == 200
    assert r.json()["items"][0]["analyzed"] is True
    assert "FROM meeting_browse mb" in conn.calls[-1][0]
    assert "recent_transcribed_meeting" not in conn.calls[-1][0]
