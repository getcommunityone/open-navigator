"""Offline unit tests for GET /api/opportunities deterministic coordinate resolution."""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import httpx
import pytest


class _FakeConn:
    def __init__(self, rows: list[dict[str, Any]], *, fail_join_query: bool = False):
        self._rows = rows
        self._fail_join_query = fail_join_query
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.calls.append((query, args))
        if self._fail_join_query and "LEFT JOIN jurisdictions" in query:
            raise RuntimeError("relation 'jurisdictions' does not exist")
        return list(self._rows)


class _FakeAcquireCtx:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


class _FakePool:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    def acquire(self) -> _FakeAcquireCtx:
        return _FakeAcquireCtx(self._conn)


def _request_opportunities(params: dict[str, Any] | None = None) -> httpx.Response:
    from api.main import app

    async def _run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            return await client.get("/api/opportunities", params=params)

    return asyncio.run(_run())


def test_opportunities_returns_empty_when_pool_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    import api.routes.bills_neon as bills_neon

    async def _no_pool():
        return None

    monkeypatch.setattr(bills_neon, "get_pool", _no_pool)
    resp = _request_opportunities()
    assert resp.status_code == 200
    assert resp.json() == {"opportunities": [], "total": 0}


def test_opportunities_emits_deterministic_coordinates_without_random_jitter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.routes.bills_neon as bills_neon
    from api.main import STATE_COORDS

    sample_rows = [
        {
            "state_code": "AL",
            "title": "Public Water Fluoridation Standards Act",
            "identifier": "HB 101",
            "session_identifier": "2026RS",
            "latest_action_description": "Referred to Health Committee",
            "latest_action_date": date(2026, 3, 15),
            "jurisdiction_latitude": None,
            "jurisdiction_longitude": None,
        },
        {
            "state_code": "MA",
            "title": "School Dental Screening Modernization",
            "identifier": "SB 202",
            "session_identifier": "194th",
            "latest_action_description": "Reported favorably",
            "latest_action_date": date(2026, 4, 2),
            "jurisdiction_latitude": 42.35843,
            "jurisdiction_longitude": -71.05977,
        },
    ]
    conn = _FakeConn(sample_rows)
    pool = _FakePool(conn)

    async def _fake_get_pool():
        return pool

    monkeypatch.setattr(bills_neon, "get_pool", _fake_get_pool)

    first = _request_opportunities().json()
    second = _request_opportunities().json()

    # Repeated requests must be strictly identical (no random.uniform offset).
    assert first == second
    assert first["total"] == 2
    opps = first["opportunities"]
    assert len(opps) == 2

    # Row 1 falls back to canonical STATE_COORDS["AL"] with zero jitter.
    al_lat, al_lon = STATE_COORDS["AL"]
    assert opps[0]["state"] == "AL"
    assert opps[0]["latitude"] == pytest.approx(al_lat)
    assert opps[0]["longitude"] == pytest.approx(al_lon)
    assert opps[0]["topic"] == "water_fluoridation"
    assert opps[0]["urgency"] == "critical"
    assert opps[0]["bill_id"] == "HB 101"
    assert opps[0]["meeting_date"] == "2026-03-15"

    # Row 2 uses exact jurisdiction coordinates from the joined jurisdictions row.
    assert opps[1]["state"] == "MA"
    assert opps[1]["latitude"] == pytest.approx(42.35843)
    assert opps[1]["longitude"] == pytest.approx(-71.05977)
    assert opps[1]["topic"] == "school_dental_screening"
    assert opps[1]["urgency"] == "high"


def test_opportunities_falls_back_when_jurisdictions_table_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.routes.bills_neon as bills_neon
    from api.main import STATE_COORDS

    sample_rows = [
        {
            "state_code": "CA",
            "title": "Oral Health Medicaid Expansion",
            "identifier": "AB 55",
            "session_identifier": "2025-2026",
            "latest_action_description": "Introduced",
            "latest_action_date": date(2026, 2, 1),
        }
    ]
    conn = _FakeConn(sample_rows, fail_join_query=True)
    pool = _FakePool(conn)

    async def _fake_get_pool():
        return pool

    monkeypatch.setattr(bills_neon, "get_pool", _fake_get_pool)

    resp = _request_opportunities({"state": "ca"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    opp = body["opportunities"][0]
    ca_lat, ca_lon = STATE_COORDS["CA"]
    assert opp["state"] == "CA"
    assert opp["latitude"] == pytest.approx(ca_lat)
    assert opp["longitude"] == pytest.approx(ca_lon)
    assert opp["topic"] == "medicaid_dental_expansion"
    assert opp["urgency"] == "medium"
    assert len(conn.calls) == 2


def test_opportunities_filters_by_topic_alias_and_urgency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.routes.bills_neon as bills_neon

    sample_rows = [
        {
            "state_code": "GA",
            "title": "Community Water Fluoridation Act",
            "identifier": "HB 10",
            "session_identifier": "2026",
            "latest_action_description": "Passed House",
            "latest_action_date": date(2026, 3, 1),
        },
        {
            "state_code": "GA",
            "title": "Pediatric Dental Screening Requirement",
            "identifier": "HB 11",
            "session_identifier": "2026",
            "latest_action_description": "Introduced",
            "latest_action_date": date(2026, 3, 2),
        },
    ]
    conn = _FakeConn(sample_rows)
    pool = _FakePool(conn)

    async def _fake_get_pool():
        return pool

    monkeypatch.setattr(bills_neon, "get_pool", _fake_get_pool)

    # Alias 'fluoride' maps to 'water_fluoridation'
    resp = _request_opportunities({"state": "GA", "topic": "fluoride"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["opportunities"][0]["bill_id"] == "HB 10"

    # Urgency filter 'high' selects dental screening bill
    resp_high = _request_opportunities({"state": "GA", "urgency": "high"})
    assert resp_high.status_code == 200
    body_high = resp_high.json()
    assert body_high["total"] == 1
    assert body_high["opportunities"][0]["bill_id"] == "HB 11"


def test_opportunities_invalid_state_and_limit_validation() -> None:
    resp_unknown = _request_opportunities({"state": "ZZ"})
    assert resp_unknown.status_code == 200
    assert resp_unknown.json() == {"opportunities": [], "total": 0}

    resp_bad_limit = _request_opportunities({"limit": 0})
    assert resp_bad_limit.status_code == 422
