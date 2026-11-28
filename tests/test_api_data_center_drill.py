"""The lists behind the story's "Who spoke up" numbers (#1288): speakers, vote decisions, caption comments."""

from __future__ import annotations

import asyncio
import re
from datetime import date
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import data_center_comments as dcc
from api.routes import data_center_drill as drill
from api.routes import data_centers as dc


class _Conn:
    """Answers the count query with ``count`` and the page query with ``rows``; checks every $n has a param."""

    def __init__(self, count: dict[str, Any] | None = None, rows: list[dict[str, Any]] | None = None, error=None):
        self.count, self.rows, self.error = count or {"n": 0}, rows or [], error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        assert len(set(re.findall(r"\$(\d+)", sql))) == len(params), sql
        return [self.count] if "LIMIT" not in sql else self.rows


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
    def _get(conn: _Conn, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        async def pool():
            return _Pool(conn)

        monkeypatch.setattr(drill, "get_db_pool", pool)
        app = FastAPI()
        app.include_router(drill.router, prefix="/api")

        async def go():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
                return await client.get(path, params=params or {})

        return asyncio.run(go())

    return _get


# --- the lists use the tiles' own filters ---------------------------------------------------------------------------


def test_speaker_list_scopes_on_the_position_row_like_the_tile() -> None:
    """The tile is sum(speakers_<side>) over data_center_meeting_position filtered on p.state_code / p.jurisdiction_name;
    the list must count the counted comment rows of the same meetings, with the same filter."""
    scope = drill.applied_scope("Alabama", "Tuscaloosa")
    count_sql, params, page_sql, page_params = drill.build_speaker_queries(scope, "against", 25, 50)
    totals_sql, tparams, _, _ = dc.build_position_queries(scope, 5)
    for clause in ("p.state_code = $", "p.jurisdiction_name ILIKE $"):
        assert clause in count_sql and clause in totals_sql
    assert "c.is_counted AND c.stance_bucket = $1" in count_sql
    assert "JOIN data_center_meeting_position p" in count_sql
    assert params == ["against", *tparams]
    assert page_params[-2:] == [25, 50] and "OFFSET" in page_sql


def test_vote_list_counts_only_recorded_tallies_on_the_side() -> None:
    scope = drill.applied_scope("GA", None)
    totals_sql, params, _page_sql, page_params = drill.build_vote_queries(scope, "against", 10, 0)
    assert "d.votes_for IS NOT NULL AND d.votes_against IS NOT NULL AND d.votes_against > 0" in totals_sql
    assert "sum(d.votes_against)" in totals_sql
    assert "p.state_code = $1" in totals_sql and params == ["GA"]
    assert page_params == ["GA", 10, 0]


def test_comment_list_uses_comment_metrics_filter() -> None:
    scope = dc.build_scope("IL", "Joliet", None)
    count_sql, params, _, _ = drill.build_comment_queries(scope, 2026, False, None, 25, 0)
    metrics_where, metrics_params = dcc._where(scope, 2026)
    assert count_sql == f"SELECT count(DISTINCT meeting_speaker_id)::int AS n FROM data_center_comment{metrics_where}"
    assert params == metrics_params
    ai_sql, _, _, _ = drill.build_comment_queries(scope, 2026, True, None, 25, 0)
    assert ai_sql.endswith("AND mentions_ai")
    co_sql, co_params, _, _ = drill.build_comment_queries(dc.build_scope(None, None, None), None, False, "google", 5, 0)
    assert "WHERE $1 = ANY(company_keys)" in co_sql and co_params == ["google"]


def test_mark_terms_marks_data_center_words_only() -> None:
    assert drill.mark_terms("No more Data Centers here, <mark>ok</mark>") == "No more <mark>Data Centers</mark> here, ok"
    assert drill.mark_terms("a hyperscale campus") == "a <mark>hyperscale</mark> campus"
    assert drill.mark_terms("the project") == "the project"
    assert drill.mark_terms(None) is None


# --- endpoints --------------------------------------------------------------------------------------------------------


def test_speakers_endpoint(get) -> None:
    row = {
        "public_comment_id": "c1", "quote": "Deny this data center.", "speaker_display_name": "Audra T.",
        "speaker_role": "resident", "match_basis": "data_center_decision", "decision_headline": "Rezoning",
        "event_decision_id": "d1", "jurisdiction_name": "Casa Grande", "state_code": "AZ",
        "meeting_date": date(2026, 11, 12), "video_url": "https://www.youtube.com/watch?v=abc", "start_seconds": 61.5,
    }
    conn = _Conn({"n": 11}, [row])
    r = get(conn, "/api/data-centers/speakers", {"side": "against", "state": "AZ", "limit": 1})
    assert r.status_code == 200
    b = r.json()
    assert b["total"] == 11 and b["side"] == "against" and b["scope"]["state_code"] == "AZ"
    it = b["items"][0]
    assert it["quote"] == "Deny this data center."
    assert it["quote_highlighted"] == "Deny this <mark>data center</mark>."
    assert it["jump_url"] == "https://www.youtube.com/watch?v=abc&t=61s"
    assert it["speaker_display_name"] == "Audra T."


def test_speakers_side_is_validated(get) -> None:
    assert get(_Conn(), "/api/data-centers/speakers", {"side": "neutral"}).status_code == 422
    assert get(_Conn(), "/api/data-centers/speakers", {"side": "for", "limit": 101}).status_code == 422


def test_vote_decisions_endpoint(get) -> None:
    row = {
        "data_center_decision_id": "1db5", "headline": "Data Center Zoning Ordinance Delayed", "outcome": "Delayed",
        "votes_for": 8, "votes_against": 1, "meeting_date": date(2026, 4, 28), "jurisdiction_name": "Birmingham",
        "state_code": "AL", "video_url": None, "decision_url": "/decisions/1db5",
    }
    conn = _Conn({"decisions": 1, "votes": 8}, [row])
    b = get(conn, "/api/data-centers/vote-decisions", {"side": "for", "state": "AL"}).json()
    assert (b["total_decisions"], b["total_votes"]) == (1, 8)
    assert b["items"][0]["decision_url"] == "/decisions/1db5"


def test_comments_endpoint_withholds_possible_minors(get) -> None:
    rows = [
        {"data_center_comment_id": "a", "speaker_display_name": "Rob D.", "possible_minor": False,
         "jurisdiction_name": "Huntsville", "state_code": "AL", "meeting_date": date(2026, 3, 1),
         "start_seconds": 125.0, "video_id": "vid1", "concern_keys": ["water_use"], "company_keys": [],
         "mentions_ai": True},
        {"data_center_comment_id": "b", "speaker_display_name": None, "possible_minor": True,
         "jurisdiction_name": "Huntsville", "state_code": "AL", "meeting_date": date(2026, 3, 1),
         "start_seconds": 300.0, "video_id": "vid1", "concern_keys": ["water_use"], "company_keys": ["google"],
         "mentions_ai": False},
    ]
    b = get(_Conn({"n": 60}, rows), "/api/data-centers/comments", {"state": "AL"}).json()
    assert b["total"] == 60 and b["year"] == "2026" and b["filter"] == "all"
    assert "privacy" in b["note"]
    first, minor = b["items"]
    assert first["jump_url"] == "https://www.youtube.com/watch?v=vid1&t=125s"
    assert first["speaker_display_name"] == "Rob D."
    assert minor["possible_minor"] is True and minor["jump_url"] is None
    assert minor["concern_keys"] == [] and minor["company_keys"] == [] and minor["start_seconds"] is None
    assert "minor" in minor["withheld_reason"]


def test_missing_mart_is_unavailable_not_zero(get) -> None:
    err = asyncpg.exceptions.UndefinedTableError("nope")
    for path, params in [
        ("/api/data-centers/speakers", {"side": "for"}),
        ("/api/data-centers/vote-decisions", {"side": "for"}),
        ("/api/data-centers/comments", {}),
    ]:
        b = get(_Conn(error=err), path, params).json()
        assert b["available"] is False and b["items"] == []
        assert b.get("total", b.get("total_votes")) is None


# --- #1330: officials sided against the public ----------------------------------------------------------------------


def test_disagreement_meetings_total_is_the_flag_count_and_rows_link_the_recording(get) -> None:
    row = {"video_id": "abc", "jurisdiction_name": "Coweta County", "state_code": "GA", "meeting_date": "2026-05-01",
           "public_lean": "mostly_opposed", "official_lean": "mostly_supportive", "outcome": "approved",
           "video_url": "https://www.youtube.com/watch?v=abc"}
    conn = _Conn(count={"n": 11}, rows=[row])
    b = get(conn, "/api/data-centers/disagreement-meetings", {"state": "GA"}).json()
    assert b["total"] == 11 and b["items"][0]["video_url"].endswith("abc")
    assert b["scope"]["state_code"] == "GA"
    # The same flag caption-facts counts as disagreement_meetings, in the same scope.
    assert all("officials_sided_against_public" in sql for sql, _ in conn.calls)
    assert conn.calls[0][1] == ("GA",)


def test_disagreement_meetings_city_scope_and_missing_mart(get) -> None:
    conn = _Conn(count={"n": 0})
    get(conn, "/api/data-centers/disagreement-meetings", {"state": "AL", "city": "Tuscaloosa"})
    assert conn.calls[0][1] == ("AL", "%Tuscaloosa%")
    b = get(_Conn(error=asyncpg.exceptions.UndefinedTableError("nope")), "/api/data-centers/disagreement-meetings", {}).json()
    assert b["available"] is False and b["total"] is None
