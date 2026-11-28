"""GET /api/data-centers/sites-timeline and GET /api/coverage/recorded-meetings (#1348).

Two layers:
* the route with a mocked pool: the response shape, years as strings, undated counts, the scope echo and the
  missing-table case;
* the per-year SQL itself, run against temporary tables in a real Postgres (skipped when none is reachable), so the
  running totals by phase are checked as counts, not as SQL text.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import data_center_sites_timeline as tl
from api.routes import recorded_coverage as cov
from api.routes.data_centers import JobClaimScope


class _Conn:
    def __init__(self, sites=None, undated=None, years=None, row=None, error: Exception | None = None):
        self.sites, self.undated, self.years, self.row, self.error = sites or [], undated or [], years or [], row, error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        if "generate_series" in sql:
            return self.years
        if "appear_basis IN" in sql and "generate_series" not in sql:
            return self.undated
        return self.sites

    async def fetchrow(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
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


def _call(monkeypatch, module, path: str, conn: _Conn, params: dict[str, Any] | None = None) -> httpx.Response:
    async def pool():
        return _Pool(conn)

    monkeypatch.setattr(module, "get_db_pool", pool)
    app = FastAPI()
    app.include_router(module.router, prefix="/api")

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(path, params=params)

    return asyncio.run(go())


def _site(**kw) -> dict[str, Any]:
    base: dict[str, Any] = {
        "data_center_site_id": "a", "site_name": "Site A", "operator": "Op", "owner": None, "status": "operating",
        "source": "us_data_center_registry", "source_name": "US Data Center Registry (SueDataCenters.org)",
        "source_url": "https://suedatacenters.org/data-centers/a", "state_code": "VA", "latitude": 38.9, "longitude": -77.4,
        "appear_year": 2019, "appear_basis": "announced", "appear_precision": "month", "listed_on": None,
        "first_report_year": None,
        "operating_year": None, "operating_is_expected": False, "capacity_mw_operational": 48.0,
        "capacity_mw_planned": None, "it_power_mw": None,
    }
    base.update(kw)
    return base


def _year(year: int, **kw) -> dict[str, Any]:
    base = {"year": year, "planned": 0, "under_construction": 0, "operating": 0, "cancelled": 0, "no_longer_listed": 0,
            "status_not_published": 0, "total": 0, "undated": 0, "is_future": False}
    base.update(kw)
    return base


def test_timeline_shape_years_as_strings_and_undated(monkeypatch):
    conn = _Conn(
        sites=[
            _site(),
            _site(data_center_site_id="b", site_name="Site B", latitude=None, longitude=None, appear_year=2021,
                  appear_basis="epoch_first_report", appear_precision="day"),
            _site(data_center_site_id="c", site_name="Site C", appear_year=2021, appear_basis="listed_by",
                  appear_precision="listed_by", listed_on="2021-07-16"),
            _site(data_center_site_id="d", site_name="Site D", appear_year=None, appear_basis="none", appear_precision=None),
        ],
        undated=[{"status": "operating", "n": 1}, {"status": "planned", "n": 1}],
        years=[_year(2019, operating=1, total=1), _year(2020, operating=1, total=1),
               _year(2021, operating=4, total=4, undated=2)],
    )
    r = _call(monkeypatch, tl, "/api/data-centers/sites-timeline", conn, {"state": "va", "city": "Ashburn"})
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["scope"]["level"] == "state" and body["scope"]["state_code"] == "VA"
    assert body["city_applied"] is False
    assert body["first_year"] == "2019" and body["last_year"] == "2021"
    assert isinstance(body["current_year"], str) and len(body["current_year"]) == 4
    assert body["sites"][0]["appear_year"] == "2019"
    assert body["years"][2] == {**_year(2021, operating=4, total=4, undated=2), "year": "2021"}
    # every site comes back, dated or not (#1428); the none site has no year, never a guess
    assert [s["appear_basis"] for s in body["sites"]] == ["announced", "epoch_first_report", "listed_by", "none"]
    assert body["sites"][3]["appear_year"] is None and body["sites"][2]["listed_on"] == "2021-07-16"
    assert (body["total"], body["dated"], body["undated"], body["unplaced"]) == (4, 2, 2, 1)
    assert (body["mapped"], body["not_mapped"]) == (3, 1)
    assert body["listed_year"] == "2021"
    assert body["by_basis"] == {"announced": 1, "epoch_first_report": 1, "listed_by": 1, "none": 1}
    assert body["undated_by_status"] == {"operating": 1, "planned": 1}
    # the state is bound, never inlined; the city never narrows sites
    assert all("'VA'" not in sql and "Ashburn" not in sql for sql, _ in conn.calls)
    assert all(params[-1] == "VA" for _, params in conn.calls)


def test_timeline_national_and_missing_table(monkeypatch):
    r = _call(monkeypatch, tl, "/api/data-centers/sites-timeline", _Conn())
    assert r.json()["scope"]["level"] == "national" and r.json()["years"] == [] and r.json()["first_year"] is None
    r = _call(monkeypatch, tl, "/api/data-centers/sites-timeline", _Conn(error=asyncpg.exceptions.UndefinedTableError("x")))
    assert r.status_code == 200 and r.json()["available"] is False and r.json()["sites"] == []


def test_coverage_counts_and_scope(monkeypatch):
    conn = _Conn(row={"governments": 29, "meetings": 1035, "states": 1})
    r = _call(monkeypatch, cov, "/api/coverage/recorded-meetings", conn, {"state": "FL"})
    assert r.json() == {
        "scope": {"level": "state", "state_code": "FL", "state": "Florida", "city": None, "jurisdiction_id": None},
        "available": True, "governments": 29, "meetings": 1035, "states": 1,
    }
    conn = _Conn(row={"governments": 2, "meetings": 300, "states": 1})
    r = _call(monkeypatch, cov, "/api/coverage/recorded-meetings", conn, {"state": "AL", "city": "Tuscaloosa"})
    assert r.json()["scope"]["level"] == "city"
    assert conn.calls[0][1] == ("AL", "%Tuscaloosa%")
    # a city without a state is national
    conn = _Conn(row={"governments": 2061, "meetings": 137661, "states": 40})
    r = _call(monkeypatch, cov, "/api/coverage/recorded-meetings", conn, {"city": "Tuscaloosa"})
    assert r.json()["scope"]["level"] == "national" and conn.calls[0][1] == ()


def test_coverage_missing_table_is_null_not_zero(monkeypatch):
    r = _call(monkeypatch, cov, "/api/coverage/recorded-meetings", _Conn(error=asyncpg.exceptions.UndefinedTableError("x")))
    assert r.json()["available"] is False and r.json()["governments"] is None and r.json()["meetings"] is None


# --- the per-year SQL, against a real Postgres ------------------------------------------------------------------------

# The local warehouse by its parts (no connection string in the source); TEST_WAREHOUSE_HOST etc. override.
PG = {
    "host": os.getenv("TEST_WAREHOUSE_HOST", "localhost"),
    "port": int(os.getenv("TEST_WAREHOUSE_PORT", "5433")),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "database": os.getenv("TEST_WAREHOUSE_DB", "open_navigator"),
}

FIXTURE = [
    # id, source, status today, state, appear, basis, first_report, operating
    ("e1", "epoch", "operating", "VA", 2020, "epoch_first_report", 2020, 2022),  # building 2020-21, operating 2022+
    ("e2", "epoch", "under_construction", "VA", 2024, "announced", 2025, 2028),  # announced 2024, work 2025, exp. 2028
    ("r1", "us_data_center_registry", "operating", "VA", 2021, "announced", None, None),
    ("r2", "us_data_center_registry", "cancelled", "VA", 2023, "announced", None, None),
    ("r3", "us_data_center_registry", "planned", "VA", None, "none", None, None),  # no date at all: enters at today
    ("r5", "us_data_center_registry", "operating", "VA", 2026, "listed_by", None, None),  # listed by 2026
    ("r4", "us_data_center_registry", "planned", "TX", 2019, "announced", None, None),  # another state
]


async def _years(scope: JobClaimScope, current_year: int) -> list[dict[str, Any]]:
    try:
        conn = await asyncpg.connect(**PG, timeout=3)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no Postgres for the SQL check ({e})")
    try:
        async with conn.transaction():
            await conn.execute(
                "CREATE TEMP TABLE data_center_site (data_center_site_id text, status text, source text) ON COMMIT DROP;"
                "CREATE TEMP TABLE data_center_site_timeline (data_center_site_id text, state_code text, appear_year int, "
                "appear_basis text, first_report_year int, operating_year int) ON COMMIT DROP;"
            )
            for sid, src, status, st, appear, basis, first, oper in FIXTURE:
                await conn.execute("INSERT INTO data_center_site VALUES ($1, $2, $3)", sid, status, src)
                await conn.execute(
                    "INSERT INTO data_center_site_timeline VALUES ($1, $2, $3, $4, $5, $6)", sid, st, appear, basis, first, oper
                )
            sql, params = tl.build_years_sql(scope, current_year)
            return [dict(r) for r in await conn.fetch(sql, *params)]
    finally:
        await conn.close()


def test_years_sql_running_totals_by_phase():
    rows = asyncio.run(_years(JobClaimScope(level="state", state_code="VA", state="Virginia"), 2026))
    got = {r["year"]: (r["planned"], r["under_construction"], r["operating"], r["cancelled"], r["total"], r["is_future"]) for r in rows}
    undated = {r["year"]: r["undated"] for r in rows}
    assert list(got) == list(range(2020, 2029))  # first appearance to the last expected operating year
    assert got[2020] == (0, 1, 0, 0, 1, False)
    assert got[2021] == (0, 1, 1, 0, 2, False)   # r1 appears with its status today
    assert got[2022] == (0, 0, 2, 0, 2, False)   # e1 turns operating
    assert got[2023] == (0, 0, 2, 1, 3, False)   # r2 appears, cancelled today
    assert got[2024] == (1, 0, 2, 1, 4, False)   # e2 announced: planned before Epoch's first dated row
    assert got[2025] == (0, 1, 2, 1, 4, False)
    assert got[2026] == (1, 1, 3, 1, 6, False)   # today: r5 (listed by 2026) and r3 (no date) join; every VA site
    assert got[2027] == (1, 1, 3, 1, 6, True)
    assert got[2028] == (1, 0, 4, 1, 6, True)    # Epoch's expected opening
    assert undated[2025] == 0 and undated[2026] == 2 and undated[2028] == 2


def test_years_sql_national_and_no_future():
    rows = asyncio.run(_years(JobClaimScope(level="national"), 2030))
    assert rows[0]["year"] == 2019 and rows[-1]["year"] == 2030  # runs to this year when nothing is expected later
    assert rows[-1]["total"] == 7 and not any(r["is_future"] for r in rows)


# --- the route's SQL against the real mart (public.data_center_site_timeline) ----------------------------------------


async def _mart_check(state_code: str | None) -> tuple[list[dict[str, Any]], dict[str, int], int]:
    try:
        conn = await asyncpg.connect(**PG, timeout=3)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no Postgres for the mart check ({e})")
    try:
        await conn.execute("SET search_path TO public")
        try:
            await conn.fetchval("SELECT appear_basis FROM data_center_site_timeline LIMIT 1")
        except asyncpg.exceptions.PostgresError as e:
            pytest.skip(f"data_center_site_timeline with appear_basis not built here ({e})")
        scope = (
            JobClaimScope(level="state", state_code=state_code, state=state_code) if state_code else JobClaimScope(level="national")
        )
        current = await conn.fetchval("SELECT extract(year from current_date)::int")
        sql, params = tl.build_years_sql(scope, current)
        years = [dict(r) for r in await conn.fetch(sql, *params)]
        where, args = ("WHERE state_code = $1", [state_code]) if state_code else ("", [])
        counts = dict(
            await conn.fetchrow(
                "SELECT count(*)::int AS total, count(*) FILTER (WHERE latitude IS NOT NULL AND longitude IS NOT NULL)::int AS mapped, "
                "count(*) FILTER (WHERE appear_basis IN ('listed_by', 'none'))::int AS undated "
                f"FROM data_center_site_timeline {where}",
                *args,
            )
        )
        by_year = {
            r["y"]: r["n"]
            for r in await conn.fetch(
                f"SELECT coalesce(appear_year, $1::int) AS y, count(*)::int AS n FROM data_center_site_timeline "
                f"{where.replace('$1', '$2')} GROUP BY 1",
                current, *args,
            )
        }
        sites_sql, sites_params = tl.build_sites_sql(scope)
        sites = await conn.fetch(sites_sql, *sites_params)
        mapped_sites = sum(1 for s in sites if s["latitude"] is not None and s["longitude"] is not None)
        return years, {**counts, "by_year": by_year, "sites": len(sites), "mapped_sites": mapped_sites}, current  # type: ignore[dict-item]
    finally:
        await conn.close()


@pytest.mark.parametrize("state_code", [None, "FL"])
def test_years_and_today_frame_match_the_mart(state_code):
    years, mart, current = asyncio.run(_mart_check(state_code))
    rows = {r["year"]: r for r in years}
    # each year's total is the running count of sites that have appeared by then (none sites enter at today)
    running = 0
    for y in sorted(rows):
        running += mart["by_year"].get(y, 0)
        assert rows[y]["total"] == running, y
        assert rows[y]["total"] == sum(rows[y][p] for p in tl.PHASES), y
    # today's frame holds every site in scope; the route returns them all, and the mapped ones are the mart's mapped
    today = rows[current]
    assert today["total"] == mart["total"] == mart["sites"]
    assert today["undated"] == mart["undated"]
    assert mart["mapped_sites"] == mart["mapped"]
