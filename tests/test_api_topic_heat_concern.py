"""GET /api/topics/{topic}/heat-by-year and /top-concern (#1418). The DB layer is mocked; rows are test stand-ins."""

from __future__ import annotations

import asyncio
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import topic_caption_facts as tcf


class _Conn:
    def __init__(self, routes: dict[str, Any], fail: tuple[str, ...] = ()):
        self.routes, self.fail, self.calls = routes, fail, []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        for marker in self.fail:
            if marker in sql:
                raise asyncpg.exceptions.UndefinedTableError(f'relation "{marker}" does not exist')
        for marker, rows in self.routes.items():
            if marker in sql:
                return rows
        return []


class _Acq:
    def __init__(self, c):
        self.c = c

    async def __aenter__(self):
        return self.c

    async def __aexit__(self, *_):
        return None


class _Pool:
    def __init__(self, c):
        self.c = c

    def acquire(self):
        return _Acq(self.c)


@pytest.fixture
def get(monkeypatch):
    def _get(conn: _Conn, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        async def pool():
            return _Pool(conn)

        monkeypatch.setattr(tcf, "get_db_pool", pool)
        app = FastAPI()
        app.include_router(tcf.router)

        async def go():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
                return await c.get(path, params=params or {})

        return asyncio.run(go())

    return _get


TOPIC = {"FROM civicsearch_topic": [{"topic_id": 100001, "query_id": "data-centers"}]}


def test_heat_by_year_serves_years_as_strings(get):
    rows = [
        {"year": 2025, "mean_heat": 1.4, "speakers_rated": 40, "share_heated": 0.1, "speakers_heated": 4},
        {"year": 2026, "mean_heat": 2.9, "speakers_rated": 55, "share_heated": 0.4, "speakers_heated": 22},
    ]
    conn = _Conn({**TOPIC, "FROM topic_heat_year": rows})
    r = get(conn, "/api/topics/data-centers/heat-by-year", {"state": "va"})
    assert r.status_code == 200
    d = r.json()
    assert d["scope"]["level"] == "state" and d["scope"]["state_code"] == "VA"
    assert d["years"][1] == {"year": "2026", "mean": 2.9, "speakers_rated": 55, "share_heated": 0.4, "speakers_heated": 22}
    assert conn.calls[-1][1] == (100001, "state", "VA", None)


def test_heat_by_year_city_needs_a_state(get):
    conn = _Conn({**TOPIC})
    d = get(conn, "/api/topics/data-centers/heat-by-year", {"city": "Tuscaloosa"}).json()
    assert d["scope"]["level"] == "national" and d["years"] == []
    d = get(conn, "/api/topics/data-centers/heat-by-year", {"state": "AL", "city": "Tuscaloosa"}).json()
    assert d["scope"]["level"] == "city" and d["scope"]["city"] == "Tuscaloosa"


def test_heat_by_year_missing_mart_is_empty_not_error(get):
    conn = _Conn({**TOPIC}, fail=("topic_heat_year",))
    r = get(conn, "/api/topics/data-centers/heat-by-year")
    assert r.status_code == 200 and r.json()["years"] == []


def test_top_concern(get):
    row = {"concern_label": "Water use", "turns_with_concern": 31, "turns_read": 80, "basis": "opposing", "share": 0.3875}
    r = get(_Conn({**TOPIC, "FROM topic_top_concern": [row]}), "/api/topics/data-centers/top-concern")
    assert r.json() | {"scope": None} == {
        "topic": "data-centers", "scope": None, "label": "Water use", "count": 31, "of": 80, "basis": "opposing", "share": 0.3875,
    }


def test_top_concern_none_when_below_minimum(get):
    d = get(_Conn({**TOPIC}), "/api/topics/data-centers/top-concern").json()
    assert d["label"] is None and d["count"] is None and d["of"] is None


def test_unknown_topic_404(get):
    assert get(_Conn({}), "/api/topics/nope/heat-by-year").status_code == 404
