"""GET /api/meeting/{event_meeting_id} carries how the summary was made (#1099)."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx
from fastapi import FastAPI

from api.routes import meetings as m

MEETING = {
    "event_meeting_id": 7, "c1_event_id": "c1-7", "body_name": "City Council", "jurisdiction_name": "Tuscaloosa",
    "jurisdiction_type": "city", "state": "Alabama", "state_code": "AL", "meeting_date": "2026-11-10",
    "video_id": "abc123", "meeting_type": None,
}
PROV = {
    "video_id": "abc123", "ai_model": "gemini-2.5-flash-lite", "generated_at": datetime(2026, 11, 11, 9, 30),
    "analysis_tier": "full", "prompt_name": "policy_analysis_part_1", "prompt_sha": "a1b2c3",
    "transcript_source": "youtube_captions", "analyses_for_meeting": 1,
}


class _Conn:
    def __init__(self, prov: dict | None, prov_error: bool = False):
        self.prov, self.prov_error = prov, prov_error

    async def fetchrow(self, sql: str, *params: Any):
        if "event_analysis_provenance" in sql:
            if self.prov_error:
                raise RuntimeError("relation event_analysis_provenance does not exist")
            return self.prov
        return MEETING

    async def fetch(self, sql: str, *params: Any):
        return []


class _Acq:
    def __init__(self, c):
        self.c = c

    async def __aenter__(self):
        return self.c

    async def __aexit__(self, *a):
        return False


class _Pool:
    def __init__(self, c):
        self.c = c

    def acquire(self):
        return _Acq(self.c)


def _get(monkeypatch, conn: _Conn) -> httpx.Response:
    async def pool():
        return _Pool(conn)

    async def no_type(_conn):
        return False

    monkeypatch.setattr(m, "get_db_pool", pool)
    monkeypatch.setattr(m, "meeting_type_available", no_type)
    monkeypatch.setattr(m, "meeting_type_by_video_sql", lambda *_a, **_k: "NULL::text AS meeting_type")
    app = FastAPI()
    app.include_router(m.router, prefix="/api")

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get("/api/meeting/7")

    return asyncio.run(go())


def test_meeting_carries_its_recorded_provenance(monkeypatch) -> None:
    body = _get(monkeypatch, _Conn(PROV)).json()
    p = body["provenance"]
    assert p["model"] == "gemini-2.5-flash-lite"
    assert p["prompt_name"] == "policy_analysis_part_1" and p["prompt_version"] == "a1b2c3"
    assert p["tier"] == "full" and p["analyses_for_meeting"] == 1
    assert p["video_url"] == "https://www.youtube.com/watch?v=abc123"


def test_missing_provenance_never_fails_the_meeting(monkeypatch) -> None:
    r = _get(monkeypatch, _Conn(None, prov_error=True))
    assert r.status_code == 200
    p = r.json()["provenance"]
    # Only the recording link is known; nothing else is filled in.
    assert p is None or (p.get("model") is None and p.get("prompt_name") is None)
