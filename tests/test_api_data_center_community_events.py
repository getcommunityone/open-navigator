"""GET /api/data-centers/community-events and /projects (#532).

The DB layer is mocked: ``get_db_pool`` returns a fake pool that records SQL and params and
returns canned rows by which relation the SQL reads.
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


class _Conn:
    def __init__(self, tables: dict[str, list[dict]] | None = None, error: Exception | None = None):
        self.tables = tables or {}
        self.error = error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        for key, rows in self.tables.items():
            if key in sql:
                return rows
        return []


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
    def _get(conn: _Conn, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        async def pool():
            return _Pool(conn)

        monkeypatch.setattr(data_centers, "get_db_pool", pool)
        app = FastAPI()
        app.include_router(data_centers.router, prefix="/api")

        async def run():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
                return await client.get(path, params=params or {})

        return asyncio.run(run())

    return _get


EVENT = {
    "community_event_id": "e1",
    "master_org_id": "m1",
    "host_name": "Applied Digital",
    "project_id": "p1",
    "project_name": "Delta Forge 2",
    "jurisdiction_id": "brookwood_0109808",
    "city": "Brookwood",
    "state_code": "AL",
    "state": "Alabama",
    "event_kind": "town_hall",
    "event_date": date(2026, 10, 6),
    "event_date_basis": "stated_month_day",
    "recording_url": None,
    "title": "Applied Digital to hold town hall in Brookwood",
    "first_reported_on": date(2026, 10, 1),
}
SOURCE = {
    "community_event_id": "e1",
    "url": "https://example.com/a",
    "title": "Applied Digital to hold town hall in Brookwood",
    "publisher": "example.com",
    "published_on": date(2026, 10, 1),
    "source": "gdelt",
    "evidence": "Applied Digital to hold <mark>town hall</mark> in Brookwood",
}


def test_community_events_confirmed_only_with_sources(get) -> None:
    conn = _Conn({
        "FROM data_center_community_event_source": [SOURCE],
        "status = 'unconfirmed'": [{"n": 2}],
        "FROM data_center_community_event e": [EVENT],
    })
    r = get(conn, "/api/data-centers/community-events", {"state": "Alabama", "city": "Brookwood"})
    assert r.status_code == 200
    body = r.json()
    assert body["scope"]["state_code"] == "AL" and body["scope"]["city"] == "Brookwood"
    assert body["unconfirmed"] == 2
    item = body["items"][0]
    assert item["host_type"] == "company"
    assert item["sources"][0]["evidence"].count("<mark>") == 1
    events_sql, params = conn.calls[0]
    assert "e.status = 'confirmed'" in events_sql
    assert params[:2] == ("AL", "%Brookwood%")


def test_community_events_missing_relation_is_empty(get) -> None:
    conn = _Conn(error=asyncpg.exceptions.UndefinedTableError("nope"))
    r = get(conn, "/api/data-centers/community-events")
    assert r.status_code == 200
    assert r.json()["items"] == [] and r.json()["scope"]["level"] == "national"


PROJECT = {
    "project_id": "p1",
    "project_name": "Delta Forge 2",
    "project_source": "curated",
    "data_center_site_id": None,
    "area": "Alabama",
    "city": None,
    "county": None,
    "state_code": "AL",
    "state": "Alabama",
    "jurisdiction_id": None,
    "status": None,
    "announced_on": date(2026, 6, 8),
    "announced_source_url": "https://ir.example.com/154",
    "announced_source_excerpt": "DALLAS, June 08, 2026 -- today announced",
    "has_conflicting_figures": False,
    "source_kind": "company_announcement",
    "source_url": "https://ir.example.com/163",
    "source_excerpt": "Delta Forge 2 in Alabama",
}


def test_projects_timeline_orders_and_labels_hosts(get) -> None:
    conn = _Conn({
        "FROM data_center_project_company": [{
            "project_id": "p1", "master_org_id": "m1", "company_name": "Applied Digital", "role": "developer",
            "confidence": "stated", "source_url": "https://ir.example.com/154", "source_excerpt": "x"}],
        "FROM data_center_project_figure": [{
            "project_id": "p1", "metric": "it_mw", "value": 210.0, "unit": "mw",
            "source_url": "https://ir.example.com/154", "source_excerpt": "210 MW of critical IT load",
            "published_on": date(2026, 6, 8)}],
        "FROM data_center_community_event e": [{
            "project_id": "p1", "community_event_id": "e1", "host_name": "Applied Digital",
            "event_kind": "town_hall", "event_date": date(2026, 10, 6), "first_reported_on": date(2026, 10, 1),
            "title": "t", "url": "https://example.com/a", "publisher": "example.com", "evidence": "<mark>town hall</mark>"}],
        "FROM data_center_project_mention": [{
            "project_id": "p1", "record_type": "decision", "evidence": "e", "event_decision_id": "d1",
            "meeting_date": None, "meeting_title": None, "jurisdiction_name": None, "video_url": None,
            "headline": "Council approves rezoning", "decision_jurisdiction": "Brookwood",
            "is_planning": True, "is_vote": True}],
        "count(*)::int AS n FROM data_center_project": [{"n": 1}],
        "FROM data_center_project p": [PROJECT],
    })
    r = get(conn, "/api/data-centers/projects", {"state": "AL", "source": "curated"})
    assert r.status_code == 200
    p = r.json()["items"][0]
    stages = [t["stage"] for t in p["timeline"]]
    assert stages == ["announced", "company_meeting", "vote"]
    assert "company-hosted" in p["timeline"][1]["host"]
    assert p["timeline"][2]["on"] is None
    assert p["figures"][0]["value"] == 210.0
    assert p["timeline"][0]["url"] == "https://ir.example.com/154"  # the passage that dates it
