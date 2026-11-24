"""GET /api/data-centers/positions (#930): who spoke for and against, and the recorded votes.

The DB layer is mocked: ``get_db_pool`` returns a fake pool that records SQL and params and
returns canned rows (totals for the totals query, quotes otherwise). The rows are test
stand-ins; the rule for which comments and votes count lives in dbt.
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

PATH = "/api/data-centers/positions"


class _Conn:
    def __init__(self, totals=None, quotes=None, error: Exception | None = None):
        self.totals = totals or []
        self.quotes = quotes or []
        self.error = error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        return self.totals if "FROM data_center_meeting_position" in sql else self.quotes


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


def _totals(**kw) -> dict[str, Any]:
    base = dict(
        meetings_reviewed=4, meetings=3, speakers_for=1, speakers_against=4, speakers_question=1,
        speakers_neutral=1, decisions_with_tally=2, votes_for=9, votes_against=3,
    )
    base.update(kw)
    return base


def _quote(side: str, **kw) -> dict[str, Any]:
    base = dict(
        public_comment_id=f"c-{side}", stance_bucket=side, quote="It will drain our wells.",
        speaker_role="Resident", jurisdiction_name="Testville", state_code="AL",
        meeting_date=date(2026, 3, 2), video_url="https://www.youtube.com/watch?v=vidA",
        start_seconds=200.0, decision_headline="Rezoning for a data center campus",
        match_basis="data_center_decision", side_rank=1,
    )
    base.update(kw)
    return base


def test_city_scope_totals_quotes_and_bound_params(get) -> None:
    conn = _Conn(totals=[_totals()], quotes=[_quote("against"), _quote("for"), _quote("question")])
    resp = get(conn, {"state": "Alabama", "city": "Testville"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scope"] == {
        "level": "city", "state_code": "AL", "state": "Alabama", "city": "Testville", "jurisdiction_id": None,
    }
    assert body["available"] is True
    assert body["totals"] == {
        "meetings": 3, "meetings_reviewed": 4, "speakers_for": 1, "speakers_against": 4,
        "speakers_question": 1, "speakers_neutral": 1, "decisions_with_tally": 2,
        "votes_for": 9, "votes_against": 3,
    }
    assert set(body["quotes"]) == {"for", "against", "question"}
    (q,) = body["quotes"]["against"]
    assert set(q) >= {
        "public_comment_id", "quote", "speaker_role", "jurisdiction_name", "state_code",
        "meeting_date", "video_url", "start_seconds",
    }
    assert q["jump_url"] == "https://www.youtube.com/watch?v=vidA&t=200s"
    assert "stance_bucket" not in q and "side_rank" not in q
    totals_sql, params = conn.calls[0]
    assert "p.state_code = $1" in totals_sql and "p.jurisdiction_name ILIKE $2" in totals_sql
    assert params == ("AL", "%Testville%")
    quotes_sql, quote_params = conn.calls[1]
    assert quote_params == ("AL", "%Testville%", 3) and "q.side_rank <= $3" in quotes_sql


def test_votes_are_null_not_zero_when_no_tally_is_recorded(get) -> None:
    conn = _Conn(totals=[_totals(decisions_with_tally=0, votes_for=None, votes_against=None)])
    totals = get(conn).json()["totals"]
    assert totals["decisions_with_tally"] == 0
    assert totals["votes_for"] is None and totals["votes_against"] is None
    # even if a row carried a stray 0, no tally means no vote figure
    conn = _Conn(totals=[_totals(decisions_with_tally=0, votes_for=0, votes_against=0)])
    totals = get(conn).json()["totals"]
    assert totals["votes_for"] is None and totals["votes_against"] is None


def test_quotes_only_counted_speakers_with_their_own_words() -> None:
    scope = data_centers.build_scope(None, None, None)
    totals_sql, params, quotes_sql, quote_params = data_centers.build_position_queries(scope, 2)
    assert "WHERE TRUE" in totals_sql and params == [] and quote_params == [2]
    assert "p.is_counted" in quotes_sql and "p.quote IS NOT NULL" in quotes_sql
    assert "p.stance_bucket IN ('for', 'against', 'question')" in quotes_sql
    # the route reads the two marts only; the rule itself is in dbt
    assert "public_comment p" in quotes_sql and "FROM data_center_public_comment" in quotes_sql
    assert "vote_tally" not in totals_sql + quotes_sql and "~*" not in totals_sql + quotes_sql


def test_untimed_quote_has_no_jump(get) -> None:
    conn = _Conn(totals=[_totals()], quotes=[_quote("for", start_seconds=None)])
    (q,) = get(conn).json()["quotes"]["for"]
    assert q["start_seconds"] is None and q["jump_url"] is None


def test_missing_mart_is_unavailable_not_zero(get) -> None:
    resp = get(_Conn(error=asyncpg.exceptions.UndefinedTableError("no relation")), {"state": "AL"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False and body["scope"]["state_code"] == "AL"
    assert all(v is None for v in body["totals"].values())
    assert body["quotes"] == {"for": [], "against": [], "question": []}


def test_limit_is_bounded(get) -> None:
    assert get(_Conn(), {"limit": 0}).status_code == 422
    assert get(_Conn(), {"limit": 11}).status_code == 422


def test_other_errors_are_500(get) -> None:
    assert get(_Conn(error=RuntimeError("boom"))).status_code == 500
