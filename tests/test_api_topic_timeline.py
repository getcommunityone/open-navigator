"""GET /api/topics/{topic}/timeline and /period-compare (#1140)."""
from __future__ import annotations

import asyncio
import re
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import yaml
from fastapi import FastAPI

from api.routes import topic_timeline as tt
from api.routes.data_centers import MENTION_LEAN_SQL


class _Conn:
    """Answers by matching a fragment of the SQL; records every call."""

    def __init__(self, fetch: dict[str, list[dict[str, Any]]], topic: dict | None, existing: set[str]):
        self.fetch_map = fetch
        self.topic = topic
        self.existing = existing
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        # The main FROM decides (a LATERAL subquery may name another table later in the SQL).
        hits = [(sql.index(frag), rows) for frag, rows in self.fetch_map.items() if frag in sql]
        if hits:
            return min(hits, key=lambda h: h[0])[1]
        return []

    async def fetchrow(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.topic

    async def fetchval(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return params[0] in self.existing


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

    monkeypatch.setattr(tt, "get_db_pool", pool)
    app = FastAPI()
    app.include_router(tt.router)

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(path, params=params)

    return asyncio.run(go())


ALL = {"recorded_meeting_year", "data_center_meeting_lean", "topic_meeting_lean", "topic_legislation_bill"}
DC_TOPIC = {"topic_id": 100001, "name": "Data centers"}


def test_timeline_years_are_strings_gaps_are_absent_and_share_is_real(monkeypatch) -> None:
    conn = _Conn(
        {
            "FROM data_center_meeting_mention m": [
                {"y": 2023, "meetings": 4, "passages": 4},
                {"y": 2025, "meetings": 4, "passages": 5},
                {"y": 2026, "meetings": 38, "passages": 237},
                {"y": None, "meetings": 1, "passages": 1},
            ],
            "FROM recorded_meeting_year r": [
                {"y": 2023, "recorded": 243},
                {"y": 2024, "recorded": 7},
                {"y": 2025, "recorded": 271},
                {"y": 2026, "recorded": 509},
            ],
            "FROM data_center_meeting_lean l": [
                {"meeting_date": date(2026, 3, 2), "outcome": "approved", "jurisdiction_name": "Abilene", "state_code": "TX",
                 "video_id": "v1", "title": "City Council", "video_url": "https://www.youtube.com/watch?v=v1"},
                {"meeting_date": date(2026, 4, 2), "outcome": "discussed_no_action", "jurisdiction_name": "Waco",
                 "state_code": "TX", "video_id": "v2", "title": None, "video_url": None},
            ],
        },
        DC_TOPIC,
        {"recorded_meeting_year", "data_center_meeting_lean"},
    )
    r = _get(monkeypatch, conn, "/api/topics/data-centers/timeline", {"state": "tx"})
    assert r.status_code == 200
    body = r.json()
    assert body["scope"] == {"level": "state", "state_code": "TX", "state": "Texas", "city": None}
    years = {y["year"]: y for y in body["years"]}
    assert list(years) == ["2023", "2024", "2025", "2026"]
    assert all(isinstance(y["year"], str) for y in body["years"])
    # 2024: recorded meetings but no data center meetings → a real 0 with its denominator, not invented passages.
    assert years["2024"] == {"year": "2024", "meetings": 0, "passages": 0, "all_recorded_meetings": 7, "share": 0.0}
    assert years["2026"]["share"] == round(38 / 509, 6)
    assert body["undated_meetings"] == 1
    assert body["total_meetings"] == 47 and body["total_passages"] == 247
    # Only real outcomes become milestones; the AI source is labelled; no bills relation → not available.
    assert [m["kind"] for m in body["milestones"]] == ["approved"]
    assert body["milestones"][0]["source"] == "ai_reading"
    assert body["milestones"][0]["date"] == "2026-03-02"
    assert body["bills_available"] is False and body["coverage_available"] is True
    years_sql = next(s for s, _ in conn.calls if "data_center_meeting_mention m WHERE" in s)
    assert "m.state_code = $1" in years_sql


def test_year_with_nothing_recorded_is_left_out(monkeypatch) -> None:
    conn = _Conn(
        {
            "FROM data_center_meeting_mention m": [{"y": 2021, "meetings": 3, "passages": 3}, {"y": 2023, "meetings": 1, "passages": 1}],
            "FROM recorded_meeting_year r": [{"y": 2021, "recorded": 485}, {"y": 2023, "recorded": 243}],
        },
        DC_TOPIC,
        {"recorded_meeting_year"},
    )
    body = _get(monkeypatch, conn, "/api/topics/data-centers/timeline").json()
    assert [y["year"] for y in body["years"]] == ["2021", "2023"]
    assert body["scope"]["level"] == "national"
    assert body["milestones"] == []


def test_other_topic_reads_topic_links_and_bills_when_present(monkeypatch) -> None:
    conn = _Conn(
        {
            "FROM topic_transcript_link l": [{"y": 2025, "meetings": 10, "passages": None}],
            "FROM recorded_meeting_year r": [{"y": 2025, "recorded": 100}],
            "FROM topic_meeting_lean l": [
                {"meeting_date": date(2025, 5, 1), "outcome": "denied", "jurisdiction_name": "Calgary", "state_code": "UT",
                 "video_id": "f1", "title": "Council", "video_url": None},
            ],
            "FROM topic_legislation_bill b": [
                {"latest_action_date": date(2025, 3, 1), "state_code": "UT", "state": "Utah", "identifier": "HB 81",
                 "title": "Fluoride Amendments", "url": "https://openstates.org/x"},
            ],
        },
        {"topic_id": 100002, "name": "Water fluoridation"},
        ALL,
    )
    body = _get(monkeypatch, conn, "/api/topics/water-fluoridation/timeline", {"state": "UT"}).json()
    assert body["years"] == [{"year": "2025", "meetings": 10, "passages": None, "all_recorded_meetings": 100, "share": 0.1}]
    assert [(m["kind"], m["source"]) for m in body["milestones"]] == [("bill_enacted", "record"), ("denied", "ai_reading")]
    assert body["milestones"][0]["title"] == "HB 81 · Fluoride Amendments"
    assert body["milestones"][1]["url"] == "https://www.youtube.com/watch?v=f1"
    assert body["bills_available"] is True
    bill_sql, bill_params = next((s, p) for s, p in conn.calls if "topic_legislation_bill b" in s)
    assert "status = 'enacted'" in bill_sql and bill_params == (100002, "UT")


def test_unknown_topic_is_404_and_bad_slug_never_reaches_sql(monkeypatch) -> None:
    conn = _Conn({}, None, ALL)
    assert _get(monkeypatch, conn, "/api/topics/no-such-topic/timeline").status_code == 404
    conn2 = _Conn({}, None, ALL)
    assert _get(monkeypatch, conn2, "/api/topics/DROP%20TABLE/timeline").status_code == 404
    assert conn2.calls == []


def test_db_failure_is_503(monkeypatch) -> None:
    class Boom(_Conn):
        async def fetch(self, sql, *p):
            raise RuntimeError("down")

    assert _get(monkeypatch, Boom({}, DC_TOPIC, ALL), "/api/topics/data-centers/timeline").status_code == 503


def test_period_compare_hides_thin_rows_and_documents_thresholds(monkeypatch) -> None:
    conn = _Conn(
        {
            "WITH t AS": [
                {"k": "TX", "t0": 4, "t1": 38, "r0": 271, "r1": 509},
                {"k": "VA", "t0": 10, "t1": 20, "r0": 100, "r1": 120},
                {"k": "WY", "t0": 1, "t1": 1, "r0": 5, "r1": 30},  # too few recorded in 2025 → hidden
                {"k": "OH", "t0": 0, "t1": 0, "r0": 200, "r1": 200},  # never came up → not a row, not counted as hidden
                {"k": "ME", "t0": 1, "t1": 1, "r0": 50, "r1": 50},  # 2 topic meetings < 3 → hidden
            ]
        },
        DC_TOPIC,
        {"recorded_meeting_year"},
    )
    r = _get(monkeypatch, conn, "/api/topics/data-centers/period-compare", {"from": 2025, "to": 2026})
    assert r.status_code == 200
    body = r.json()
    assert body["from_year"] == "2025" and body["to_year"] == "2026" and body["grain"] == "state"
    assert body["min_recorded_meetings"] == tt.MIN_RECORDED_MEETINGS
    assert body["min_topic_meetings"] == tt.MIN_TOPIC_MEETINGS
    assert body["hidden_rows"] == 2
    assert [row["label"] for row in body["rows"]] == ["Virginia", "Texas"]
    tx = body["rows"][1]
    assert tx["earlier_share"] == round(4 / 271, 6) and tx["later_share"] == round(38 / 509, 6)
    _sql, params = next((s, p) for s, p in conn.calls if "WITH t AS" in s)
    assert params[:2] == (2025, 2026)


def test_period_compare_state_scope_groups_by_town(monkeypatch) -> None:
    conn = _Conn({"WITH t AS": [{"k": "Abilene", "t0": 2, "t1": 6, "r0": 40, "r1": 60}]}, DC_TOPIC, {"recorded_meeting_year"})
    body = _get(monkeypatch, conn, "/api/topics/data-centers/period-compare", {"state": "TX", "from": 2025, "to": 2026}).json()
    assert body["grain"] == "place"
    assert body["rows"][0]["label"] == "Abilene"
    sql = next(s for s, _ in conn.calls if "WITH t AS" in s)
    assert "m.jurisdiction_name AS k" in sql and "r.jurisdiction_name AS k" in sql


def test_period_compare_rejects_reversed_years(monkeypatch) -> None:
    conn = _Conn({}, DC_TOPIC, ALL)
    assert _get(monkeypatch, conn, "/api/topics/data-centers/period-compare", {"from": 2026, "to": 2025}).status_code == 422


def test_lean_table_of_another_shape_drops_milestones_not_the_line(monkeypatch) -> None:
    import asyncpg

    class _BadLean(_Conn):
        async def fetch(self, sql: str, *params: Any):
            if "FROM topic_meeting_lean l" in sql:
                self.calls.append((sql, params))
                raise asyncpg.exceptions.UndefinedColumnError('column l.outcome does not exist')
            return await super().fetch(sql, *params)

    conn = _BadLean(
        {"FROM topic_transcript_link l": [{"y": 2025, "meetings": 4, "passages": None}]},
        {"topic_id": 100002, "name": "Water fluoridation"},
        {"topic_meeting_lean"},
    )
    r = _get(monkeypatch, conn, "/api/topics/water-fluoridation/timeline")
    assert r.status_code == 200
    body = r.json()
    assert body["years"][0]["meetings"] == 4
    assert body["milestones"] == []
    lean_sql, lean_params = next((s, p) for s, p in conn.calls if "FROM topic_meeting_lean l" in s)
    assert "l.topic_id = $1" in lean_sql and lean_params[0] == 100002


def _model_columns(schema_file: str) -> set[str]:
    root = Path(__file__).resolve().parents[1] / "dbt_project" / "models" / "marts" / schema_file
    doc = yaml.safe_load(root.read_text())
    return {c["name"] for m in doc["models"] for c in m.get("columns", [])}


def test_lean_queries_read_only_columns_in_the_model_contract() -> None:
    """#1207: a column that exists only in one warehouse (excluded_no_item) made production's milestone query fail and
    the track silently empty. Every ``l.<col>`` the milestone SQL reads must be in the model's schema.yml."""
    dc_cols = _model_columns("_schema_data_center_meeting_lean.yml")
    topic_cols = _model_columns("_schema_topic_meeting_lean.yml")
    for slug, cols, tid in (("data-centers", dc_cols, None), ("guns", topic_cols, 7)):
        for scope in (tt.build_scope(None, None), tt.build_scope("GA", "Atlanta")):
            sql, _ = tt.milestones_sql(slug, scope, tid)
            used = set(re.findall(r"\bl\.([a-z_]+)", sql))
            assert used and used <= cols, f"{slug}: {sorted(used - cols)} not in the model"
    assert "excluded_no_item" not in MENTION_LEAN_SQL
    for col in ("dc_outcome", "public_lean", "video_id"):
        assert col in dc_cols
