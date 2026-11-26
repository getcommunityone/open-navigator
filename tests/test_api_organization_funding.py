"""GET /api/organizations/{id}/funding (#1073)."""
from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import FastAPI

from api.routes import organizations as orgs

AIRBNB = "aeaba7dca853623224831df17eabb364"
FOUNDATION = {
    "company_key": "airbnb", "company_name": "Airbnb", "foundation_name": "Airbnb.org", "foundation_ein": "833135259",
    "foundation_master_org_id": "833135259", "relationship": "founded_by_company",
    "foundation_source_url": "https://www.airbnb.org/about",
}


class _Conn:
    """Answers each query by a phrase in its SQL; records every call."""

    def __init__(self, *, table: bool = True, answers: dict[str, list[dict[str, Any]]] | None = None,
                 error: Exception | None = None):
        self.table = table
        self.answers = answers or {}
        self.error = error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchval(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        return self.table

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        for phrase, rows in self.answers.items():
            if phrase in sql:
                return rows
        return []


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

    monkeypatch.setattr(orgs, "get_db_pool", pool)
    app = FastAPI()
    app.include_router(orgs.router)

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(path, params=params)

    return asyncio.run(go())


def test_missing_table_returns_empty_lists(monkeypatch) -> None:
    conn = _Conn(table=False)
    r = _get(monkeypatch, conn, f"/api/organizations/{AIRBNB}/funding")
    assert r.status_code == 200
    body = r.json()
    assert body["funds"] == [] and body["funded_by"] == []
    assert body["funds_total"] is None and body["funds_grants"] == 0
    assert len(conn.calls) == 1  # only the table check


def test_funds_carry_real_sums_years_as_strings_and_links(monkeypatch) -> None:
    key = "135633307"
    conn = _Conn(answers={
        "SELECT DISTINCT company_key": [FOUNDATION],
        "SELECT tax_year, sum(amount)": [
            {"tax_year": 2023, "amount": 5165500, "grants": 22},
            {"tax_year": 2021, "amount": 11136000, "grants": 23},
        ],
        "WITH g AS": [{
            "grantee_key": key, "total_amount": 3951000, "grants": 3, "grantee_name": "HIAS INC",
            "grantee_ein": "135633307", "grantee_master_org_id": key, "grantee_city": "SILVER SPRING",
            "grantee_state_code": "MD", "foundation_name": "Airbnb.org", "foundation_ein": "833135259",
        }],
        "GROUP BY 1, 2 ORDER BY 1, 2": [
            {"grantee_key": key, "tax_year": 2023, "amount": 1000000, "grants": 1},
            {"grantee_key": key, "tax_year": 2021, "amount": 2951000, "grants": 2},
        ],
        "row_number() OVER (PARTITION BY coalesce": [
            {"grantee_key": key, "grant_id": "g1", "amount": 2000000, "purpose": "REFUGEE HOUSING",
             "tax_year": 2021, "source_url": "https://example.invalid/990.xml"},
        ],
    })
    r = _get(monkeypatch, conn, f"/api/organizations/{AIRBNB}/funding", {"limit": 10})
    assert r.status_code == 200
    body = r.json()
    assert body["funds_total"] == 5165500 + 11136000
    assert body["funds_grants"] == 45
    assert body["funds_by_year"][0] == {"tax_year": "2023", "amount": 5165500, "grants": 22}
    assert body["foundations"][0]["foundation_source_url"] == "https://www.airbnb.org/about"
    f = body["funds"][0]
    assert f["grantee_master_org_id"] == key and f["total_amount"] == 3951000
    assert [y["tax_year"] for y in f["by_year"]] == ["2023", "2021"]
    assert f["top_grants"][0]["tax_year"] == "2021" and f["top_grants"][0]["amount"] == 2000000
    assert body["funded_by"] == []
    # the company id matches its own rows or its foundation's, and the limit is bound
    funds_call = next(c for c in conn.calls if "WITH g AS" in c[0])
    assert "foundation_master_org_id = $1" in funds_call[0]
    assert funds_call[1] == (AIRBNB, 10)


def test_funded_by_lists_the_companies_behind_grants_to_a_grantee(monkeypatch) -> None:
    grantee = "135633307"
    conn = _Conn(answers={
        "GROUP BY 1, 2, 3, 4, 5, 6, 7, 8": [{
            **FOUNDATION, "master_org_id": AIRBNB, "total_amount": 3951000, "grants": 3,
        }],
        "SELECT foundation_ein, tax_year": [{"foundation_ein": "833135259", "tax_year": 2023, "amount": None, "grants": 1}],
        "SELECT foundation_ein, grant_id": [],
    })
    r = _get(monkeypatch, conn, f"/api/organizations/{grantee}/funding")
    assert r.status_code == 200
    body = r.json()
    assert body["funds"] == [] and body["funds_total"] is None
    fb = body["funded_by"][0]
    assert fb["company_name"] == "Airbnb" and fb["master_org_id"] == AIRBNB
    assert fb["total_amount"] == 3951000
    # an amount the 990 left blank stays blank, never 0
    assert fb["by_year"] == [{"tax_year": "2023", "amount": None, "grants": 1}]


def test_db_error_is_503(monkeypatch) -> None:
    r = _get(monkeypatch, _Conn(error=RuntimeError("down")), f"/api/organizations/{AIRBNB}/funding")
    assert r.status_code == 503
