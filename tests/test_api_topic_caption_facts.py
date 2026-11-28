"""GET /api/topics/{topic}/caption-facts (#1125): the real counts behind a topic caption.

The DB layer is mocked: ``get_db_pool`` returns a fake pool that routes each SQL to canned rows. The rows are test
stand-ins for the shapes the marts return, not warehouse figures.
"""

from __future__ import annotations

import asyncio
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import topic_caption_facts as tcf

PATH = "/api/topics/{}/caption-facts"


class _Conn:
    def __init__(self, routes: dict[str, Any], fail: tuple[str, ...] = ()):
        self.routes = routes
        self.fail = fail
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        for marker in self.fail:
            if marker in sql:
                raise asyncpg.exceptions.UndefinedTableError(f'relation "{marker}" does not exist')
        for marker, rows in self.routes.items():
            if marker in sql:
                return rows(params) if callable(rows) else rows
        return []


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
    def _get(conn: _Conn, topic: str, params: dict[str, Any] | None = None) -> httpx.Response:
        async def pool():
            return _Pool(conn)

        monkeypatch.setattr(tcf, "get_db_pool", pool)
        app = FastAPI()
        app.include_router(tcf.router)

        async def go():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
                return await c.get(PATH.format(topic), params=params or {})

        return asyncio.run(go())

    return _get


POPS = [
    {"state_code": "CA", "state": "California", "population": 39_000_000},
    {"state_code": "NC", "state": "North Carolina", "population": 10_000_000},
    {"state_code": "FL", "state": "Florida", "population": 21_000_000},
]
TOPIC_STATES = [
    {"state_code": "CA", "state": None, "meetings": 570},
    {"state_code": "NC", "state": None, "meetings": 317},
    {"state_code": "FL", "state": None, "meetings": 40},
]


def topic_conn(**extra) -> _Conn:
    routes = {
        "FROM civicsearch_topic": [{"topic_id": 100003, "query_id": "short-term-rentals"}],
        "FROM browse_transcript_count": [{"n": 4186}],
        "FROM browse_entity_state_transcript_count": TOPIC_STATES,
        "FROM browse_entity_place_transcript_count": [
            {"name": "Orlando", "meetings": 13},
            {"name": "Orlando Utilities", "meetings": 20},
            {"name": "Titusville", "meetings": 9},
        ],
        "FROM jurisdictions": POPS,
    }
    routes.update(extra.pop("routes", {}))
    return _Conn(routes, **extra)


def test_national_topic_counts_and_ratio(get):
    conn = topic_conn(fail=("topic_meeting_lean",))
    r = get(conn, "short-term-rentals")
    assert r.status_code == 200
    d = r.json()
    assert d["topic"] == "short-term-rentals"
    assert d["scope"]["level"] == "national"
    assert d["meetings"] == 4186
    assert [s["state_code"] for s in d["states"]] == ["CA", "NC", "FL"]
    assert d["states"][0]["state"] == "California"
    assert d["states"][0]["population"] == 39_000_000
    assert d["top_state"] == "CA"
    assert d["ratio_to_next"] == pytest.approx(1.8, abs=0.01)
    # Not data centers: no speakers; topic_meeting_lean missing -> every AI reading is null, not 0.
    assert d["speakers"] is None
    assert d["public_against_meetings"] is None and d["disagreement_meetings"] is None
    assert any("topic_meeting_lean" in sql for sql, _ in conn.calls)


def test_state_scope_reads_the_state_from_the_national_list(get):
    r = get(topic_conn(), "short-term-rentals", {"state": "fl"})
    d = r.json()
    assert d["scope"] == {"level": "state", "state_code": "FL", "state": "Florida", "city": None}
    assert d["meetings"] == 40
    # The state list is never narrowed: the state can be ranked.
    assert len(d["states"]) == 3


def test_city_scope_prefers_the_exact_place(get):
    r = get(topic_conn(), "short-term-rentals", {"state": "FL", "city": "orlando"})
    d = r.json()
    assert d["scope"]["level"] == "city"
    assert d["place"] == "Orlando"
    assert d["meetings"] == 13
    assert [p["name"] for p in d["places"]] == ["Orlando", "Orlando Utilities", "Titusville"]


def test_city_without_state_is_ignored(get):
    d = get(topic_conn(), "short-term-rentals", {"city": "Orlando"}).json()
    assert d["scope"]["level"] == "national"
    assert d["places"] is None


def test_topic_meeting_lean_lights_up_when_present(get):
    lean = [{"lean_meetings": 80, "public_against_meetings": 30, "public_for_meetings": 5,              "disagreement_meetings": 12, "disagreement_states": 4}]
    conn = topic_conn(routes={"FROM topic_meeting_lean": lean})
    d = get(conn, "short-term-rentals").json()
    assert d["lean_meetings"] == 80
    assert d["public_for_meetings"] == 5
    assert d["disagreement_meetings"] == 12
    # #1200: no split or silent count in this row: 0, not derived.
    assert d["public_silent_meetings"] == 0
    assert d["public_split_meetings"] == 0
    params = next(p for s, p in conn.calls if "topic_meeting_lean" in s)
    assert params[0] == 100003


def test_alias_resolves_flock_to_the_plate_reader_topic(get):
    conn = topic_conn()
    get(conn, "flock")
    sql, params = conn.calls[0]
    assert "civicsearch_topic" in sql and params == ("license-plate-readers",)


def test_unknown_topic_is_404(get):
    conn = _Conn({"FROM civicsearch_topic": []})
    assert get(conn, "nope").status_code == 404


def test_required_query_failure_is_503(get):
    conn = topic_conn(fail=("browse_transcript_count",))
    assert get(conn, "short-term-rentals").status_code == 503


def dc_conn(**extra) -> _Conn:
    routes = {
        "FROM civicsearch_topic": [{"topic_id": 100001, "query_id": "data-centers"}],
        "count(DISTINCT m.video_id)::int AS n FROM data_center_meeting_mention": [{"n": 1859}],
        "GROUP BY m.state_code": [
            {"state_code": "NC", "state": "North Carolina", "meetings": 122},
            {"state_code": "GA", "state": "Georgia", "meetings": 118},
        ],
        "FROM data_center_meeting_position": [
            {"for_": 3, "against": 18, "question": 1, "neutral": 7, "meetings_reviewed": 188, "states": 4,
             "decisions_with_tally": 12, "votes_for": 79, "votes_against": 10}
        ],
        "FROM data_center_meeting_lean": [
            {"lean_meetings": 1828, "public_against_meetings": 283, "public_against_states": 32, "public_for_meetings": 0,
             "disagreement_meetings": 23, "disagreement_states": 10}
        ],
        "FROM jurisdictions": POPS,
    }
    routes.update(extra.pop("routes", {}))
    return _Conn(routes, **extra)


def test_data_centers_reads_speakers_and_lean(get):
    d = get(dc_conn(), "data-centers").json()
    assert d["meetings"] == 1859
    assert d["speakers"] == {"for": 3, "against": 18, "question": 1, "neutral": 7, "states": 4, "meetings_reviewed": 188}
    # #1289: the recorded votes, so the stance headline can be checked against them.
    assert d["votes"] == {"decisions": 12, "for": 79, "against": 10, "decisions_for": None, "decisions_against": None}
    assert d["public_against_meetings"] == 283
    assert d["public_against_states"] == 32
    assert d["public_for_meetings"] == 0  # #1200: read from public_lean for data centers too
    assert d["disagreement_meetings"] == 23
    assert d["disagreement_states"] == 10
    assert d["top_state"] == "NC"


def test_data_centers_missing_marts_are_null(get):
    conn = dc_conn(fail=("data_center_meeting_position", "data_center_meeting_lean", "jurisdictions"))
    d = get(conn, "data-centers", {"state": "GA"}).json()
    assert d["meetings"] == 118
    assert d["speakers"] is None
    assert d["votes"] is None
    assert d["lean_meetings"] is None and d["disagreement_meetings"] is None
    assert d["states"][0]["population"] is None


def test_data_centers_reviewed_no_votes(get):
    """#1289: meetings reviewed with no tally give 0 decisions (a real 0); votes stay 0, never null sums."""
    row = {"for_": 0, "against": 0, "question": 0, "neutral": 0, "meetings_reviewed": 24, "states": 0,
           "decisions_with_tally": 0, "votes_for": None, "votes_against": None}
    d = get(dc_conn(routes={"FROM data_center_meeting_position": [row]}), "data-centers", {"state": "AL"}).json()
    assert d["speakers"]["meetings_reviewed"] == 24
    assert d["votes"] == {"decisions": 0, "for": 0, "against": 0, "decisions_for": 0, "decisions_against": 0}


def test_lean_sql_scopes():
    sql, params = tcf.build_lean_sql(100001, "GA", "%Fayette%")
    assert "data_center_meeting_lean" in sql and "topic_id" not in sql
    assert params == ["GA", "%Fayette%"]
    sql, params = tcf.build_lean_sql(100005, None, None)
    assert "topic_meeting_lean" in sql and params == [100005]


def _lean_by_scope(params):
    """Data-center lean rows that depend on the scope params: (state, city) -> canned counts (test stand-ins)."""
    if not params:
        return [{"lean_meetings": 1828, "public_against_meetings": 283, "public_against_states": 32,
                 "disagreement_meetings": 23, "disagreement_states": 10}]
    if len(params) == 1:
        return [{"lean_meetings": 71, "public_against_meetings": 6, "public_against_states": 1,
                 "disagreement_meetings": 0, "disagreement_states": 0}]
    return [{"lean_meetings": 2, "public_against_meetings": 0, "public_against_states": 0,
             "disagreement_meetings": 0, "disagreement_states": 0}]


def test_city_scope_returns_state_then_national_readings(get):
    """#1182: a city too thin for its own reading gets its state's and the country's, nearest first."""
    conn = dc_conn(routes={
        "FROM data_center_meeting_lean": _lean_by_scope,
        "GROUP BY m.jurisdiction_name": [{"name": "Tuscaloosa", "meetings": 2}],
        "AND m.jurisdiction_name ILIKE": [{"n": 2}],
        "FROM jurisdictions": [{"state_code": "AL", "state": "Alabama", "population": 5_000_000}],
    })
    d = get(conn, "data-centers", {"state": "AL", "city": "Tuscaloosa"}).json()
    assert d["public_against_meetings"] == 0
    assert [(w["level"], w["state_code"], w["state"]) for w in d["wider"]] == [
        ("state", "AL", "Alabama"),
        ("national", None, None),
    ]
    assert d["wider"][0]["public_against_meetings"] == 6
    assert d["wider"][1]["public_against_meetings"] == 283
    assert d["wider"][1]["public_against_states"] == 32


def test_state_scope_returns_national_reading_and_national_none(get):
    conn = dc_conn(routes={"FROM data_center_meeting_lean": _lean_by_scope})
    d = get(conn, "data-centers", {"state": "GA"}).json()
    assert [w["level"] for w in d["wider"]] == ["national"]
    assert get(dc_conn(), "data-centers").json()["wider"] is None


def test_wider_left_out_when_no_reading_loaded(get):
    conn = topic_conn(fail=("topic_meeting_lean",))
    d = get(conn, "short-term-rentals", {"state": "FL"}).json()
    assert d["wider"] == []


def test_split_and_silent_add_up_to_the_meetings_read(get):
    """#1200: the four positions (against, for, split, silent) always add up to the meetings read."""
    lean = [{"lean_meetings": 100, "public_against_meetings": 20, "public_for_meetings": 10, "public_silent_meetings": 60,
             "public_split_meetings": 10,
             "disagreement_meetings": 0, "disagreement_states": 0}]
    d = get(topic_conn(routes={"FROM topic_meeting_lean": lean}), "guns").json()
    assert (d["public_against_meetings"], d["public_for_meetings"], d["public_split_meetings"], d["public_silent_meetings"]) == (20, 10, 10, 60)


def test_lean_sql_reads_for_and_silent_from_public_lean():
    sql, _ = tcf.build_lean_sql(100005, None, None)
    assert "AS public_for_meetings" in sql and "AS public_silent_meetings" in sql
    assert "did_not_speak" in sql and "no_public_comment_on_data_center" in sql
    assert "public_lean_p, 0) >= 0.7" in sql


def test_split_counts_mixed_and_unsure_leans_only():
    """A label outside the question's choices (#1201) is never counted as split."""
    sql, _ = tcf.build_lean_sql(100002, None, None)
    assert "l.public_lean = 'mixed'" in sql and "public_lean_p, 0) < 0.7" in sql


def test_nothing_read_is_zero_and_a_failed_read_is_null(get):
    """#1200: a lean query that ran and found nothing is 0 ("no reading yet"); one that failed stays null."""
    empty = [{"lean_meetings": 0, "public_against_meetings": 0, "public_against_states": 0, "public_for_meetings": 0,
              "public_silent_meetings": 0, "public_split_meetings": 0, "disagreement_meetings": 0, "disagreement_states": 0}]
    d = get(topic_conn(routes={"FROM topic_meeting_lean": empty}), "guns").json()
    assert d["lean_meetings"] == 0 and d["public_against_meetings"] is None
    d = get(topic_conn(fail=("topic_meeting_lean",)), "guns").json()
    assert d["lean_meetings"] is None


# --- #1290: which way the votes went, and the caption comments --------------------------------------------------------

def test_vote_sides_and_caption_comments(get):
    routes = {
        "FROM data_center_decision": [
            {"decisions_tallied": 12, "yes_votes": 79, "no_votes": 10, "decisions_for": 7, "decisions_against": 5, "has_side": True}
        ],
        "FROM data_center_comment": [{"comments": 2822, "governments": 334}],
    }
    d = get(dc_conn(routes=routes), "data-centers").json()
    assert d["votes"]["decisions_for"] == 7 and d["votes"]["decisions_against"] == 5
    assert d["caption_comments"] == {"comments": 2822, "governments": 334}


def test_with_sides_every_vote_count_comes_from_the_decision_mart(get):
    routes = {
        "FROM data_center_decision": [
            {"decisions_tallied": 4, "yes_votes": 20, "no_votes": 3, "decisions_for": 3, "decisions_against": 1, "has_side": True}
        ]
    }
    v = get(dc_conn(routes=routes), "data-centers").json()["votes"]
    # The positions mart said 12 decisions; the decision mart (preferred analysis, no ties) has 4: one basis, one count.
    assert v == {"decisions": 4, "for": 20, "against": 3, "decisions_for": 3, "decisions_against": 1}


def test_vote_sides_and_comments_scope_like_the_speakers(get):
    conn = dc_conn(routes={"FROM data_center_decision": [{"decisions_tallied": 1, "decisions_for": 1, "decisions_against": 0, "has_side": True}]})
    get(conn, "data-centers", {"state": "AL", "city": "Tuscaloosa"})
    for marker in ("FROM data_center_decision", "FROM data_center_comment"):
        assert next(p for sql, p in conn.calls if marker in sql) == ("AL", "%Tuscaloosa%")


def test_missing_vote_side_or_comment_table_is_null_not_zero(get):
    d = get(dc_conn(fail=("data_center_decision", "data_center_comment")), "data-centers").json()
    assert d["votes"]["decisions"] == 12  # the tallies still come from the positions mart
    assert d["votes"]["decisions_for"] is None and d["votes"]["decisions_against"] is None
    assert d["caption_comments"] is None


def test_serving_copy_without_vote_side_has_null_sides(get):
    d = get(dc_conn(routes={"FROM data_center_decision": [{"decisions_for": 0, "decisions_against": 0, "has_side": False}]}), "data-centers").json()
    assert d["votes"]["decisions_for"] is None


def test_other_topics_have_no_caption_comments(get):
    conn = _Conn({"FROM civicsearch_topic": [{"topic_id": 100005, "query_id": "guns"}], "FROM jurisdictions": POPS})
    d = get(conn, "guns").json()
    assert d["caption_comments"] is None and d["votes"] is None


# --- #1330: officials' positions and meetings with any position --------------------------------------------------------

def test_official_positions_and_position_meetings(get):
    routes = {
        "FROM data_center_meeting_lean": [
            {"lean_meetings": 71, "public_against_meetings": 6, "public_against_states": 1, "public_for_meetings": 0,
             "public_split_meetings": 2, "public_silent_meetings": 63, "disagreement_meetings": 0, "disagreement_states": 0,
             "official_against_meetings": 7, "official_for_meetings": 8, "official_divided_meetings": 13,
             "position_meetings": 31, "both_position_meetings": 5}
        ]
    }
    d = get(dc_conn(routes=routes), "data-centers", {"state": "AL"}).json()
    assert (d["official_against_meetings"], d["official_for_meetings"], d["official_divided_meetings"]) == (7, 8, 13)
    assert d["position_meetings"] == 31 and d["both_position_meetings"] == 5


def test_lean_sql_counts_official_positions_on_the_p07_rule():
    sql, _ = tcf.build_lean_sql(tcf.DATA_CENTERS_TOPIC_ID, "AL", None)
    assert "official_lean = 'mostly_opposed' AND coalesce(l.official_lean_p, 0) >= 0.7" in sql
    assert "AS position_meetings" in sql and "AS both_position_meetings" in sql


def test_older_reading_without_official_counts_leaves_them_null(get):
    d = get(dc_conn(), "data-centers").json()
    assert d["position_meetings"] is None and d["official_for_meetings"] is None


def test_classifier_speakers_are_a_labelled_separate_source(get):
    """#1391: speakers' own words read by the classifier come back as their own labelled block, scoped like the rest,
    and never fold into the hand-counted speakers."""
    clf = [{"for_": 4, "against": 9, "concerns_only": 3, "no_position": 1, "meetings": 6}]
    conn = topic_conn(routes={"FROM meeting_speaker_topic_side": clf})
    d = get(conn, "guns", {"state": "GA", "city": "Atlanta"}).json()
    c = d["classifier_speakers"]
    assert c == {"source": "speakers' own words, classifier", "for": 4, "against": 9, "concerns_only": 3,
                 "no_position": 1, "meetings": 6}
    assert d["speakers"] is None
    sql, params = next((s, p) for s, p in conn.calls if "meeting_speaker_topic_side" in s)
    assert "not_sure" in sql and params == (100003, "GA", "%Atlanta%")  # topic_conn resolves every slug to 100003


def test_classifier_speakers_null_when_missing_or_none_read(get):
    assert get(topic_conn(fail=("meeting_speaker_topic_side",)), "guns").json()["classifier_speakers"] is None
    zero = [{"for_": 0, "against": 0, "concerns_only": 0, "no_position": 0, "meetings": 0}]
    assert get(topic_conn(routes={"FROM meeting_speaker_topic_side": zero}), "guns").json()["classifier_speakers"] is None
