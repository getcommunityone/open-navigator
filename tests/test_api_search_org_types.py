"""Organization sub-type search filter + facets (#1221).

The DB layer is mocked: ``get_db_pool`` returns a fake pool that records SQL and
params and returns canned rows, so these tests pin the SQL contract without a
warehouse.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from api.routes import search, search_postgres
from api.routes.search_postgres import (
    ORG_TYPE_PREDICATES,
    SEARCHABLE_ORG_TYPES,
    org_type_where,
    parse_org_types,
)


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


def _patch_pool(monkeypatch, conn: _Conn) -> None:
    async def pool():
        return _Pool(conn)

    monkeypatch.setattr(search_postgres, "get_db_pool", pool)


# ---- vocabulary ---------------------------------------------------------------


def test_parse_org_types_dedupes_and_lowercases():
    assert parse_org_types(None) == []
    assert parse_org_types("") == []
    assert parse_org_types("Nonprofit, church,nonprofit") == ["nonprofit", "church"]


@pytest.mark.parametrize("raw", ["other", "nonprofits", "drop table"])
def test_parse_org_types_rejects_unknown(raw: str):
    with pytest.raises(ValueError):
        parse_org_types(raw)


def test_other_is_never_searchable():
    # 'other' holds private family / living trusts from property records.
    assert "other" not in SEARCHABLE_ORG_TYPES
    assert "other" not in ORG_TYPE_PREDICATES
    assert "'other'" not in org_type_where(None)


def test_org_type_where_narrows_with_or():
    sql = org_type_where(["foundation", "company"])
    assert sql.startswith("m.org_type IN (")
    assert "s.foundation_code IN ('02','03','04')" in sql
    assert "m.org_type IN ('business','company')" in sql
    assert " OR " in sql
    # bare-name form for the search's renamed `base` projection
    assert org_type_where(["church"], m="", s="").endswith("(org_type = 'church')")


# ---- search_organizations_pg ----------------------------------------------------


def _org_row(**over):
    row = dict(
        master_org_id="org_1", ein=None, name="First Baptist Church", city="Tuscaloosa",
        state_code="AL", state="Alabama", county=None, org_type="church",
        org_subtype="place_of_worship", ntee_code=None, ntee_description=None,
        revenue=None, assets=None, income=None, tax_period=None, gt990_tax_year=None,
        gt990_total_revenue=None, gt990_total_expenses=None, gt990_total_assets=None,
        gt990_mission=None, has_gt990_data=None,
    )
    row.update(over)
    return row


def test_org_search_left_joins_and_filters_sub_type(monkeypatch):
    conn = _Conn(rows=[_org_row()])
    _patch_pool(monkeypatch, conn)
    results = asyncio.run(search_postgres.search_organizations_pg("baptist", org_types=["church"]))
    sql = conn.calls[0][0]
    assert "LEFT JOIN mdm_organization_nonprofit s" in sql
    assert "(org_type = 'church')" in sql
    assert results[0].metadata["org_type"] == "church"
    # A non-nonprofit describes itself by its type, not as a nonprofit.
    assert results[0].description == "Place of worship"


def test_org_search_without_sub_type_still_excludes_other(monkeypatch):
    conn = _Conn(rows=[])
    _patch_pool(monkeypatch, conn)
    asyncio.run(search_postgres.search_organizations_pg("water"))
    sql = conn.calls[0][0]
    assert "org_type IN ('nonprofit', 'church'" in sql
    assert "'other'" not in sql


# ---- counts + facets -------------------------------------------------------------


def test_count_organizations_mirrors_join_and_filter(monkeypatch):
    search._count_cache.clear()
    conn = _Conn(total=42)
    _patch_pool(monkeypatch, conn)
    n = asyncio.run(search.count_organizations(state="AL", org_types=["government"]))
    assert n == 42
    sql, params = conn.calls[0]
    assert "LEFT JOIN mdm_organization_nonprofit s" in sql
    assert "(m.org_type = 'government')" in sql
    assert params == ("AL",)


def test_count_organization_types_returns_facets_and_selected(monkeypatch):
    search._org_type_facet_cache.clear()
    row = {k: i + 1 for i, k in enumerate(ORG_TYPE_PREDICATES)}
    row["selected"] = 7
    conn = _Conn(row=row)
    _patch_pool(monkeypatch, conn)
    out = asyncio.run(search.count_organization_types(query="health", org_types=["healthcare"]))
    assert out is not None
    assert set(out) == {*ORG_TYPE_PREDICATES, "selected"}
    assert out["selected"] == 7
    sql = conn.calls[0][0]
    assert "AS foundation" in sql and "AS selected" in sql
    assert "plainto_tsquery('english', $1)" in sql


def test_count_organization_types_times_out_to_none(monkeypatch):
    search._org_type_facet_cache.clear()

    class _Slow(_Conn):
        async def fetchrow(self, sql, *params):
            await asyncio.sleep(1)

    _patch_pool(monkeypatch, _Slow())
    monkeypatch.setattr(search, "ORG_TYPE_FACET_TIMEOUT_S", 0.01)
    assert asyncio.run(search.count_organization_types(query="church")) is None


# ---- endpoint validation ---------------------------------------------------------


def _get(params: dict[str, Any]) -> httpx.Response:
    app = FastAPI()
    app.include_router(search.router, prefix="/api")

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get("/api/search", params=params)

    return asyncio.run(go())


def test_unknown_org_type_is_400():
    r = _get({"types": "organizations", "org_type": "other"})
    assert r.status_code == 400
    assert r.json()["detail"] == "unknown org_type other"


def test_unknown_facet_is_400():
    r = _get({"types": "organizations", "facets": "nope"})
    assert r.status_code == 400


def test_rare_sub_type_browse_is_fenced(monkeypatch):
    conn = _Conn(rows=[])
    _patch_pool(monkeypatch, conn)
    asyncio.run(search_postgres.search_organizations_pg(None, org_types=["political"]))
    assert "OFFSET 0" in conn.calls[0][0]
    conn.calls.clear()
    asyncio.run(search_postgres.search_organizations_pg(None, org_types=["nonprofit"]))
    assert "OFFSET 0" not in conn.calls[0][0]
