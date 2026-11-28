"""Who governs a place (#1445): GET /api/jurisdictions/{id}/bodies and GET /api/bodies/{id}, with a fake pool.

Rows are shaped like public.governing_body / body_membership / body_recent_speaker / meeting_body (Tuscaloosa
examples from the local warehouse); no database is touched.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

import api.routes.governing_bodies as gb

JUR = {"jurisdiction_id": "tuscaloosa_0177256", "name": "Tuscaloosa", "state_code": "AL", "state_name": "Alabama"}
COUNCIL = {
    "governing_body_id": "g-council", "jurisdiction_id": "tuscaloosa_0177256", "body_name": "City Council",
    "body_type": "council", "is_primary": True, "meeting_count": 361,
    "first_meeting_date": date(2020, 1, 7), "last_meeting_date": date(2026, 11, 17),
}
PZ = {
    "governing_body_id": "g-pz", "jurisdiction_id": "tuscaloosa_0177256", "body_name": "Planning and Zoning Commission",
    "body_type": "planning_zoning", "is_primary": False, "meeting_count": 42,
    "first_meeting_date": date(2022, 2, 7), "last_meeting_date": date(2026, 11, 16),
}


def member(name, role, title, district=None, pid=None, current=True, end=None, body="g-council"):
    return {
        "body_membership_id": f"m-{name}-{role}", "governing_body_id": body, "person_id": pid, "member_name": name,
        "role": role, "role_title": title, "district": district, "start_date": None, "end_date": end,
        "is_current": current, "source": "officials",
    }


MEMBERS = [
    member("Lee Busby", "council_member", "City Councilor", "District 4", "p-busby"),
    member("Walt Maddox", "mayor", "Mayor", None, "p-maddox"),
    member("Raevan Howard", "council_member", "City Councilor", "District 2", "p-howard"),
    member("Raevan Howard", "president_pro_tem", "President Pro Tempore", "District 2", "p-howard"),
    member("Kip Tyner", "council_member", "City Councilor", "District 5", "p-tyner", current=False, end=date(2026, 9, 18)),
]
SPEAKERS = [
    {"governing_body_id": "g-council", "person_id": "p-maddox", "member_name": "Walt Maddox", "role": "mayor",
     "meetings_heard": 9, "last_heard_date": date(2026, 11, 17),
     "last_moment_url": "https://www.youtube.com/watch?v=abc&t=331s", "attribution_method": "chair_call"},
]
MEETINGS = [
    {"meeting_body_id": "mb1", "meeting_title": "Tuscaloosa City Council Meeting - Nov 17, 2026",
     "meeting_date": date(2026, 11, 17), "video_id": "abc", "video_url": "https://www.youtube.com/watch?v=abc",
     "event_meeting_id": None},
]


class FakeConn:
    def __init__(self, known: bool = True) -> None:
        self.known = known
        self.calls: list[str] = []

    async def fetchrow(self, sql, *args):
        self.calls.append(sql)
        if "FROM public.jurisdictions" in sql:
            return JUR if self.known and args[0] in ("tuscaloosa_0177256", "0177256") else None
        if "FROM public.governing_body g" in sql:
            return ({**COUNCIL, "jurisdiction_name": "Tuscaloosa", "state_code": "AL", "state_name": "Alabama"}
                    if args[0] == "g-council" else None)
        raise AssertionError(sql)

    async def fetch(self, sql, *args):
        self.calls.append(sql)
        if "FROM public.governing_body" in sql:
            return [COUNCIL, PZ] if self.known else []
        if "FROM public.body_membership" in sql:
            return [m for m in MEMBERS if m["governing_body_id"] in args[0]]
        if "FROM public.body_recent_speaker" in sql:
            return [s for s in SPEAKERS if s["governing_body_id"] in args[0]]
        if "FROM public.meeting_body" in sql:
            return MEETINGS[: args[1]]
        raise AssertionError(sql)


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self):
                return pool.conn

            async def __aexit__(self, *a):
                return False

        return _Ctx()


@pytest.fixture
def client(monkeypatch):
    conn = FakeConn()

    async def fake_pool():
        return FakePool(conn)

    monkeypatch.setattr(gb, "get_db_pool", fake_pool)
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(gb.router, prefix="/api")
    return TestClient(app)


def test_bodies_by_geoid(client):
    r = client.get("/api/jurisdictions/0177256/bodies")
    assert r.status_code == 200
    data = r.json()
    assert data["jurisdiction_id"] == "tuscaloosa_0177256" and data["jurisdiction_name"] == "Tuscaloosa"
    council, pz = data["bodies"]
    assert council["body_name"] == "City Council" and council["meeting_count"] == 361
    # Three current people (Howard's two roles count once); Tyner's ended seat is listed but not counted.
    assert council["member_count"] == 3
    names = [(m["member_name"], m["role"], m["is_current"]) for m in council["members"]]
    assert names[0] == ("Walt Maddox", "mayor", True)
    assert names[-1] == ("Kip Tyner", "council_member", False)
    assert council["recent_speakers"][0]["moment_url"].endswith("&t=331s")
    # A body with no members on file has none, not invented ones.
    assert pz["members"] == [] and pz["member_count"] == 0
    # Dates serialize as ISO strings.
    assert council["last_meeting_date"] == "2026-11-17"


def test_unknown_place_is_404(monkeypatch):
    conn = FakeConn(known=False)

    async def fake_pool():
        return FakePool(conn)

    monkeypatch.setattr(gb, "get_db_pool", fake_pool)
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(gb.router, prefix="/api")
    assert TestClient(app).get("/api/jurisdictions/nowhere/bodies").status_code == 404


def test_body_detail(client):
    r = client.get("/api/bodies/g-council?limit=5")
    assert r.status_code == 200
    data = r.json()
    assert data["body"]["jurisdiction_name"] == "Tuscaloosa" and data["body"]["state"] == "Alabama"
    assert data["body"]["member_count"] == 3
    assert data["meetings"][0]["meeting_date"] == "2026-11-17"
    assert client.get("/api/bodies/nope").status_code == 404
    assert client.get("/api/bodies/g-council?limit=0").status_code == 422


def test_sort_and_count_helpers():
    ordered = gb.sort_members(MEMBERS)
    assert [m.role for m in ordered][:2] == ["mayor", "president_pro_tem"]
    assert gb.member_count(MEMBERS) == 3


def test_routes_registered_on_the_app():
    from api.main import app

    paths = set(app.openapi()["paths"])
    assert "/api/jurisdictions/{jurisdiction_id}/bodies" in paths
    assert "/api/bodies/{governing_body_id}" in paths
