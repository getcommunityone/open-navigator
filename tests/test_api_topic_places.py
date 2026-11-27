"""GET /api/topics/{topic_id}/places (#1349): a topic's meetings per government in one state, for the county map.

The DB layer is mocked; the rows are test stand-ins shaped like topic_place_meeting, not warehouse figures. A last
test reads the local warehouse, when it is reachable, and checks the mart's sums against topic_transcript_link.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import topics

PATH = "/api/topics/{}/places"


def _row(jid: str, kind: str, meetings: int, against: int = 0, forr: int = 0, split: int = 0, silent: int = 0, **kw: Any):
    return {
        "jurisdiction_id": jid,
        "jurisdiction_name": kw.get("name", jid),
        "jurisdiction_type": kind,
        "geoid": kw.get("geoid"),
        "latitude": kw.get("lat"),
        "longitude": kw.get("lon"),
        "meetings": meetings,
        "lean_meetings": against + forr + split + silent,
        "public_against_meetings": against,
        "public_for_meetings": forr,
        "no_side_meetings": split,
        "silent_meetings": silent,
        "disagreement_meetings": kw.get("disagree", 0),
    }


ROWS = [
    _row("c1", "city", 9, against=1, silent=8, lat=30.5, lon=-87.9),
    _row("k1", "county", 2, geoid="01073", split=1, silent=1),
    _row("c2", "city", 1, lat=33.2, lon=-87.5),
]


class _Conn:
    def __init__(self, total: int, rows: list[dict[str, Any]] | None, error: bool = False):
        self.total, self.rows, self.error = total, rows, error

    async def fetchval(self, sql: str, *params: Any):
        assert "topic_transcript_link" in sql
        return self.total

    async def fetch(self, sql: str, *params: Any):
        assert "topic_place_meeting" in sql
        if self.error:
            raise asyncpg.exceptions.UndefinedTableError('relation "topic_place_meeting" does not exist')
        return self.rows or []


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
    def _get(conn: _Conn, topic_id: int, params: dict[str, Any]) -> httpx.Response:
        async def pool():
            return _Pool(conn)

        monkeypatch.setattr(topics, "get_db_pool", pool)
        app = FastAPI()
        app.include_router(topics.router)

        async def go():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
                return await c.get(PATH.format(topic_id), params=params)

        return asyncio.run(go())

    return _get


def test_place_counts_sum_to_total_minus_unplaced(get):
    r = get(_Conn(15, ROWS), 100002, {"state": "al"})
    assert r.status_code == 200
    body = r.json()
    assert body["state_code"] == "AL" and body["available"] is True
    assert body["total_meetings"] == 15
    assert sum(p["meetings"] for p in body["by_place"]) == body["total_meetings"] - body["unplaced_meetings"]
    assert body["unplaced_meetings"] == 3


def test_ai_reading_is_carried_as_meetings_in_the_map_shape(get):
    body = get(_Conn(12, ROWS), 100002, {"state": "AL"}).json()
    c1 = body["by_place"][0]
    assert c1["speakers_against"] == 1 and c1["speakers_for"] == 0 and c1["silent_meetings"] == 8
    assert c1["latitude"] == 30.5 and c1["longitude"] == -87.9
    k1 = body["by_place"][1]
    assert k1["jurisdiction_type"] == "county" and k1["geoid"] == "01073" and k1["speakers_neutral"] == 1
    assert all(p["speakers_question"] == 0 for p in body["by_place"])


def test_missing_mart_keeps_the_outline_not_an_error(get):
    body = get(_Conn(7, None, error=True), 100002, {"state": "AL"}).json()
    assert body["available"] is False and body["by_place"] == [] and body["unplaced_meetings"] == 7


def test_state_is_required(get):
    assert get(_Conn(0, []), 100002, {}).status_code == 422


def _dsn() -> str | None:
    return os.environ.get("OPEN_NAVIGATOR_DATABASE_URL")


@pytest.mark.skipif(not _dsn(), reason="local warehouse not configured")
def test_warehouse_place_sums_never_exceed_the_state_totals():
    """Against the real mart: per (topic, state), placed meetings = total minus unplaced and never more than total."""

    async def go():
        try:
            conn = await asyncpg.connect(_dsn(), timeout=5)
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"warehouse unreachable: {e}")
        try:
            try:
                rows = await conn.fetch(
                    """
                    WITH t AS (SELECT topic_id, state_code, count(DISTINCT video_id)::int AS total
                               FROM public.topic_transcript_link WHERE state_code IS NOT NULL GROUP BY 1, 2),
                         p AS (SELECT topic_id, state_code, sum(meetings)::int AS placed
                               FROM public.topic_place_meeting GROUP BY 1, 2)
                    SELECT t.topic_id, t.state_code, t.total, coalesce(p.placed, 0) AS placed
                    FROM t LEFT JOIN p USING (topic_id, state_code)
                    """
                )
            except asyncpg.exceptions.UndefinedTableError:
                pytest.skip("topic_place_meeting not built in this warehouse")
        finally:
            await conn.close()
        return rows

    rows = asyncio.run(go())
    assert rows
    for r in rows:
        assert 0 <= r["placed"] <= r["total"], dict(r)
