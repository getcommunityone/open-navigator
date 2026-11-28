"""GET /api/rankings and /api/rankings/topics (#1437): where places stand on a topic. The pool is faked."""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from api.routes import rankings as rk


class _Conn:
    def __init__(self, rows: list[dict[str, Any]], topic: dict[str, Any] | None):
        self.rows, self.topic = rows, topic
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.rows

    async def fetchrow(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.topic


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


def _get(monkeypatch, conn: _Conn, path: str, params: dict | None = None) -> httpx.Response:
    async def pool():
        return _Pool(conn)

    monkeypatch.setattr(rk, "get_db_pool", pool)
    app = FastAPI()
    app.include_router(rk.router)

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(path, params=params)

    return asyncio.run(go())


def _place(jid: str, band: str, f: int, a: int, ranked: bool, rank: int | None, shrunk: float, **kw) -> dict[str, Any]:
    return {"jurisdiction_id": jid, "jurisdiction_name": jid.title(), "state_code": "AL", "size_band": band,
            "population": 1000, "speakers_for": f, "speakers_against": a, "meetings": 3,
            "against_share": a / (f + a), "shrunk_against_share": shrunk, "is_ranked": ranked, "band_rank": rank,
            "band_ranked_count": 1 if ranked else None, "officials_side": kw.get("officials_side"),
            "last_meeting_date": date(2026, 10, 1), "topic_id": 100001, "slug": "data-centers",
            "name": "Data centers", "national_against_share": 0.8}


TOPIC = {"topic_id": 100001, "slug": "data-centers", "name": "Data centers"}


def test_places_ranked_first_and_national_summary(monkeypatch) -> None:
    rows = [_place("tiny", "small", 1, 2, False, None, 0.77), _place("big", "large", 2, 18, True, 1, 0.85),
            _place("mid", "mid", 12, 3, True, 1, 0.42, officials_side="for")]
    r = _get(monkeypatch, _Conn(rows, TOPIC), "/api/rankings", {"topic": "data-centers"})
    assert r.status_code == 200
    body = r.json()
    assert [p["jurisdiction_id"] for p in body["places"]] == ["big", "mid", "tiny"]
    n = body["national"]
    assert n["places_ranked"] == 2 and n["places_unranked"] == 1
    assert n["places_leaning_against"] == 1 and n["places_leaning_for"] == 1
    assert n["speakers_for"] == 15 and n["speakers_against"] == 23
    assert n["against_share"] == round(23 / 38, 4)
    assert n["median_shrunk_against_share"] == round((0.85 + 0.42) / 2, 4)
    assert body["places"][1]["officials_side"] == "for"
    # nothing names a person: only place fields
    assert not any(k for k in body["places"][0] if "speaker_label" in k or "name" == k)


def test_band_and_state_are_passed_to_sql_and_validated(monkeypatch) -> None:
    conn = _Conn([], TOPIC)
    r = _get(monkeypatch, conn, "/api/rankings", {"topic": "100001", "band": "MID", "state": "al"})
    assert r.status_code == 200
    assert conn.calls[0][1] == (100001, None)
    assert conn.calls[1][1] == (rk.WINDOW_MONTHS, 100001, "mid", "AL")
    body = r.json()
    assert body["places"] == [] and body["national"]["against_share"] is None
    assert body["national"]["median_shrunk_against_share"] is None
    assert _get(monkeypatch, conn, "/api/rankings", {"topic": "x", "band": "huge"}).status_code == 422
    assert _get(monkeypatch, conn, "/api/rankings", {"topic": "x", "state": "Alabama"}).status_code == 422


def test_unknown_topic_is_404(monkeypatch) -> None:
    assert _get(monkeypatch, _Conn([], None), "/api/rankings", {"topic": "nope"}).status_code == 404


def test_topics_summary(monkeypatch) -> None:
    rows = [_place("big", "large", 2, 18, True, 1, 0.85), _place("b2", "mid", 1, 19, True, 1, 0.9),
            _place("tiny", "small", 1, 2, False, None, 0.77)]
    r = _get(monkeypatch, _Conn(rows, None), "/api/rankings/topics")
    assert r.status_code == 200
    [t] = r.json()
    assert t == {"topic_id": 100001, "slug": "data-centers", "name": "Data centers", "places_ranked": 2,
                 "places_unranked": 1, "places_leaning_against": 2, "places_leaning_for": 0,
                 "national_against_share": 0.8, "median_shrunk_against_share": 0.875}


@pytest.mark.parametrize("shrunk,against,for_", [(0.5, 0, 0), (0.51, 1, 0), (0.49, 0, 1)])
def test_leaning_needs_more_than_half(shrunk: float, against: int, for_: int) -> None:
    s = rk.summarise([_place("p", "mid", 5, 5, True, 1, shrunk)])
    assert (s["places_leaning_against"], s["places_leaning_for"]) == (against, for_)
