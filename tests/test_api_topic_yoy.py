"""GET /api/topics/yoy (#1343, #1361): every major meeting topic, last full year against this year to date."""
from __future__ import annotations

import asyncio
import os
from datetime import date
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import topic_yoy as ty
from api.routes.topic_timeline import build_scope


class _Conn:
    def __init__(self, rows: list[dict[str, Any]]):
        self.rows = rows
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.rows


class _Acquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *a):
        return False


class _Pool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Acquire(self.conn)


def _get(monkeypatch, pool_factory, params: dict | None = None) -> httpx.Response:
    monkeypatch.setattr(ty, "get_db_pool", pool_factory)
    app = FastAPI()
    app.include_router(ty.router)

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get("/api/topics/yoy", params=params)

    return asyncio.run(go())


def _row(
    tid: int,
    slug: str,
    ma: int,
    mb: int,
    ra: int = 1000,
    rb: int = 1200,
    through=date(2026, 11, 23),
    source: str = "curated",
    has_story: bool = True,
) -> dict:
    return {
        "topic_id": tid, "slug": slug, "name": slug.replace("-", " ").capitalize(),
        "source": source, "has_story": has_story,
        "meetings_a": ma, "meetings_b": mb,
        "recorded_a": ra, "recorded_b": rb, "share_a": round(ma / ra, 6) if ra else None,
        "share_b": round(mb / rb, 6) if rb else None, "through": through,
    }


def test_rows_years_as_strings_thresholds_and_partial_year(monkeypatch) -> None:
    conn = _Conn([
        _row(100001, "data-centers", 146, 976),
        _row(100002, "water-fluoridation", 4, 82),
        _row(100007, "violent-crime", 0, 0, has_story=False),
        _row(83, "affordable-housing", 328, 552, source="civicsearch", has_story=False),
    ])

    async def pool():
        return _Pool(conn)

    r = _get(monkeypatch, pool)
    assert r.status_code == 200
    body = r.json()
    yb = str(date.today().year)
    assert body["year_b"] == yb and body["year_a"] == str(int(yb) - 1)
    assert body["year_b_through"] == "2026-11-23" and body["year_b_partial"] is True
    assert body["scope"]["level"] == "national"
    assert body["min_meetings"] == 5
    by = {t["slug"]: t for t in body["topics"]}
    assert by["data-centers"]["comparable"] is True
    assert by["data-centers"]["source"] == "curated"
    assert by["data-centers"]["has_story"] is True
    assert by["data-centers"]["share_b"] == round(976 / 1200, 6)
    assert by["affordable-housing"]["comparable"] is True
    assert by["affordable-housing"]["source"] == "civicsearch"
    assert by["affordable-housing"]["has_story"] is False
    # Fewer than 5 meetings in either year: listed, never compared.
    assert by["water-fluoridation"]["comparable"] is False
    assert by["violent-crime"]["comparable"] is False
    assert all(isinstance(t["year_a"], str) for t in body["topics"])


def test_scope_params_reach_every_leg(monkeypatch) -> None:
    conn = _Conn([_row(100001, "data-centers", 31, 65, 794, 790)])

    async def pool():
        return _Pool(conn)

    body = _get(monkeypatch, pool, {"state": "ga", "city": "Atlanta"}).json()
    assert body["scope"] == {"level": "city", "state_code": "GA", "state": "Georgia", "city": "Atlanta"}
    sql, params = conn.calls[0]
    # Two legs (topic_meeting_year and recorded_meeting_year) each filter on state and city.
    assert params.count("GA") == 2 and params.count("%Atlanta%") == 2
    assert "topic_meeting_year" in sql and "recorded_meeting_year" in sql


def test_source_filter_and_validation(monkeypatch) -> None:
    conn = _Conn([_row(83, "affordable-housing", 328, 552, source="civicsearch", has_story=False)])

    async def pool():
        return _Pool(conn)

    ok = _get(monkeypatch, pool, {"source": "CivicSearch"})
    assert ok.status_code == 200
    sql, params = conn.calls[0]
    assert "c.source = $" in sql
    assert params[-1] == "civicsearch"

    bad = _get(monkeypatch, pool, {"source": "unknown"})
    assert bad.status_code == 422


def test_too_few_recorded_meetings_makes_nothing_comparable() -> None:
    scope = build_scope("GA", "Smallville")
    out = ty.shape([_row(100005, "guns", 6, 7, 12, 15)], scope, 2025, 2026)
    assert out.topics[0].comparable is False


def test_share_over_one_is_never_drawn() -> None:
    out = ty.shape([_row(100005, "guns", 50, 30, 40, 40)], build_scope(None, None), 2025, 2026)
    assert out.topics[0].comparable is False


def test_thin_year() -> None:
    assert ty.thin_year(2025, 2026, 14038, 16873) is None
    assert ty.thin_year(2025, 2026, 1000, 200) == "2026"
    assert ty.thin_year(2025, 2026, 100, 900) == "2025"
    assert ty.thin_year(2025, 2026, 0, 0) is None


def test_full_year_through_december_is_not_partial() -> None:
    out = ty.shape([_row(100005, "guns", 60, 70, through=date(2026, 12, 31))], build_scope(None, None), 2025, 2026)
    assert out.year_b_partial is False


def test_db_failure_is_503(monkeypatch) -> None:
    async def pool():
        raise RuntimeError("down")

    assert _get(monkeypatch, pool).status_code == 503


# --- the live warehouse: the endpoint's numbers equal the marts' ----------------------------------------------------

_DB = {
    "host": os.environ.get("TOPIC_TEST_DB_HOST", "localhost"),
    "port": int(os.environ.get("TOPIC_TEST_DB_PORT", "5433")),
    "user": os.environ.get("POSTGRES_USER", "postgres"),
    "password": os.environ.get("POSTGRES_PASSWORD", ""),
    "database": "open_navigator",
}


@pytest.mark.parametrize("state", [None, "GA"])
def test_live_numbers_match_marts(monkeypatch, state: str | None) -> None:
    yb = date.today().year
    ya = yb - 1

    async def run():
        try:
            pool = await asyncpg.create_pool(**_DB, min_size=1, max_size=2, timeout=3,
                                             server_settings={"search_path": "public"})
        except (TimeoutError, OSError, asyncpg.PostgresError):
            return None
        try:
            async with pool.acquire() as c:
                try:
                    rec = await c.fetchrow(
                        "SELECT coalesce(sum(recorded_meetings) FILTER (WHERE meeting_year = $1), 0)::int AS a,"
                        " coalesce(sum(recorded_meetings) FILTER (WHERE meeting_year = $2), 0)::int AS b"
                        " FROM recorded_meeting_year WHERE ($3::text IS NULL OR state_code = $3)", ya, yb, state)
                    guns = await c.fetchrow(
                        "SELECT count(DISTINCT video_id) FILTER (WHERE extract(year FROM event_date)::int = $1)::int AS a,"
                        " count(DISTINCT video_id) FILTER (WHERE extract(year FROM event_date)::int = $2)::int AS b"
                        " FROM topic_transcript_link l JOIN civicsearch_topic c ON c.topic_id = l.topic_id"
                        " WHERE c.query_id = 'guns' AND l.event_date <= current_date"
                        " AND ($3::text IS NULL OR l.state_code = $3)", ya, yb, state)
                    dc = await c.fetchrow(
                        "SELECT count(DISTINCT video_id) FILTER (WHERE extract(year FROM meeting_date)::int = $1)::int AS a,"
                        " count(DISTINCT video_id) FILTER (WHERE extract(year FROM meeting_date)::int = $2)::int AS b"
                        " FROM data_center_meeting_mention WHERE meeting_date <= current_date"
                        " AND ($3::text IS NULL OR state_code = $3)", ya, yb, state)
                    housing = await c.fetchrow(
                        "SELECT coalesce(sum(meetings) FILTER (WHERE meeting_year = $1), 0)::int AS a,"
                        " coalesce(sum(meetings) FILTER (WHERE meeting_year = $2), 0)::int AS b"
                        " FROM topic_meeting_year m JOIN civicsearch_topic c ON c.topic_id = m.topic_id"
                        " WHERE c.query_id = 'affordable-housing'"
                        " AND ($3::text IS NULL OR m.state_code = $3)", ya, yb, state)
                except asyncpg.exceptions.UndefinedTableError:
                    return None

            async def get_pool():
                return pool

            r = _get_async(monkeypatch, get_pool, {"state": state} if state else None)
            return rec, guns, dc, housing, await r
        finally:
            await pool.close()

    out = asyncio.run(run())
    if out is None:
        pytest.skip("local warehouse not reachable")
    rec, guns, dc, housing, body = out
    assert body["recorded_a"] == rec["a"] and body["recorded_b"] == rec["b"]
    by = {t["slug"]: t for t in body["topics"]}
    assert (by["guns"]["meetings_a"], by["guns"]["meetings_b"]) == (guns["a"], guns["b"])
    assert by["guns"]["source"] == "curated" and by["guns"]["has_story"] is True
    assert (by["data-centers"]["meetings_a"], by["data-centers"]["meetings_b"]) == (dc["a"], dc["b"])
    assert by["data-centers"]["has_story"] is True
    assert (by["affordable-housing"]["meetings_a"], by["affordable-housing"]["meetings_b"]) == (housing["a"], housing["b"])
    assert by["affordable-housing"]["source"] == "civicsearch" and by["affordable-housing"]["has_story"] is False
    if rec["b"]:
        assert by["guns"]["share_b"] == pytest.approx(guns["b"] / rec["b"], abs=1e-6)


async def _get_async(monkeypatch, pool_factory, params):
    monkeypatch.setattr(ty, "get_db_pool", pool_factory)
    app = FastAPI()
    app.include_router(ty.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        return (await c.get("/api/topics/yoy", params=params)).json()
