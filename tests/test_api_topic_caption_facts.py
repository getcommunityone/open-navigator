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
    lean = [{"lean_meetings": 80, "public_against_meetings": 30, "public_for_meetings": 5, "has_public_for": True,
             "disagreement_meetings": 12, "disagreement_states": 4}]
    conn = topic_conn(routes={"FROM topic_meeting_lean": lean})
    d = get(conn, "short-term-rentals").json()
    assert d["lean_meetings"] == 80
    assert d["public_for_meetings"] == 5
    assert d["disagreement_meetings"] == 12
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
            {"for_": 3, "against": 18, "question": 1, "neutral": 7, "meetings_reviewed": 188, "states": 4}
        ],
        "FROM data_center_meeting_lean": [
            {"lean_meetings": 1828, "public_against_meetings": 283, "public_against_states": 32, "public_for_meetings": 0, "has_public_for": False,
             "disagreement_meetings": 23, "disagreement_states": 10}
        ],
        "FROM jurisdictions": POPS,
    }
    routes.update(extra.pop("routes", {}))
    return _Conn(routes, **extra)


def test_data_centers_reads_speakers_and_lean(get):
    d = get(dc_conn(), "data-centers").json()
    assert d["meetings"] == 1859
    assert d["speakers"] == {"for": 3, "against": 18, "question": 1, "neutral": 7, "states": 4}
    assert d["public_against_meetings"] == 283
    assert d["public_against_states"] == 32
    assert d["public_for_meetings"] is None  # the data-center mart has no public_for reading
    assert d["disagreement_meetings"] == 23
    assert d["disagreement_states"] == 10
    assert d["top_state"] == "NC"


def test_data_centers_missing_marts_are_null(get):
    conn = dc_conn(fail=("data_center_meeting_position", "data_center_meeting_lean", "jurisdictions"))
    d = get(conn, "data-centers", {"state": "GA"}).json()
    assert d["meetings"] == 118
    assert d["speakers"] is None
    assert d["lean_meetings"] is None and d["disagreement_meetings"] is None
    assert d["states"][0]["population"] is None


def test_lean_sql_scopes():
    sql, params = tcf.build_lean_sql(100001, "GA", "%Fayette%")
    assert "data_center_meeting_lean" in sql and "topic_id" not in sql
    assert params == ["GA", "%Fayette%"]
    sql, params = tcf.build_lean_sql(100005, None, None)
    assert "topic_meeting_lean" in sql and params == [100005]
