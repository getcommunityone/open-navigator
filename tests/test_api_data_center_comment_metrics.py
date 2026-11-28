"""GET /api/data-centers/comment-metrics (#1233): comment-level numbers from our own captions."""

from __future__ import annotations

import asyncio
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import data_center_comments as dcc

PATH = "/api/data-centers/comment-metrics"


class _Conn:
    def __init__(self, rows: dict[str, list[dict[str, Any]]] | None = None, error: Exception | None = None):
        self.rows, self.error = rows or {}, error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        # Count the $n placeholders: every query gets exactly the params it names.
        import re

        assert len(set(re.findall(r"\$(\d+)", sql))) == len(params), sql
        if "FROM segmented_meeting" in sql:
            return self.rows.get("segmented", [])
        if "data_center_meeting_mention" in sql:
            return self.rows.get("quarters", [])
        if "FROM meeting_speaker_position p WHERE p.meeting_speaker_id IN" in sql and "avg(p.heat)" in sql:
            return self.rows.get("heat", [])
        if "FROM meeting_speaker_position" in sql:
            return self.rows.get("shapes", [])
        if "data_center_comment_place" in sql:
            return self.rows.get("places", [])
        for col in ("concern_keys", "company_keys", "person_keys", "role_keys"):
            if f"unnest({col})" in sql:
                return self.rows.get(col, [])
        return self.rows.get("totals", [])


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

        monkeypatch.setattr(dcc, "get_db_pool", pool)
        app = FastAPI()
        app.include_router(dcc.router, prefix="/api")

        async def go():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
                return await client.get(PATH, params=params or {})

        return asyncio.run(go())

    return _get


ROWS = {
    "totals": [{"comments": 200, "governments": 12, "meetings": 30, "multi_concern": 150, "ai": 40}],
    "concern_keys": [{"key": "water_use", "n": 80}, {"key": "few_jobs", "n": 20}],
    "company_keys": [{"key": "google", "n": 9}],
    "person_keys": [{"key": "elon_musk", "n": 3}],
    "role_keys": [{"key": "resident", "n": 120}],
    "places": [{"key": "road", "n": 25}],
    "segmented": [{"n": 44}],
    "quarters": [{"quarter": "2026-Q1", "meetings": 10, "passages": 40, "comments": 70}],
}


def test_metrics_shape_and_stance_unknown(get) -> None:
    conn = _Conn(ROWS)
    r = get(conn, {"year": 2026, "state": "Illinois", "city": "Joliet"})
    assert r.status_code == 200
    body = r.json()
    assert body["year"] == "2026"
    assert body["scope"]["level"] == "city" and body["scope"]["state_code"] == "IL"
    assert (body["comments"], body["governments"], body["meetings"], body["meetings_segmented"]) == (200, 12, 30, 44)
    assert body["concerns"][0] == {"key": "water_use", "label": "Water use", "count": 80, "share": 0.4}
    assert body["multi_concern_share"] == 0.75
    assert body["ai_mentions"]["count"] == 40 and body["ai_mentions"]["share"] == 0.2
    assert body["companies"][0]["label"] == "Google / Alphabet"
    assert body["people"][0]["label"] == "Elon Musk"
    assert body["roles"][0]["label"] == "Resident"
    assert body["places"][0]["label"] == "Roads and routes"
    q = body["mentions_per_meeting_by_quarter"][0]
    assert q == {"quarter": "2026-Q1", "meetings_with_mention": 10, "mention_passages": 40,
                 "passages_per_meeting": 4.0, "comments": 70}
    # Stance-dependent numbers are unknown, with the reason, never 0.
    assert body["meetings_with_no_supporters"] is None and "phase 2" in body["no_supporters_reason"]
    assert body["positions"] is None
    sqls = " ".join(s for s, _ in conn.calls)
    assert "state_code = $" in sqls and "jurisdiction_name ILIKE $" in sqls


def test_no_comments_gives_null_shares(get) -> None:
    r = get(_Conn({"totals": [{"comments": 0, "governments": 0, "meetings": 0, "multi_concern": 0, "ai": 0}]}))
    body = r.json()
    assert body["comments"] == 0
    assert body["multi_concern_share"] is None and body["ai_mentions"] is None
    assert body["scope"]["level"] == "national"


def test_all_years_with_year_zero(get) -> None:
    conn = _Conn(ROWS)
    body = get(conn, {"year": 0}).json()
    assert body["year"] is None
    assert not any("make_date" in s for s, _ in conn.calls)


def test_missing_mart_is_503(get) -> None:
    r = get(_Conn(error=asyncpg.UndefinedTableError("relation \"data_center_comment\" does not exist")))
    assert r.status_code == 503


def test_heat_summary_needs_three_rated_speakers() -> None:
    assert dcc._heat_summary([{"rated": 2, "mean": 3.0, "peak": 4}]) is None
    assert dcc._heat_summary([{"rated": 0, "mean": None, "peak": None}]) is None
    h = dcc._heat_summary([{"rated": 3, "mean": 2.3333, "peak": 4}])
    assert h is not None and (h.speakers_rated, h.mean, h.peak) == (3, 2.33, 4)
