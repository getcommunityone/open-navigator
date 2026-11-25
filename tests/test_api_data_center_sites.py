"""GET /api/data-centers/sites (#249, DC-4.1): Epoch AI sites with status and source.

The DB layer is mocked: ``get_db_pool`` returns a fake pool that records SQL and
params and returns canned rows (counts for the GROUP BY query, items otherwise).
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

PATH = "/api/data-centers/sites"


class _Conn:
    def __init__(self, rows=None, counts=None, error: Exception | None = None):
        self.rows = rows or []
        self.counts = counts or []
        self.error = error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        return self.counts if "GROUP BY 1" in sql else self.rows


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


def _site(**kw) -> dict[str, Any]:
    base = dict(
        data_center_site_id="abc", site_name="Site A", owner=None, users=None, project=None,
        address=None, country="United States", state_code="TX", state="Texas", status="planned",
        last_known_status="planned", status_as_of=date(2027, 1, 1), construction_note=None,
        it_power_mw=None, first_seen_on=date(2026, 11, 15), last_seen_on=date(2026, 11, 15),
        is_listed=True, source_name="Epoch AI", source_url="https://epoch.ai/data/data-centers",
        license="CC BY 4.0", attribution='Epoch AI, "AI data centers". Licensed CC BY 4.0.',
    )
    base.update(kw)
    return base


def test_state_scope_counts_and_credit(get) -> None:
    conn = _Conn(
        rows=[_site(), _site(data_center_site_id="d", site_name="Site D", status="no_longer_listed",
                             last_known_status="operating", is_listed=False, last_seen_on=date(2026, 10, 1))],
        counts=[{"status": "planned", "n": 1}, {"status": "no_longer_listed", "n": 1},
                {"status": "status_not_published", "n": 2}],
    )
    resp = get(conn, {"state": "Texas", "city": "Abilene"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scope"] == {"level": "state", "state_code": "TX", "state": "Texas", "city": None, "jurisdiction_id": None}
    assert body["city_applied"] is False
    assert body["counts"] == {"planned": 1, "under_construction": 0, "operating": 0, "cancelled": 0,
                              "no_longer_listed": 1, "status_not_published": 2}
    gone = body["items"][1]
    assert gone["status"] == "no_longer_listed" and gone["last_known_status"] == "operating"
    assert gone["last_seen_on"] == "2026-10-01"
    assert all(i["license"] == "CC BY 4.0" and i["source_name"] == "Epoch AI" for i in body["items"])
    items_sql, items_params = conn.calls[0]
    assert "state_code = $1" in items_sql and items_params == ("TX", 100)
    counts_sql, counts_params = conn.calls[1]
    assert counts_params == ("TX",) and "status = " not in counts_sql


def test_status_filter_narrows_items_not_counts() -> None:
    scope = data_centers.build_scope(None, None, None)
    items_sql, params, counts_sql, counts_params = data_centers.build_sites_queries(scope, "planned", 5)
    assert "status = $1" in items_sql and params == ["planned", 5]
    assert counts_params == [] and "WHERE TRUE" in counts_sql


def test_bad_status_is_422(get) -> None:
    assert get(_Conn(), {"status": "abandoned"}).status_code == 422


def test_registry_sites_carry_their_own_source_and_credit(get) -> None:
    """#958: a registry site is credited to the registry on its own row, and may be cancelled (the registry says so)."""
    reg = _site(
        data_center_site_id="r1", site_name="100 Jersey Avenue Data Center", state_code="NJ", state="New Jersey",
        status="cancelled", last_known_status="cancelled", source="us_data_center_registry",
        source_status="cancelled", city="New Brunswick", county="Middlesex", latitude=40.488, longitude=-74.457,
        source_name="US Data Center Registry (SueDataCenters.org)",
        source_url="https://suedatacenters.org/data-centers/jersey-avenue-new-brunswick-data-center-nj",
        attribution="US Data Center Registry, SueDataCenters.org (Theory Road LLC), base data from Compute Atlas. CC BY 4.0.",
    )
    conn = _Conn(rows=[_site(), reg], counts=[{"status": "planned", "n": 1}, {"status": "cancelled", "n": 1}])
    body = get(conn, {"status": "cancelled"}).json()
    assert body["counts"]["cancelled"] == 1
    epoch, registry = body["items"]
    assert epoch["source"] == "epoch" and epoch["source_name"] == "Epoch AI"
    assert registry["source"] == "us_data_center_registry" and registry["status"] == "cancelled"
    assert registry["source_url"].startswith("https://suedatacenters.org/") and "Compute Atlas" in registry["attribution"]
    assert registry["city"] == "New Brunswick"
    items_sql, _ = conn.calls[0]
    assert "source, source_status" in items_sql and "WHEN 'cancelled' THEN 3" in items_sql


def test_missing_mart_is_an_empty_list(get) -> None:
    resp = get(_Conn(error=asyncpg.exceptions.UndefinedTableError("no relation")))
    assert resp.status_code == 200
    assert resp.json()["items"] == [] and resp.json()["scope"]["level"] == "national"


def test_other_errors_are_500(get) -> None:
    assert get(_Conn(error=RuntimeError("boom"))).status_code == 500
