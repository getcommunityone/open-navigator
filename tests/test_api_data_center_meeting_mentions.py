"""GET /api/data-centers/meeting-mentions (#445): data centers discussed in meeting transcripts.

The DB layer is mocked: ``get_db_pool`` returns a fake pool that records SQL and
params and returns canned rows (counts for the count query, items otherwise).
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

PATH = "/api/data-centers/meeting-mentions"


class _Conn:
    def __init__(
        self, rows=None, counts=None, error: Exception | None = None, by_state=None, by_place=None,
        lean=None, lean_error: Exception | None = None,
        meetings=None, speakers=None, extras_error: Exception | None = None,
    ):
        self.meetings = meetings or []
        self.speakers = speakers or []
        self.extras_error = extras_error
        self.lean = lean or []
        self.lean_error = lean_error
        self.rows = rows or []
        self.by_place = by_place or []
        self.counts = counts or []
        self.by_state = by_state or []
        self.error = error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        if "FROM event_meeting e" in sql or "JOIN data_center_public_comment c" in sql:
            if self.extras_error:
                raise self.extras_error
            return self.meetings if "FROM event_meeting e" in sql else self.speakers
        if "data_center_meeting_lean" in sql:
            if self.lean_error:
                raise self.lean_error
            return self.lean
        if "GROUP BY m.state_code" in sql:
            return self.by_state
        if "GROUP BY m.jurisdiction_id" in sql:
            return self.by_place
        return self.counts if "AS passages" in sql and "LIMIT" not in sql else self.rows


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


def _item(**kw) -> dict[str, Any]:
    base = dict(
        data_center_meeting_mention_id="m1", video_id="7VghnjHd_1w",
        video_url="https://www.youtube.com/watch?v=7VghnjHd_1w", meeting_title="City Council Business Meeting",
        meeting_date=date(2026, 5, 26), jurisdiction_id="charlotte_3712000", jurisdiction_name="Charlotte",
        state_code="NC", state="North Carolina", passage_index=42, start_seconds=7747.466,
        evidence="we encourage you to adopt a temporary moratorium to pause <mark>data</mark> <mark>center</mark> development",
        match_terms=["data center"], match_strength="data_center", data_center_site_id=None, site_name=None,
        site_match_basis=None,
    )
    base.update(kw)
    return base


def test_city_scope_counts_evidence_and_jump(get) -> None:
    conn = _Conn(rows=[_item()], counts=[{"passages": 30, "meetings": 1, "site_specific": 0}])
    resp = get(conn, {"state": "North Carolina", "city": "Charlotte"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scope"] == {
        "level": "city", "state_code": "NC", "state": "North Carolina", "city": "Charlotte", "jurisdiction_id": None,
    }
    assert body["counts"] == {"passages": 30, "meetings": 1, "site_specific": 0, "by_state": [], "by_place": []}
    (item,) = body["items"]
    assert "<mark>data</mark>" in item["evidence"]
    assert item["jump_url"] == "https://www.youtube.com/watch?v=7VghnjHd_1w&t=7747s"
    items_sql, params = conn.calls[0]
    assert "m.state_code = $1" in items_sql and "m.jurisdiction_name ILIKE $2" in items_sql
    assert params == ("NC", "%Charlotte%", 100)
    counts_sql, counts_params = conn.calls[1]
    assert counts_params == ("NC", "%Charlotte%") and "LIMIT" not in counts_sql


def test_untimed_passage_has_no_jump(get) -> None:
    conn = _Conn(rows=[_item(start_seconds=None)], counts=[{"passages": 1, "meetings": 1, "site_specific": 0}])
    (item,) = get(conn).json()["items"]
    assert item["start_seconds"] is None and item["jump_url"] is None


def test_national_scope_binds_only_limit() -> None:
    scope = data_centers.build_scope(None, None, None)
    sql, params, counts_sql, counts_params = data_centers.build_mention_queries(scope, None, None, 7)
    assert "WHERE TRUE" in sql and params == [7] and counts_params == []
    assert sql.index("m.meeting_date DESC NULLS LAST") < sql.index("LIMIT $1")


def test_site_and_strength_filters_are_bound() -> None:
    scope = data_centers.build_scope("TX", None, None)
    sql, params, counts_sql, counts_params = data_centers.build_mention_queries(scope, "abc", "site_specific", 5)
    assert "m.data_center_site_id = $2" in sql and "m.match_strength = $3" in sql
    assert params == ["TX", "abc", "site_specific", 5] and counts_params == ["TX", "abc", "site_specific"]


def test_bad_strength_is_422(get) -> None:
    assert get(_Conn(), {"strength": "maybe"}).status_code == 422


def test_missing_mart_is_an_empty_list(get) -> None:
    resp = get(_Conn(error=asyncpg.exceptions.UndefinedTableError("no relation")))
    assert resp.status_code == 200 and resp.json()["items"] == [] and resp.json()["counts"]["passages"] == 0


def test_other_errors_are_500(get) -> None:
    assert get(_Conn(error=RuntimeError("boom"))).status_code == 500


def test_counts_by_state_are_real_distinct_meetings_in_scope(get) -> None:
    """#970: the Overview dot map shades each state by its own national count."""
    conn = _Conn(
        counts=[{"passages": 9, "meetings": 5, "site_specific": 1}],
        by_state=[
            {"state_code": "TX", "state": "Texas", "meetings": 3},
            {"state_code": "NC", "state": "North Carolina", "meetings": 2},
        ],
    )
    body = get(conn).json()
    assert body["counts"]["by_state"] == [
        {"state_code": "TX", "state": "Texas", "meetings": 3},
        {"state_code": "NC", "state": "North Carolina", "meetings": 2},
    ]
    sql, params = next(c for c in conn.calls if "GROUP BY m.state_code" in c[0])
    assert "count(DISTINCT m.video_id)" in sql and "m.state_code IS NOT NULL" in sql and params == ()

    # A state or city scope never narrows the per-state counts: the map is national and only highlights the scope,
    # so Texas is never shown as having no meetings just because the story is scoped to North Carolina.
    conn = _Conn(counts=[{"passages": 1, "meetings": 1, "site_specific": 0}])
    get(conn, {"state": "NC", "city": "Charlotte"})
    sql, params = next(c for c in conn.calls if "GROUP BY m.state_code" in c[0])
    assert "m.state_code = $" not in sql and "ILIKE" not in sql and params == ()
    items_sql, items_params = conn.calls[0]
    assert "m.state_code = $1" in items_sql and items_params[:2] == ("NC", "%Charlotte%")

    conn = _Conn(counts=[{"passages": 1, "meetings": 1, "site_specific": 1}])
    get(conn, {"strength": "site_specific"})
    sql, params = next(c for c in conn.calls if "GROUP BY m.state_code" in c[0])
    assert "m.match_strength = $1" in sql and params == ("site_specific",)


def test_by_state_is_empty_not_missing_when_none(get) -> None:
    body = get(_Conn(counts=[{"passages": 0, "meetings": 0, "site_specific": 0}])).json()
    assert body["counts"]["by_state"] == []


def test_by_place_only_at_state_scope_and_not_narrowed_by_city(get) -> None:
    """#1039: the state's county map gets meetings per government in the state, never narrowed to the city."""
    place = {
        "jurisdiction_id": "columbia_13073", "jurisdiction_name": "Columbia County", "jurisdiction_type": "county",
        "geoid": "13073", "latitude": 33.55, "longitude": -82.25, "meetings": 18,
    }
    conn = _Conn(by_place=[place])
    body = get(conn, {"state": "GA", "city": "Columbus"}).json()
    no_speakers = {
        "speakers_for": 0, "speakers_against": 0, "speakers_question": 0, "speakers_neutral": 0,
        "public_against_meetings": 0, "disagreement_meetings": 0,
    }
    assert body["counts"]["by_place"] == [{**place, **no_speakers}]
    sql, params = next(c for c in conn.calls if "GROUP BY m.jurisdiction_id" in c[0])
    assert params == ("GA",)
    assert "ILIKE" not in sql

    conn = _Conn(by_place=[place])
    body = get(conn).json()
    assert body["counts"]["by_place"] == []
    assert not any("GROUP BY m.jurisdiction_id" in c[0] for c in conn.calls)


def test_by_place_carries_real_speaker_sums_per_government(get) -> None:
    """#1106: each government gets the speaker sums from data_center_meeting_position for its meetings."""
    place = {
        "jurisdiction_id": "chandler_0412000", "jurisdiction_name": "Chandler", "jurisdiction_type": "city",
        "geoid": "0412000", "latitude": 33.3, "longitude": -111.84, "meetings": 4,
        "speakers_for": 3, "speakers_against": 7, "speakers_question": 1, "speakers_neutral": 2,
    }
    conn = _Conn(by_place=[place])
    body = get(conn, {"state": "AZ"}).json()
    assert body["counts"]["by_place"] == [{**place, "public_against_meetings": 0, "disagreement_meetings": 0}]
    sql, params = next(c for c in conn.calls if "GROUP BY m.jurisdiction_id" in c[0])
    assert params == ("AZ",)
    assert "data_center_meeting_position" in sql
    # Positions are summed per meeting first, then joined to the distinct (government, meeting) set,
    # so a meeting with many passages can't multiply its speakers.
    assert "GROUP BY p.video_id" in sql
    assert "SELECT DISTINCT m.jurisdiction_id, m.video_id" in sql
    assert "LEFT JOIN sp ON sp.jurisdiction_id = m.jurisdiction_id" in sql


_PLACES = [
    {"jurisdiction_id": "a_1", "jurisdiction_name": "A County", "jurisdiction_type": "county", "geoid": "13001",
     "latitude": None, "longitude": None, "meetings": 5},
    {"jurisdiction_id": "b_2", "jurisdiction_name": "B", "jurisdiction_type": "city", "geoid": "1300002",
     "latitude": None, "longitude": None, "meetings": 2},
]


def test_by_place_carries_jev_lean_counts(get) -> None:
    """#1117: public-against and disagreement meetings per government, over the same filtered meeting set."""
    lean = [{"jurisdiction_id": "a_1", "public_against_meetings": 3, "disagreement_meetings": 1}]
    conn = _Conn(by_place=_PLACES, lean=lean)
    body = get(conn, {"state": "GA", "city": "B"}).json()
    by_id = {p["jurisdiction_id"]: p for p in body["counts"]["by_place"]}
    assert (by_id["a_1"]["public_against_meetings"], by_id["a_1"]["disagreement_meetings"]) == (3, 1)
    assert (by_id["b_2"]["public_against_meetings"], by_id["b_2"]["disagreement_meetings"]) == (0, 0)
    sql, params = next(c for c in conn.calls if "data_center_meeting_lean" in c[0])
    assert params == ("GA",)  # the state only: never narrowed to the city
    assert "ILIKE" not in sql
    assert "l.public_against" in sql and "l.officials_sided_against_public" in sql
    # Only the two reliable readings: supported / mixed leans are never read.
    assert "mostly_supported" not in sql and "mixed" not in sql


def test_by_place_lean_missing_table_is_zero_not_a_failure(get) -> None:
    err = asyncpg.exceptions.UndefinedTableError("relation \"data_center_meeting_lean\" does not exist")
    resp = get(_Conn(by_place=_PLACES, lean_error=err), {"state": "GA"})
    assert resp.status_code == 200, resp.text
    assert all(p["public_against_meetings"] == 0 and p["disagreement_meetings"] == 0 for p in resp.json()["counts"]["by_place"])


def test_no_lean_query_without_a_state(get) -> None:
    conn = _Conn(by_place=_PLACES)
    get(conn)
    assert not any("data_center_meeting_lean" in c[0] for c in conn.calls)


# --- #1124: the card's AI summary, meeting link and speaker -----------------------------------------------------


_COUNTS = [{"passages": 1, "meetings": 1, "site_specific": 0}]


def test_card_extras_summary_link_and_speaker_present(get) -> None:
    conn = _Conn(
        rows=[_item()], counts=_COUNTS,
        meetings=[{"video_id": "7VghnjHd_1w", "event_meeting_id": 4321, "meeting_summary": "The council discussed a pause."}],
        speakers=[{"data_center_meeting_mention_id": "m1", "speaker_display_name": "Test Person", "speaker_role": "Resident",
                   "speakers": 1}],
    )
    (item,) = get(conn, {"state": "NC"}).json()["items"]
    assert item["meeting_summary"] == "The council discussed a pause."
    assert item["meeting_url"] == "/meetings/4321"
    # Privacy: never more than "First L.", even if a fuller name reached the mart.
    assert item["speaker_display_name"] == "Test P." and item["speaker_role"] == "Resident"
    sql, params = next(c for c in conn.calls if "FROM event_meeting e" in c[0])
    assert params == (["7VghnjHd_1w"],)
    sql, params = next(c for c in conn.calls if "JOIN data_center_public_comment c" in c[0])
    assert params == (["m1"],)
    # Attribution only from a verbatim quote inside the excerpt: no timing guess.
    assert "position(" in sql and "c.speaker_display_name IS NOT NULL" in sql


def test_card_extras_absent_are_null(get) -> None:
    (item,) = get(_Conn(rows=[_item()], counts=_COUNTS)).json()["items"]
    assert item["meeting_summary"] is None and item["meeting_url"] is None
    assert item["speaker_display_name"] is None and item["speaker_role"] is None


def test_card_meeting_without_summary_keeps_link_only(get) -> None:
    conn = _Conn(rows=[_item()], counts=_COUNTS, meetings=[{"video_id": "7VghnjHd_1w", "event_meeting_id": 9, "meeting_summary": None}])
    (item,) = get(conn).json()["items"]
    assert item["meeting_summary"] is None and item["meeting_url"] == "/meetings/9"


def test_card_two_speakers_matching_is_no_speaker(get) -> None:
    conn = _Conn(rows=[_item()], counts=_COUNTS, speakers=[
        {"data_center_meeting_mention_id": "m1", "speaker_display_name": "A B.", "speaker_role": "Resident", "speakers": 2},
    ])
    (item,) = get(conn).json()["items"]
    assert item["speaker_display_name"] is None and item["speaker_role"] is None


def test_card_extras_missing_tables_still_answer(get) -> None:
    err = asyncpg.exceptions.UndefinedColumnError("column \"meeting_summary\" does not exist")
    resp = get(_Conn(rows=[_item()], counts=_COUNTS, extras_error=err))
    assert resp.status_code == 200, resp.text
    (item,) = resp.json()["items"]
    assert item["meeting_summary"] is None and item["speaker_display_name"] is None


def test_first_l() -> None:
    assert data_centers.first_l("Audra Thompson") == "Audra T."
    assert data_centers.first_l("Audra T.") == "Audra T."
    assert data_centers.first_l("Audra") == "Audra"
    assert data_centers.first_l("  ") is None and data_centers.first_l(None) is None
