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
    def __init__(
        self, totals=None, quotes=None, by_state=None, error: Exception | None = None,
        lean=None, lean_error: Exception | None = None, lean_totals=None,
    ):
        self.lean_totals = lean_totals or []
        self.lean = lean or []
        self.lean_error = lean_error
        self.totals = totals or []
        self.quotes = quotes or []
        self.by_state = by_state or []
        self.error = error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        if "data_center_meeting_lean" in sql:
            if self.lean_error:
                raise self.lean_error
            return self.lean_totals if "AS stopped_meetings" in sql else self.lean
        if "GROUP BY p.state_code" in sql:
            return self.by_state
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


def test_every_match_basis_the_rule_emits_is_served(get) -> None:
    # #932 added data_center_item and same_item to int_data_center__public_comment; a quote with
    # either must serialize instead of failing validation (a 500 for the whole scope).
    conn = _Conn(totals=[_totals()], quotes=[
        _quote("against", public_comment_id="c1", match_basis="same_item",
               decision_headline="Phoenix Mart PAD major amendment tabled"),
        _quote("for", public_comment_id="c2", match_basis="data_center_item",
               decision_headline="Approve Data Center Ordinance"),
        _quote("question", public_comment_id="c3", match_basis="own_words", decision_headline=None),
    ])
    resp = get(conn)
    assert resp.status_code == 200, resp.text
    quotes = resp.json()["quotes"]
    assert quotes["against"][0]["match_basis"] == "same_item"
    assert quotes["against"][0]["decision_headline"] == "Phoenix Mart PAD major amendment tabled"
    assert quotes["for"][0]["match_basis"] == "data_center_item"
    assert quotes["question"][0]["match_basis"] == "own_words"


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
    assert body["by_state"] == []


def test_limit_is_bounded(get) -> None:
    assert get(_Conn(), {"limit": 0}).status_code == 422
    assert get(_Conn(), {"limit": 11}).status_code == 422


def test_other_errors_are_500(get) -> None:
    assert get(_Conn(error=RuntimeError("boom"))).status_code == 500


def _state(code: str, **kw) -> dict[str, Any]:
    base = dict(state_code=code, speakers_for=0, speakers_against=0, speakers_question=0, speakers_neutral=0, meetings=1)
    base.update(kw)
    return base


def test_by_state_is_national_even_on_a_scoped_page(get) -> None:
    # #1087: the home map needs every state's split, so the per-state query never takes the scope.
    rows = [_state("AZ", speakers_against=11, speakers_question=1, meetings=3), _state("TX", speakers_for=2, meetings=2)]
    conn = _Conn(totals=[_totals()], by_state=rows)
    resp = get(conn, {"state": "AL", "city": "Testville"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["by_state"] == [{**r, "public_against_meetings": 0, "disagreement_meetings": 0} for r in rows]
    (sql, params) = next(c for c in conn.calls if "GROUP BY p.state_code" in c[0])
    assert params == ()
    assert "$1" not in sql and "ILIKE" not in sql
    assert "FROM data_center_meeting_position" in sql and "p.state_code IS NOT NULL" in sql


def test_by_state_defaults_to_empty(get) -> None:
    assert get(_Conn(totals=[_totals()])).json()["by_state"] == []


def test_by_state_carries_jev_lean_counts_nationally(get) -> None:
    """#1117: public-against and disagreement meetings per state, never narrowed by the scope. A state with lean
    counts but no speaker row still gets a row (0 speakers) so the map can tint it."""
    rows = [_state("AZ", speakers_against=11, meetings=3)]
    lean = [
        {"state_code": "AZ", "public_against_meetings": 2, "disagreement_meetings": 0},
        {"state_code": "GA", "public_against_meetings": 9, "disagreement_meetings": 2},
    ]
    conn = _Conn(totals=[_totals()], by_state=rows, lean=lean)
    body = get(conn, {"state": "AL", "city": "Testville"}).json()
    by = {s["state_code"]: s for s in body["by_state"]}
    assert [s["state_code"] for s in body["by_state"]] == ["AZ", "GA"]
    assert by["AZ"]["speakers_against"] == 11 and by["AZ"]["public_against_meetings"] == 2
    assert by["GA"] == {**_state("GA", meetings=0), "public_against_meetings": 9, "disagreement_meetings": 2}
    (sql, params) = next(c for c in conn.calls if "GROUP BY l.state_code" in c[0])
    assert params == () and "$1" not in sql
    assert "mostly_supported" not in sql and "mixed" not in sql


def test_by_state_lean_missing_table_is_zero_not_a_failure(get) -> None:
    err = asyncpg.exceptions.UndefinedTableError("relation \"data_center_meeting_lean\" does not exist")
    rows = [_state("AZ", speakers_against=1)]
    resp = get(_Conn(totals=[_totals()], by_state=rows, lean_error=err))
    assert resp.status_code == 200, resp.text
    assert resp.json()["available"] is True
    assert resp.json()["by_state"] == [{**rows[0], "public_against_meetings": 0, "disagreement_meetings": 0}]


def _lean_totals(**kw) -> dict[str, Any]:
    base = dict(
        public_against_meetings=12, public_against_states=5, stopped_meetings=4,
        disagreement_meetings=3, disagreement_states=2,
        public_for_meetings=2, public_mixed_meetings=1, public_spoke_meetings=15,
    )
    base.update(kw)
    return base


def test_lean_totals_are_national_even_on_a_scoped_page(get) -> None:
    """#1122: the home hero's AI-reading totals never take the scope."""
    conn = _Conn(totals=[_totals()], lean_totals=[_lean_totals()])
    resp = get(conn, {"state": "AL", "city": "Testville"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["lean_totals"] == _lean_totals()
    (sql, params) = next(c for c in conn.calls if "AS stopped_meetings" in c[0])
    assert params == () and "$1" not in sql and "ILIKE" not in sql
    assert "'tabled_or_deferred', 'denied', 'moratorium'" in sql
    assert "l.public_against" in sql and "l.officials_sided_against_public" in sql


def test_lean_totals_null_when_table_missing(get) -> None:
    err = asyncpg.exceptions.UndefinedTableError("relation \"data_center_meeting_lean\" does not exist")
    resp = get(_Conn(totals=[_totals()], lean_error=err))
    assert resp.status_code == 200, resp.text
    assert resp.json()["available"] is True
    assert resp.json()["lean_totals"] is None


def test_lean_totals_null_values_become_zero(get) -> None:
    row = _lean_totals(stopped_meetings=None)
    body = get(_Conn(totals=[_totals()], lean_totals=[row])).json()
    assert body["lean_totals"]["stopped_meetings"] == 0


def test_lean_totals_other_leans_use_the_confident_threshold() -> None:
    """#1134: for, mixed and spoke counts take the same P >= 0.7 as public_against, and spoke leaves out no-comment."""
    from api.routes.data_centers import LEAN_TOTALS_SQL

    sql = LEAN_TOTALS_SQL
    for col in ("public_for_meetings", "public_mixed_meetings", "public_spoke_meetings"):
        assert f"AS {col}" in sql
    assert "l.public_lean = 'mostly_supported' AND coalesce(l.public_lean_p, 0) >= 0.7" in sql
    assert "l.public_lean = 'mixed' AND coalesce(l.public_lean_p, 0) >= 0.7" in sql
    assert "l.public_lean IN ('mostly_opposed', 'mostly_supported', 'mixed') AND coalesce(l.public_lean_p, 0) >= 0.7" in sql
    assert "no_public_comment_on_data_center" not in sql


def test_lean_totals_serve_the_other_leans(get) -> None:
    body = get(_Conn(totals=[_totals()], lean_totals=[_lean_totals(public_mixed_meetings=None)])).json()
    assert body["lean_totals"]["public_for_meetings"] == 2
    assert body["lean_totals"]["public_mixed_meetings"] == 0
    assert body["lean_totals"]["public_spoke_meetings"] == 15


def test_scope_lean_totals_take_the_state_and_city(get) -> None:
    """#1134: the scoped AI-reading totals narrow by state and city the way the speaker totals do."""
    conn = _Conn(totals=[_totals()], lean_totals=[_lean_totals()])
    resp = get(conn, {"state": "AL", "city": "Tuscaloosa"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["scope_lean_totals"] == _lean_totals()
    calls = [c for c in conn.calls if "AS stopped_meetings" in c[0]]
    assert len(calls) == 2
    sql, params = calls[1]
    assert params == ("AL", "%Tuscaloosa%")
    assert "l.state_code = $1" in sql and "l.jurisdiction_name ILIKE $2" in sql


def test_scope_lean_totals_nationally_reuse_the_national_query(get) -> None:
    conn = _Conn(totals=[_totals()], lean_totals=[_lean_totals()])
    body = get(conn).json()
    assert body["scope_lean_totals"] == body["lean_totals"] == _lean_totals()
    assert len([c for c in conn.calls if "AS stopped_meetings" in c[0]]) == 1


def test_scope_lean_totals_null_when_table_missing(get) -> None:
    err = asyncpg.exceptions.UndefinedTableError("relation \"data_center_meeting_lean\" does not exist")
    body = get(_Conn(totals=[_totals()], lean_error=err), {"state": "AL"}).json()
    assert body["available"] is True and body["scope_lean_totals"] is None


def test_named_speakers_come_first_and_per_state_ranks_within_each_state() -> None:
    # Owner, 2026-11-26: the home map should say who spoke ("Rob D.") wherever the record has a name.
    scope = data_centers.build_scope(None, None, None)
    _, _, side_sql, side_params = data_centers.build_position_queries(scope, 10)
    assert "PARTITION BY p.stance_bucket ORDER BY ((to_jsonb(p) ->> 'speaker_display_name') IS NULL)" in side_sql
    assert side_params == [10]
    _, _, state_sql, state_params = data_centers.build_position_queries(scope, 10, per_state=3)
    assert "PARTITION BY p.state_code, p.stance_bucket ORDER BY" in state_sql
    assert state_params == [3]


def test_per_state_is_bounded(get) -> None:
    conn = _Conn(totals=[_totals()])
    assert get(conn, {"per_state": data_centers.POSITION_QUOTES_PER_STATE_MAX + 1}).status_code == 422
