"""GET /api/data-centers/concerns (#251, DC-4.3): what residents object to, by area."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import data_centers

PATH = "/api/data-centers/concerns"


class _Conn:
    def __init__(self, area=None, national=None, error: Exception | None = None):
        self.area, self.national, self.error = area or [], national or [], error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        return self.national if "area_level = 'national'" in sql else self.area


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


def _row(concern: str, n: int, total: int, rank: int, dominant: bool, j: str | None = "Tuscaloosa") -> dict:
    return dict(concern=concern, mention_count=n, objection_count=total, share=n / total, concern_rank=rank,
                is_dominant=dominant, jurisdiction_name=j, last_meeting_on=date(2026, 6, 10))


def test_city_returns_area_and_national(get) -> None:
    conn = _Conn(area=[_row("water", 3, 4, 1, True), _row("noise", 1, 4, 2, False)],
                 national=[_row("water", 3, 6, 1, True, None)])
    body = get(conn, {"state": "AL", "city": "Tuscaloosa"}).json()
    assert body["scope"]["level"] == "city"
    assert [i["concern"] for i in body["items"]] == ["water", "noise"]
    assert body["items"][0]["is_dominant"] and body["items"][0]["share"] == 0.75
    assert body["national"][0]["share"] == 0.5
    area_sql, area_params = conn.calls[1]
    assert "area_level = 'jurisdiction'" in area_sql and area_params == ("AL", "%Tuscaloosa%")


def test_national_scope_reuses_the_national_rows(get) -> None:
    conn = _Conn(national=[_row("water", 3, 6, 1, True, None)])
    body = get(conn).json()
    assert body["scope"]["level"] == "national" and body["items"] == body["national"]
    assert len(conn.calls) == 1


def test_no_concern_data_is_empty_not_invented(get) -> None:
    body = get(_Conn(), {"state": "WY"}).json()
    assert body["items"] == [] and body["national"] == []


def test_missing_mart_and_errors(get) -> None:
    assert get(_Conn(error=asyncpg.exceptions.UndefinedTableError("x"))).json()["items"] == []
    assert get(_Conn(error=RuntimeError("boom"))).status_code == 500
