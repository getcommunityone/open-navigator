"""GET /api/data-centers/job-claims (#246, DC-1.1): jobs claims split by phase.

The DB layer is mocked (no live database): ``get_db_pool`` is patched with a fake
pool whose connection records the SQL and params and returns canned rows.
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

PATH = "/api/data-centers/job-claims"


class _FakeConn:
    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        error: Exception | None = None,
        totals: list[dict[str, Any]] | None = None,
    ):
        self.rows = rows or []
        self.totals = totals or []
        self.error = error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error is not None:
            raise self.error
        return self.totals if "GROUP BY phase" in sql else self.rows


class _Acquire:
    def __init__(self, conn: _FakeConn):
        self.conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self.conn

    async def __aexit__(self, *_exc: object) -> None:
        return None


class _FakePool:
    def __init__(self, conn: _FakeConn):
        self.conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self.conn)


class _Client:
    """Sync wrapper over httpx.ASGITransport (the repo's in-process pattern)."""

    def __init__(self, app: FastAPI):
        self.app = app

    def get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        async def go() -> httpx.Response:
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                return await client.get(path, params=params)

        return asyncio.run(go())


@pytest.fixture
def make_client(monkeypatch):
    def _make(conn: _FakeConn) -> _Client:
        async def _get_pool():
            return _FakePool(conn)

        monkeypatch.setattr(data_centers, "get_db_pool", _get_pool)
        app = FastAPI()
        app.include_router(data_centers.router, prefix="/api")
        return _Client(app)

    return _make


def _row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "job_claim_id": "jc-1",
        "phase": "construction",
        "headcount_low": None,
        "headcount_high": None,
        "starts_on": None,
        "ends_on": None,
        "project_name": None,
        "quote": "This will bring jobs.",
        "speaker_name": None,
        "speaker_role": None,
        "person_id": None,
        "event_meeting_id": 9,
        "meeting_date": date(2026, 3, 2),
        "body_name": None,
        "video_id": "vid123",
        "start_seconds": 754.5,
    }
    base.update(overrides)
    return base


# --- query building -----------------------------------------------------------


def test_national_query_only_filters_project_type() -> None:
    scope = data_centers.build_scope(None, None, None)
    sql, params = data_centers.build_job_claims_query(scope, 100)
    assert scope.level == "national"
    assert "FROM job_claim" in sql
    assert "project_type = 'data_center'" in sql
    assert "state_code =" not in sql and "jurisdiction_name ILIKE" not in sql
    assert "jurisdiction_id =" not in sql
    assert "ORDER BY meeting_date DESC NULLS LAST, start_seconds" in sql
    assert "LIMIT $1" in sql
    assert params == [100]


def test_all_filters_bind_params_in_order() -> None:
    scope = data_centers.build_scope(" al ", "  Tuscaloosa ", "ocd-jurisdiction/x")
    sql, params = data_centers.build_job_claims_query(scope, 25)
    assert "state_code = $1" in sql
    assert "(city ILIKE $2 OR jurisdiction_name ILIKE $2)" in sql
    assert "jurisdiction_id = $3" in sql
    assert "LIMIT $4" in sql
    assert params == ["AL", "%Tuscaloosa%", "ocd-jurisdiction/x", 25]
    # Values are bound, never inlined.
    assert "Tuscaloosa" not in sql and "'AL'" not in sql


def test_city_only_uses_first_placeholder() -> None:
    sql, params = data_centers.build_job_claims_query(
        data_centers.build_scope(None, "Mobile", None), 10
    )
    assert "(city ILIKE $1 OR jurisdiction_name ILIKE $1)" in sql
    assert params == ["%Mobile%", 10]


def test_totals_query_uses_the_same_scope_without_a_limit() -> None:
    scope = data_centers.build_scope("AL", "Mobile", None)
    sql, params = data_centers.build_job_claims_totals_query(scope)
    assert "GROUP BY phase" in sql and "LIMIT" not in sql
    assert "project_type = 'data_center'" in sql and "state_code = $1" in sql
    assert params == ["AL", "%Mobile%"]


# --- scope echo ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (
            (None, None, None),
            {
                "level": "national",
                "state_code": None,
                "state": None,
                "city": None,
                "jurisdiction_id": None,
            },
        ),
        (
            ("al", None, None),
            {
                "level": "state",
                "state_code": "AL",
                "state": "Alabama",
                "city": None,
                "jurisdiction_id": None,
            },
        ),
        (
            ("Alabama", None, None),
            {
                "level": "state",
                "state_code": "AL",
                "state": "Alabama",
                "city": None,
                "jurisdiction_id": None,
            },
        ),
        (
            ("AL", "Tuscaloosa", None),
            {
                "level": "city",
                "state_code": "AL",
                "state": "Alabama",
                "city": "Tuscaloosa",
                "jurisdiction_id": None,
            },
        ),
        (
            (None, None, "j-1"),
            {
                "level": "jurisdiction",
                "state_code": None,
                "state": None,
                "city": None,
                "jurisdiction_id": "j-1",
            },
        ),
        (
            ("  ", " ", ""),
            {
                "level": "national",
                "state_code": None,
                "state": None,
                "city": None,
                "jurisdiction_id": None,
            },
        ),
    ],
)
def test_scope_echo(args, expected) -> None:
    assert data_centers.build_scope(*args).model_dump() == expected


def test_route_echoes_scope_and_passes_params(make_client) -> None:
    conn = _FakeConn(rows=[])
    resp = make_client(conn).get(PATH, params={"state": "al", "city": "tuscaloosa"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope"] == {
        "level": "city",
        "state_code": "AL",
        "state": "Alabama",
        "city": "tuscaloosa",
        "jurisdiction_id": None,
    }
    assert body["items"] == []
    assert body["totals"] == {"construction": 0, "operations": 0}
    (_sql, params), (_totals_sql, totals_params) = conn.calls
    assert params == ("AL", "%tuscaloosa%", 100)
    assert totals_params == ("AL", "%tuscaloosa%")


def test_totals_count_the_whole_scope_not_just_the_page(make_client) -> None:
    conn = _FakeConn(
        rows=[_row()],
        totals=[
            {"phase": "construction", "claim_count": 140},
            {"phase": "operations", "claim_count": 3},
        ],
    )
    body = make_client(conn).get(PATH, params={"limit": 1}).json()
    assert len(body["items"]) == 1
    assert body["totals"] == {"construction": 140, "operations": 3}


# --- null handling / serialization --------------------------------------------


def test_unknown_values_stay_null_and_dates_are_iso(make_client) -> None:
    rows = [
        _row(),
        _row(
            job_claim_id="jc-2",
            phase="operations",
            headcount_low=40,
            headcount_high=60,
            starts_on=date(2027, 1, 1),
            ends_on=date(2028, 6, 30),
            project_name="Project Blue",
            speaker_name="A. Speaker",
            person_id="p-1",
            start_seconds=None,
        ),
    ]
    resp = make_client(_FakeConn(rows=rows)).get(PATH)
    assert resp.status_code == 200
    first, second = resp.json()["items"]
    for key in (
        "headcount_low",
        "headcount_high",
        "starts_on",
        "ends_on",
        "project_name",
        "speaker_name",
        "speaker_role",
        "person_id",
        "body_name",
    ):
        assert first[key] is None, key
    assert first["meeting_date"] == "2026-03-02"
    assert first["start_seconds"] == 754.5
    assert second["phase"] == "operations"
    assert second["headcount_low"] == 40 and second["headcount_high"] == 60
    assert second["starts_on"] == "2027-01-01" and second["ends_on"] == "2028-06-30"
    assert second["start_seconds"] is None
    assert set(first) == {
        "job_claim_id",
        "phase",
        "headcount_low",
        "headcount_high",
        "starts_on",
        "ends_on",
        "project_name",
        "quote",
        "speaker_name",
        "speaker_role",
        "person_id",
        "event_meeting_id",
        "meeting_date",
        "body_name",
        "video_id",
        "start_seconds",
    }


def test_claim_names_speaker_role_and_meeting_body(make_client) -> None:
    """DC-1.2 (#247): who said it, in what role, at which body's meeting, and when."""
    rows = [
        _row(
            speaker_name="Dana Ruiz",
            speaker_role="applicant",
            body_name="Tuscaloosa City Council",
            start_seconds=754.0,
        )
    ]
    resp = make_client(_FakeConn(rows=rows)).get(PATH)
    assert resp.status_code == 200
    (item,) = resp.json()["items"]
    assert item["speaker_name"] == "Dana Ruiz"
    assert item["speaker_role"] == "applicant"
    assert item["body_name"] == "Tuscaloosa City Council"
    assert item["event_meeting_id"] == 9
    assert item["meeting_date"] == "2026-03-02"
    assert item["start_seconds"] == 754.0


def test_select_reads_the_attribution_columns() -> None:
    from api.routes.data_centers import build_job_claims_query, build_scope

    sql, _ = build_job_claims_query(build_scope(None, None, None), 10)
    assert "speaker_role" in sql and "body_name" in sql


# --- missing relation / errors ------------------------------------------------


def test_missing_relation_returns_empty_items_with_scope(make_client) -> None:
    conn = _FakeConn(
        error=asyncpg.exceptions.UndefinedTableError(
            'relation "job_claim" does not exist'
        )
    )
    resp = make_client(conn).get(PATH, params={"jurisdiction_id": "j-1"})
    assert resp.status_code == 200
    assert resp.json() == {
        "scope": {
            "level": "jurisdiction",
            "state_code": None,
            "state": None,
            "city": None,
            "jurisdiction_id": "j-1",
        },
        "totals": {"construction": 0, "operations": 0},
        "items": [],
    }


def test_other_db_errors_are_500(make_client) -> None:
    resp = make_client(_FakeConn(error=ConnectionError("network blip"))).get(PATH)
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Failed to load job claims"


# --- limit bounds ---------------------------------------------------------------


@pytest.mark.parametrize("limit", [0, -1, 501])
def test_limit_out_of_bounds_is_422(make_client, limit) -> None:
    conn = _FakeConn()
    resp = make_client(conn).get(PATH, params={"limit": limit})
    assert resp.status_code == 422
    assert conn.calls == []


@pytest.mark.parametrize("limit", [1, 500])
def test_limit_edges_are_accepted(make_client, limit) -> None:
    conn = _FakeConn()
    resp = make_client(conn).get(PATH, params={"limit": limit})
    assert resp.status_code == 200
    assert conn.calls[0][1][-1] == limit
