"""Which meeting a story map card quotes (#1230).

Two layers:

* Route tests with a mocked pool: the topic ``/states`` route and the data-center ``meeting-mentions?quotes_per_state=``
  route run the map-quote SQL, pass the stance through, and fall back to the newest passage when the serving copy lacks
  ``meeting_video_kind``.
* SQL tests (``live``) that run the real selection SQL on Postgres against TEMP fixture tables (temp tables shadow the
  served names, so nothing real is read or written): an interview is never quoted, a meeting where the public took a side
  wins over a newer keyword-only one, and with no stance a screened meeting wins over an unscreened one.

Every row here is a test stand-in for a mart's shape, not a warehouse figure.
"""

from __future__ import annotations

import asyncio
import os
from datetime import date
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import data_centers, topics


# --- mocked pool -------------------------------------------------------------------------------------------------


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


def _call(monkeypatch, module, conn, path: str, params: dict[str, Any] | None = None, prefix: str = "") -> httpx.Response:
    async def pool():
        return _Pool(conn)

    monkeypatch.setattr(module, "get_db_pool", pool)
    app = FastAPI()
    app.include_router(module.router, prefix=prefix)

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(path, params=params or {})

    return asyncio.run(go())


def _topic_row(**kw) -> dict[str, Any]:
    base = dict(
        video_id="v1", event_title="City Council Meeting", event_date=date(2025, 10, 1), state_code="AL",
        state="Alabama", city="Tuscaloosa", jurisdiction_name="Tuscaloosa", video_url="https://www.youtube.com/watch?v=v1",
        evidence_passage="stolen <mark>guns</mark>", n_keyword_hits=3, public_stance="against",
    )
    base.update(kw)
    return base


class _TopicConn:
    def __init__(self, kind_missing: bool = False):
        self.kind_missing = kind_missing
        self.calls: list[str] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append(sql)
        if "DISTINCT ON (l.state_code, l.video_id)" in sql:
            if "meeting_video_kind" in sql:
                if self.kind_missing:
                    raise asyncpg.exceptions.UndefinedTableError('relation "meeting_video_kind" does not exist')
                return [
                    _topic_row(video_id="v1", public_stance="against"),
                    _topic_row(video_id="v2", public_stance="for", event_title="Council 2"),
                    _topic_row(video_id="v3", public_stance="split", event_title="Council 3"),
                ][: int(params[2])]
            return [
                _topic_row(public_stance=None, video_id="newest1"),
                _topic_row(public_stance=None, video_id="newest2"),
            ][: int(params[2])]
        if "DISTINCT ON (l.state_code)" in sql:
            if "meeting_video_kind" in sql:
                if self.kind_missing:
                    raise asyncpg.exceptions.UndefinedTableError('relation "meeting_video_kind" does not exist')
                return [_topic_row()]
            return [_topic_row(public_stance=None, video_id="newest")]
        if "GROUP BY l.state_code" in sql:
            return [{"state_code": "AL", "state": "Alabama", "meetings": 386}]
        return []


def test_topic_states_quote_carries_the_public_stance(monkeypatch) -> None:
    conn = _TopicConn()
    r = _call(monkeypatch, topics, conn, "/api/topics/100005/states")
    assert r.status_code == 200
    (q,) = r.json()["newest"]
    assert q["video_id"] == "v1" and q["public_stance"] == "against"
    assert q["excerpt"] == "stolen <mark>guns</mark>"
    pick = next(s for s in conn.calls if "DISTINCT ON (l.state_code)" in s)
    # Real meetings only, stance meetings first.
    assert "k.is_public_meeting IS NOT FALSE" in pick
    assert "'mostly_opposed', 'mostly_supportive', 'mixed'" in pick


def test_topic_states_falls_back_to_newest_without_meeting_kind(monkeypatch) -> None:
    r = _call(monkeypatch, topics, _TopicConn(kind_missing=True), "/api/topics/100005/states")
    assert r.status_code == 200
    (q,) = r.json()["newest"]
    assert q["video_id"] == "newest" and q["public_stance"] is None


def test_topic_states_quotes_per_state_returns_multiple_distinct_meetings(monkeypatch) -> None:
    conn = _TopicConn()
    r = _call(monkeypatch, topics, conn, "/api/topics/100005/states", {"quotes_per_state": 3})
    assert r.status_code == 200
    newest = r.json()["newest"]
    assert [m["video_id"] for m in newest] == ["v1", "v2", "v3"]
    assert [m["public_stance"] for m in newest] == ["against", "for", "split"]
    pick = next(s for s in conn.calls if "DISTINCT ON (l.state_code, l.video_id)" in s)
    assert "k.is_public_meeting IS NOT FALSE" in pick
    assert "stance_rn" in pick


def test_topic_states_quotes_per_state_fallback_and_bounds(monkeypatch) -> None:
    r = _call(monkeypatch, topics, _TopicConn(kind_missing=True), "/api/topics/100005/states", {"quotes_per_state": 2})
    assert r.status_code == 200
    assert [m["video_id"] for m in r.json()["newest"]] == ["newest1", "newest2"]
    bad = _call(monkeypatch, topics, _TopicConn(), "/api/topics/100005/states", {"quotes_per_state": 20})
    assert bad.status_code == 422


def _dc_item(**kw) -> dict[str, Any]:
    base = dict(
        data_center_meeting_mention_id="m1", video_id="vid1", video_url="https://www.youtube.com/watch?v=vid1",
        meeting_title="City Council Meeting", meeting_date=date(2026, 5, 26), jurisdiction_id="j1",
        jurisdiction_name="Charlotte", state_code="NC", state="North Carolina", passage_index=4, start_seconds=60.0,
        evidence="a <mark>data</mark> <mark>center</mark>", match_terms=["data center"], match_strength="data_center",
        data_center_site_id=None, site_name=None, site_match_basis=None,
    )
    base.update(kw)
    return base


class _DcConn:
    def __init__(self, kind_missing: bool = False):
        self.kind_missing = kind_missing
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if "state_rank" in sql:
            if self.kind_missing:
                raise asyncpg.exceptions.UndefinedTableError('relation "meeting_video_kind" does not exist')
            return [_dc_item(video_id="stance")]
        if "AS passages" in sql:
            return [{"passages": 9, "meetings": 5, "site_specific": 0}]
        if "GROUP BY m.state_code" in sql:
            return [{"state_code": "NC", "state": "North Carolina", "meetings": 5}]
        if "FROM data_center_meeting_mention m" in sql and "ORDER BY m.meeting_date DESC" in sql:
            return [_dc_item(video_id="newest")]
        return []


def test_dc_quotes_per_state_uses_the_map_quote_query(monkeypatch) -> None:
    conn = _DcConn()
    r = _call(monkeypatch, data_centers, conn, "/api/data-centers/meeting-mentions", {"quotes_per_state": 3}, "/api")
    assert r.status_code == 200
    body = r.json()
    assert [i["video_id"] for i in body["items"]] == ["stance"]
    # Counts are the scope's, unchanged by the per-state pick.
    assert body["counts"]["meetings"] == 5
    sql, params = next(c for c in conn.calls if "state_rank" in c[0])
    assert params[-1] == 3
    assert "k.is_public_meeting IS NOT FALSE" in sql and "l.public_against" in sql


def test_dc_quotes_per_state_falls_back_to_newest(monkeypatch) -> None:
    conn = _DcConn(kind_missing=True)
    r = _call(monkeypatch, data_centers, conn, "/api/data-centers/meeting-mentions", {"quotes_per_state": 3}, "/api")
    assert r.status_code == 200
    assert [i["video_id"] for i in r.json()["items"]] == ["newest"]


def test_dc_without_quotes_per_state_keeps_newest_first(monkeypatch) -> None:
    conn = _DcConn()
    r = _call(monkeypatch, data_centers, conn, "/api/data-centers/meeting-mentions", {}, "/api")
    assert [i["video_id"] for i in r.json()["items"]] == ["newest"]
    assert not any("state_rank" in c[0] for c in conn.calls)


def test_dc_quotes_per_state_is_bounded(monkeypatch) -> None:
    r = _call(monkeypatch, data_centers, _DcConn(), "/api/data-centers/meeting-mentions", {"quotes_per_state": 50}, "/api")
    assert r.status_code == 422


# --- the real SQL on Postgres, against temp fixture tables ---------------------------------------------------------


def _dsn() -> str:
    """Any Postgres: the test only creates TEMP tables, which vanish with the connection."""
    if os.getenv("RUN_LIVE_TESTS") != "1":
        pytest.skip("live: set RUN_LIVE_TESTS=1 and TEST_DATABASE_URL")
    dsn = os.getenv("TEST_DATABASE_URL", "")
    if not dsn:
        pytest.skip("needs TEST_DATABASE_URL (any Postgres; only TEMP tables are created)")
    return dsn


_FIXTURE_DDL = """
CREATE TEMP TABLE topic_transcript_link (
    topic_id int, video_id text, event_title text, event_date date, state_code text, state text, city text,
    jurisdiction_name text, video_url text, evidence_passage text, n_keyword_hits int);
CREATE TEMP TABLE topic_meeting_lean (
    video_id text, topic_id int, public_lean text, public_lean_p numeric, public_against boolean, public_for boolean);
CREATE TEMP TABLE meeting_video_kind (video_id text, meeting_kind text, is_public_meeting boolean);
CREATE TEMP TABLE data_center_meeting_mention (
    data_center_meeting_mention_id text, video_id text, video_url text, meeting_title text, meeting_date date,
    jurisdiction_id text, jurisdiction_name text, state_code text, state text, passage_index int,
    start_seconds numeric, evidence text, match_terms text[], match_strength text, data_center_site_id text,
    site_match_basis text);
CREATE TEMP TABLE data_center_site (data_center_site_id text, site_name text);
CREATE TEMP TABLE data_center_meeting_lean (video_id text, public_lean text, public_against boolean);
"""


def _link(video_id: str, title: str, d: str, state: str = "AL") -> tuple:
    return (100005, video_id, title, date.fromisoformat(d), state, None, None, "Place", f"https://y/{video_id}",
            f"<mark>guns</mark> in {video_id}", 1)


async def _with_fixtures(fn):
    conn = await asyncpg.connect(_dsn())
    try:
        await conn.execute(_FIXTURE_DDL)
        return await fn(conn)
    finally:
        await conn.close()


@pytest.mark.live
def test_topic_sql_skips_interviews_and_prefers_stance_meetings() -> None:
    async def run(conn):
        await conn.executemany(
            "INSERT INTO topic_transcript_link VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)",
            [
                _link("interview", "Full Interview", "2026-09-08"),            # newest, but an interview
                _link("keyword", "City Council Meeting", "2026-06-01"),       # newer, public silent
                _link("stance", "City Council Meeting", "2025-10-01"),        # older, public opposed
                _link("tx_unscreened", "Council", "2026-03-01", "TX"),        # no stance, never screened
                _link("tx_screened", "Council", "2025-01-01", "TX"),          # no stance, screened meeting
            ],
        )
        await conn.executemany(
            "INSERT INTO topic_meeting_lean VALUES ($1, 100005, $2, $3, $4, $5)",
            [
                ("interview", "did_not_speak", 0.9, False, False),
                ("keyword", "did_not_speak", 0.9, False, False),
                ("stance", "mostly_opposed", 0.95, True, False),
            ],
        )
        await conn.executemany(
            "INSERT INTO meeting_video_kind VALUES ($1, $2, $3)",
            [
                ("interview", "government_other", False),
                ("keyword", "government_meeting", True),
                ("tx_screened", "government_meeting", True),
            ],
        )
        return await topics.fetch_newest_per_state(conn, 100005, None)

    rows = {r["state_code"]: dict(r) for r in asyncio.run(_with_fixtures(run))}
    assert rows["AL"]["video_id"] == "stance" and rows["AL"]["public_stance"] == "against"
    assert rows["TX"]["video_id"] == "tx_screened" and rows["TX"]["public_stance"] is None


@pytest.mark.live
def test_topic_sql_reports_silent_and_split() -> None:
    async def run(conn):
        await conn.executemany(
            "INSERT INTO topic_transcript_link VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)",
            [_link("weak", "Council", "2025-01-01", "CA"), _link("silent", "Council", "2025-01-01", "NY")],
        )
        await conn.executemany(
            "INSERT INTO topic_meeting_lean VALUES ($1, 100005, $2, $3, $4, $5)",
            [("weak", "mostly_supportive", 0.55, False, False), ("silent", "did_not_speak", 0.9, False, False)],
        )
        return await topics.fetch_newest_per_state(conn, 100005, None)

    rows = {r["state_code"]: r["public_stance"] for r in asyncio.run(_with_fixtures(run))}
    # A lean under P 0.7 is split, as on the map; a read meeting where the public didn't speak is silent.
    assert rows == {"CA": "split", "NY": "silent"}


@pytest.mark.live
def test_dc_sql_one_passage_per_meeting_real_meetings_against_first() -> None:
    def mention(mid: str, vid: str, d: str, idx: int, state: str = "NC") -> tuple:
        return (mid, vid, f"https://y/{vid}", "Council", date.fromisoformat(d), "j", "Place", state, None, idx, None,
                f"<mark>data center</mark> {mid}", ["data center"], "data_center", None, None)

    async def run(conn):
        await conn.executemany(
            "INSERT INTO data_center_meeting_mention VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)",
            [
                mention("a", "briefing", "2026-09-01", 1),
                mention("b", "newer", "2026-08-01", 1),
                mention("c", "opposed", "2026-01-01", 2),
                mention("d", "opposed", "2026-01-01", 1),
            ],
        )
        await conn.executemany(
            "INSERT INTO data_center_meeting_lean VALUES ($1, $2, $3)",
            [("opposed", "mostly_opposed", True), ("newer", "no_public_comment_on_data_center", False)],
        )
        await conn.execute("INSERT INTO meeting_video_kind VALUES ('briefing', 'government_other', false)")
        scope = data_centers.JobClaimScope(level="national")
        sql, params = data_centers.build_mention_state_quotes_query(scope, None, None, 3)
        return await conn.fetch(sql, *params)

    rows = asyncio.run(_with_fixtures(run))
    assert [(r["video_id"], r["passage_index"]) for r in rows] == [("opposed", 1), ("newer", 1)]
