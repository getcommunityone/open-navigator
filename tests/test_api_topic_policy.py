"""GET /api/topics/{topic}/legislation, /positions and /local-actions (#1274)."""
from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg
import httpx
from fastapi import FastAPI

from api.routes import topic_policy


class _Conn:
    """Answers each query by the table it reads (first match wins); an Exception value is raised instead."""

    def __init__(self, by_table: dict[str, Any], states: int = 0):
        self.by_table = by_table
        self.states = states
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        for table, result in self.by_table.items():
            if f"FROM {table} " in sql:
                if isinstance(result, Exception):
                    raise result
                return result
        return []

    async def fetchrow(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return {"states": self.states}


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

    monkeypatch.setattr(topic_policy, "get_db_pool", pool)
    app = FastAPI()
    app.include_router(topic_policy.router)

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(path, params=params)

    return asyncio.run(go())


# --- legislation -------------------------------------------------------------------------------------------------


def _summary(**kw) -> dict[str, Any]:
    base = {"topic_id": 100002, "state_code": "KS", "state": "Kansas", "category": "ban", "year": 2026, "status": "pending", "bills": 1}
    base.update(kw)
    return base


_CATS = [
    {"topic_id": 100002, "category": "ban", "label": "Ban", "description": "Prohibits adding fluoride.", "display_order": 1},
    {"topic_id": 100002, "category": "restriction", "label": "Restriction", "description": "Notice.", "display_order": 2},
    {"topic_id": 100002, "category": "unclear", "label": "Direction not stated", "description": "x", "display_order": 5},
]


def test_legislation_summary_counts(monkeypatch) -> None:
    rows = [
        _summary(),
        _summary(state_code="KY", state="Kentucky", category="restriction", year=2025, status="failed", bills=2),
        _summary(state_code="KY", state="Kentucky", category="unclear", year=2026, status="passed_chamber"),
        _summary(state_code="UT", state=None, category="unclear", year=2025, status="enacted"),
        _summary(state_code="GA", state="GA", category="ban", year=None, status="failed"),
    ]
    conn = _Conn({"topic_legislation_category": _CATS, "topic_legislation_bill": rows})
    r = _get(monkeypatch, conn, "/api/topics/Water-Fluoridation/legislation")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True and body["topic_id"] == 100002
    assert body["total_bills"] == 6 and body["states_with_bills"] == 4
    assert body["status_counts"] == {"pending": 1, "failed": 3, "passed_chamber": 1, "enacted": 1}
    by = {(s["state_code"], s["status"]): s for s in body["summary"]}
    assert by[("UT", "enacted")]["state"] == "Utah"  # filled from the code when the row has none
    assert by[("GA", "failed")]["state"] == "Georgia"  # a row carrying the code as its name
    assert by[("KY", "failed")]["year"] == "2025"  # a bare year is a string on the wire
    assert by[("GA", "failed")]["year"] is None
    assert {c["category"]: c["bills"] for c in body["categories"]} == {"ban": 2, "restriction": 2, "unclear": 2}
    sql, params = next(c for c in conn.calls if "FROM topic_legislation_bill " in c[0])
    assert "GROUP BY" in sql and params == ("water-fluoridation",)


def _bill(**kw) -> dict[str, Any]:
    base = {
        "bill_id": "abc", "state": "Kansas", "identifier": "SB 333",
        "title": "Prohibiting the use of fluoride additives in public water supplies.", "session": "2025-2026",
        "year": 2026, "category": "ban", "status": "pending", "passed_a_chamber": False,
        "url": "https://openstates.org/ks/bills/2025-2026/SB333/", "introduced_date": date(2026, 1, 16),
        "last_action_date": date(2026, 1, 16), "last_action_description": "Referred to Committee", "matching": 3,
    }
    base.update(kw)
    return base


def test_state_bills_binds_filters_and_reports_matching(monkeypatch) -> None:
    rows = [_bill(), _bill(bill_id="def", identifier="HB 2", status="failed", passed_a_chamber=True, introduced_date=None)]
    conn = _Conn({"topic_legislation_bill": rows})
    r = _get(monkeypatch, conn, "/api/topics/water-fluoridation/legislation/ks", {"since_year": "2025", "category": "Ban", "limit": "2"})
    assert r.status_code == 200
    body = r.json()
    assert body["state_code"] == "KS" and body["state"] == "Kansas"
    assert body["matching"] == 3 and body["limit"] == 2 and len(body["bills"]) == 2
    assert body["since_year"] == "2025" and body["category"] == "ban"
    assert body["bills"][0]["year"] == "2026" and body["bills"][0]["introduced_date"] == "2026-01-16"
    assert body["bills"][1]["passed_a_chamber"] is True and body["bills"][1]["introduced_date"] is None
    _, params = conn.calls[0]
    assert params == ("water-fluoridation", "KS", 2025, "ban", 2)


def test_state_bills_empty_state(monkeypatch) -> None:
    body = _get(monkeypatch, _Conn({"topic_legislation_bill": []}), "/api/topics/water-fluoridation/legislation/WY").json()
    assert body["matching"] == 0 and body["bills"] == [] and body["state"] == "Wyoming"


def test_state_bills_rejects_bad_state_and_limit(monkeypatch) -> None:
    assert _get(monkeypatch, _Conn({}), "/api/topics/water-fluoridation/legislation/Kansas").status_code == 400
    assert _get(monkeypatch, _Conn({}), "/api/topics/water-fluoridation/legislation/KS", {"limit": "5000"}).status_code == 422


def test_legislation_missing_table_is_empty_200(monkeypatch) -> None:
    missing = asyncpg.exceptions.UndefinedTableError("relation does not exist")
    conn = _Conn({"topic_legislation_category": missing})
    r = _get(monkeypatch, conn, "/api/topics/water-fluoridation/legislation")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False and body["summary"] == [] and body["total_bills"] == 0


def test_legislation_db_error_is_503(monkeypatch) -> None:
    conn = _Conn({"topic_legislation_category": _CATS, "topic_legislation_bill": RuntimeError("boom")})
    assert _get(monkeypatch, conn, "/api/topics/water-fluoridation/legislation").status_code == 503


def test_top_status_order() -> None:
    assert topic_policy.top_status(["failed", "pending"]) == "pending"
    assert topic_policy.top_status(["failed"]) == "failed"
    assert topic_policy.top_status(["pending", "enacted", "passed_chamber"]) == "enacted"


# --- positions ---------------------------------------------------------------------------------------------------


def test_positions_five_scale_counts_and_keeps_zero_options(monkeypatch) -> None:
    rows = [
        {"position": "did_not_speak", "five": True, "meetings": 413, "states": 40},
        {"position": "oppose_local_choice", "five": True, "meetings": 74, "states": 20},
        {"position": "support_local_choice", "five": True, "meetings": 22, "states": 10},
        {"position": "oppose_ban_all", "five": True, "meetings": 9, "states": 5},
        {"position": "no_opinion", "five": True, "meetings": 7, "states": 4},
    ]
    conn = _Conn({"topic_meeting_lean": rows}, states=24)
    body = _get(monkeypatch, conn, "/api/topics/water-fluoridation/positions").json()
    assert body["scale"] == "five" and body["available"] is True
    assert body["read_meetings"] == 525 and body["did_not_speak"] == 413 and body["spoke_meetings"] == 112
    assert body["states"] == 24
    assert [(o["key"], o["meetings"]) for o in body["options"]] == [
        ("support_require_all", 0), ("support_local_choice", 22), ("no_opinion", 7),
        ("oppose_local_choice", 74), ("oppose_ban_all", 9),
    ]
    sql, params = next(c for c in conn.calls if "GROUP BY" in c[0])
    assert "excluded_no_item" in sql and params == ("water-fluoridation", None)


def test_positions_lean_scale_for_other_topics(monkeypatch) -> None:
    rows = [
        {"position": "mostly_opposed", "five": False, "meetings": 5, "states": 2},
        {"position": "mixed", "five": False, "meetings": 2, "states": 1},
        {"position": "did_not_speak", "five": False, "meetings": 9, "states": 3},
    ]
    body = _get(monkeypatch, _Conn({"topic_meeting_lean": rows}), "/api/topics/pickleball/positions", {"state": "ca"}).json()
    assert body["scale"] == "lean" and body["state_code"] == "CA"
    assert [(o["key"], o["meetings"]) for o in body["options"]] == [
        ("mostly_supportive", 0), ("mixed", 2), ("mostly_opposed", 5),
    ]


def test_positions_none_read_is_unavailable(monkeypatch) -> None:
    body = _get(monkeypatch, _Conn({"topic_meeting_lean": []}), "/api/topics/water-fluoridation/positions").json()
    assert body["available"] is False and body["scale"] is None and body["read_meetings"] == 0


# --- local actions -----------------------------------------------------------------------------------------------


def _action(**kw) -> dict[str, Any]:
    base = {
        "video_id": "v1", "jurisdiction_name": "Waxhaw", "state_code": "NC", "state": "North Carolina",
        "meeting_date": date(2026, 4, 14), "outcome_group": "blocked", "outcome": "voted_to_end_fluoridation",
        "outcome_p": Decimal("0.90"), "video_url": "https://www.youtube.com/watch?v=v1", "event_title": "Board meeting",
    }
    base.update(kw)
    return base


def test_local_actions_counts_by_state_and_year(monkeypatch) -> None:
    rows = [
        _action(),
        _action(video_id="v2", meeting_date=date(2026, 3, 10), outcome_group="tabled_or_deferred", outcome="tabled_or_deferred"),
        _action(video_id="v3", jurisdiction_name="Laredo", state_code="TX", state="Texas", meeting_date=date(2025, 8, 18),
                outcome_group="advanced", outcome="voted_to_keep_or_start"),
        _action(video_id="v4", jurisdiction_name="Bartow", state_code="FL", state="Florida", meeting_date=None,
                outcome_group="tabled_or_deferred", outcome="tabled_or_deferred", video_url=None),
    ]
    conn = _Conn({"topic_meeting_lean": rows})
    body = _get(monkeypatch, conn, "/api/topics/water-fluoridation/local-actions").json()
    assert body["total"] == 4 and body["undated"] == 1
    assert body["totals"] == {"advanced": 1, "blocked": 1, "tabled_or_deferred": 2}
    assert body["by_state"][0]["state_code"] == "NC"  # most actions first
    assert body["by_state"][0]["counts"] == {"advanced": 0, "blocked": 1, "tabled_or_deferred": 1}
    assert [y["year"] for y in body["by_year"]] == ["2025", "2026"]
    first = body["meetings"][0]
    assert first["outcome_p"] == 0.9 and first["url"] == "https://www.youtube.com/watch?v=v1"
    assert first["meeting_date"] == "2026-04-14"
    assert body["meetings"][3]["meeting_date"] is None


def test_local_actions_missing_table_is_empty_200(monkeypatch) -> None:
    conn = _Conn({"topic_meeting_lean": asyncpg.exceptions.UndefinedTableError("missing")})
    r = _get(monkeypatch, conn, "/api/topics/water-fluoridation/local-actions")
    assert r.status_code == 200 and r.json()["available"] is False and r.json()["meetings"] == []


def test_bad_topic_slug_is_400(monkeypatch) -> None:
    assert _get(monkeypatch, _Conn({}), "/api/topics/bad%20slug!/local-actions").status_code == 400


def test_local_actions_filters_false_hits_and_empty_is_unavailable(monkeypatch) -> None:
    conn = _Conn({"topic_meeting_lean": []})
    body = _get(monkeypatch, conn, "/api/topics/pickleball/local-actions").json()
    assert body["available"] is False and body["total"] == 0
    assert "excluded_no_item" in conn.calls[0][0]
