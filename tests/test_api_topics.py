"""Topics API (#500): curated "Data centers" topic alongside the CivicSearch taxonomy.

The DB layer is mocked: ``get_db_pool`` returns a fake pool that records SQL and
params and returns canned rows.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from api.routes import search, topics


class _Conn:
    def __init__(self, rows=None, total: int = 0, row=None):
        self.rows = rows or []
        self.total = total
        self.row = row
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.rows

    async def fetchval(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.total

    async def fetchrow(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.row


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

        monkeypatch.setattr(topics, "get_db_pool", pool)
        app = FastAPI()
        app.include_router(topics.router)

        async def go():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
                return await c.get(path, params=params)

        return asyncio.run(go())

    return _get


def test_topic_list_carries_source_and_scoped_meeting_count(get):
    conn = _Conn(rows=[
        dict(topic_id=51, name="Education, schools, students", query_id="education",
             keyword_stats='["school board"]', transcript_occurrences=63046,
             source="civicsearch", meeting_count=14387),
        dict(topic_id=100001, name="Data centers", query_id="data-centers",
             keyword_stats='["data center", "hyperscale"]', transcript_occurrences=0,
             source="curated", meeting_count=81),
    ])
    r = get(conn, "/api/topics", {"state": "ga"})
    assert r.status_code == 200
    body = r.json()
    assert body[1]["source"] == "curated"
    assert body[1]["meeting_count"] == 81
    assert body[1]["keywords"] == ["data center", "hyperscale"]
    sql, params = conn.calls[0]
    # state is normalized and drives the per-state count + existence filter
    assert params == (None, "GA")
    assert "browse_entity_state_transcript_count" in sql
    assert "to_jsonb(t) ->> 'source'" in sql


def test_every_topic_gets_the_scoped_count_not_only_curated_ones(get):
    """#504: under a state the CivicSearch topics carry that state's meeting count too."""
    conn = _Conn(rows=[
        dict(topic_id=51, name="Education, schools, students", query_id="education",
             keyword_stats="[]", transcript_occurrences=63046, source="civicsearch", meeting_count=193),
    ])
    body = get(conn, "/api/topics", {"state": "al"}).json()
    assert body[0]["source"] == "civicsearch" and body[0]["meeting_count"] == 193
    sql, params = conn.calls[0]
    assert params == (None, "AL")
    count_expr = sql[sql.index("CASE WHEN $2::text IS NULL"):sql.index("END AS meeting_count")]
    assert "browse_entity_state_transcript_count" in count_expr
    assert "browse_transcript_count n" in count_expr
    assert "source" not in count_expr and "curated" not in count_expr  # no per-source branch


def test_topic_list_source_defaults_when_column_missing(get):
    conn = _Conn(rows=[dict(topic_id=1, name="X", query_id=None, keyword_stats=None,
                            transcript_occurrences=3, source=None, meeting_count=None)])
    body = get(conn, "/api/topics").json()
    assert body[0]["source"] == "civicsearch"
    assert body[0]["meeting_count"] is None


def test_topic_meetings_returns_highlighted_passages_in_scope(get):
    conn = _Conn(total=2, rows=[dict(
        video_id="abc123", event_title="County Commission", event_date=date(2026, 9, 2),
        state_code="GA", state="Georgia", city=None, jurisdiction_name="Coweta County",
        video_url="https://www.youtube.com/watch?v=abc123",
        evidence_passage="the proposed <mark>data</mark> <mark>center</mark> on Highway 16",
        n_keyword_hits=2,
    )])
    r = get(conn, "/api/topics/100001/meetings", {"state": "ga", "city": "Coweta", "limit": 6})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["topic_id"] == 100001
    item = body["items"][0]
    assert item["date"] == "2026-09-02"
    assert "<mark>data</mark>" in item["excerpt"]
    count_sql, count_params = conn.calls[0]
    assert "topic_transcript_link" in count_sql
    assert count_params == (100001, "GA", "%Coweta%")
    _, list_params = conn.calls[1]
    assert list_params == (100001, "GA", "%Coweta%", 6, 0)


def test_topic_meetings_national_scope_passes_nulls(get):
    conn = _Conn(total=0, rows=[])
    body = get(conn, "/api/topics/51/meetings").json()
    assert body == {"topic_id": 51, "total": 0, "items": []}
    assert conn.calls[0][1] == (51, None, None)


def test_curated_topic_tsquery_matches_phrases_not_loose_words():
    tq = search._curated_topic_tsquery(
        "Data centers",
        ["data center", "data centre", "data centers", "hyperscale", "server farm"],
    )
    assert tq == (
        "(data <-> center) | (data <-> centre) | (data <-> centers) | hyperscale | (server <-> farm)"
    )


def test_curated_topic_tsquery_is_injection_safe_and_handles_empty():
    assert search._curated_topic_tsquery("x", ["data' | !center & (farm"]) == (
        "(data <-> center <-> farm)"
    )
    assert search._curated_topic_tsquery("x", ["", "123"]) is None


def test_resolve_topic_tsquery_uses_phrases_for_curated(monkeypatch):
    conn = _Conn(row=dict(name="Data centers", keyword_stats='["data center", "hyperscale"]',
                          source="curated"))

    async def pool():
        return _Pool(conn)

    monkeypatch.setattr(search.search_postgres, "get_db_pool", pool)
    assert asyncio.run(search.resolve_topic_tsquery(100001)) == "(data <-> center) | hyperscale"


def test_resolve_topic_tsquery_keeps_word_or_for_civicsearch(monkeypatch):
    conn = _Conn(row=dict(name="Police matters", keyword_stats='["police chief"]',
                          source="civicsearch"))

    async def pool():
        return _Pool(conn)

    monkeypatch.setattr(search.search_postgres, "get_db_pool", pool)
    assert asyncio.run(search.resolve_topic_tsquery(66)) == "police | matters | chief"
