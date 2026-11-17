"""GET /api/policy-question: the moratorium outcome family (#483) and scoped counts (#499)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from api.routes import policy_questions

QID = "f7001f99695ccecb1e8df4ab0ee721fd"


class _Conn:
    """Fake asyncpg connection: returns canned rows, dispatched on the SQL it is sent."""

    def __init__(
        self,
        row: dict[str, Any] | None = None,
        rows: list[dict[str, Any]] | None = None,
        counts: dict[str, Any] | None = None,
        money: list[dict[str, Any]] | None = None,
        topic: dict[str, Any] | None = None,
        discussion: int = 0,
    ):
        self.row, self.rows = row, rows or []
        self.counts, self.money, self.topic, self.discussion = counts, money or [], topic, discussion
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def params_for(self, needle: str) -> tuple[Any, ...]:
        return next(p for sql, p in self.calls if needle in sql)

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if "item_interestingness" in sql:
            return self.money
        return self.rows

    async def fetchrow(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if "count(*) filter" in sql:
            return self.counts
        if "civicsearch_topic" in sql:
            return self.topic
        return self.row

    async def fetchval(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.discussion


class _Acquire:
    def __init__(self, conn: _Conn):
        self.conn = conn

    async def __aenter__(self) -> _Conn:
        return self.conn

    async def __aexit__(self, *_: Any) -> None:
        return None


class _Pool:
    def __init__(self, conn: _Conn):
        self.conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self.conn)


@pytest.fixture
def get(monkeypatch):
    def _get(conn: _Conn, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        async def pool():
            return _Pool(conn)

        monkeypatch.setattr(policy_questions, "get_db_pool", pool)
        app = FastAPI()
        app.include_router(policy_questions.router, prefix="/api")

        async def go():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
                return await c.get(path, params=params)

        return asyncio.run(go())

    return _get


def _detail_row(**overrides: Any) -> dict[str, Any]:
    row = dict(
        question_id=QID, canonical_text="Should we allow new data centers?", topic_code=None,
        primary_theme="economic_development", cofog_code=None, scope="local", status="active",
        first_seen=None, instances_total=4, decisions_total=4, bills_total=0, jurisdictions_total=4,
        jurisdictions_approved=1, states_total=2, approved_count=1, denied_count=1, deferred_count=0,
        moratorium_count=2, other_count=0, is_featured=True, display_order=1,
        money_total=0, money_share=0, talk_share=0,
    )
    row.update(overrides)
    return row


def test_list_projects_moratorium_count() -> None:
    assert "moratorium_count" in policy_questions._LIST_COLS


def test_summary_defaults_moratorium_count_to_zero() -> None:
    assert policy_questions.PolicyQuestionSummary(question_id=QID).moratorium_count == 0
    assert policy_questions.RollupOut().moratorium_count == 0


_COUNT_KEYS = (
    "instances_total", "decisions_total", "bills_total", "jurisdictions_total",
    "jurisdictions_approved", "states_total", "approved_count", "denied_count",
    "deferred_count", "moratorium_count", "other_count",
)


def _counts(**overrides: int) -> dict[str, int]:
    c = {k: v for k, v in _detail_row().items() if k in _COUNT_KEYS}
    c.update(overrides)
    return c


def test_detail_returns_moratorium_in_rollup_and_summary(get) -> None:
    body = get(_Conn(row=_detail_row(), counts=_counts()), f"/api/policy-question/{QID}").json()
    assert body["moratorium_count"] == 2
    assert body["rollup"]["moratorium_count"] == 2
    assert body["rollup"]["approved_count"] == 1 and body["rollup"]["denied_count"] == 1


def test_detail_without_moratorium_count_reads_zero(get) -> None:
    counts = _counts()
    counts.pop("moratorium_count")
    body = get(_Conn(row=_detail_row(), counts=counts), f"/api/policy-question/{QID}").json()
    assert body["moratorium_count"] == 0 and body["rollup"]["moratorium_count"] == 0


# ── #499: scoped header counts ──


def test_detail_without_filter_is_national(get) -> None:
    conn = _Conn(row=_detail_row(), counts=_counts())
    body = get(conn, f"/api/policy-question/{QID}").json()
    assert body["scope"] == {"level": "national", "state_code": None, "city": None}
    assert body["question_scope"] == "local"
    # National: the scope params are null, so every row counts.
    assert conn.params_for("count(*) filter") == (QID, None, None)


def test_detail_state_scope_recomputes_counts(get) -> None:
    # WA has no decisions: every count is the scoped zero, not the national rollup.
    conn = _Conn(row=_detail_row(), counts=_counts(**{k: 0 for k in _COUNT_KEYS}), discussion=3)
    body = get(conn, f"/api/policy-question/{QID}", {"state": "wa"}).json()
    assert body["scope"] == {"level": "state", "state_code": "WA", "city": None}
    assert conn.params_for("count(*) filter") == (QID, "WA", None)
    assert body["instances_total"] == 0 and body["jurisdictions_total"] == 0
    assert body["rollup"]["moratorium_count"] == 0 and body["rollup"]["approved_count"] == 0
    assert body["money_total"] == 0 and body["money_sources"] == []
    assert body["discussion_meeting_count"] == 3
    assert conn.params_for("question_transcript_link") == (QID, "WA", None)


def test_detail_full_state_name_and_city_scope(get) -> None:
    conn = _Conn(row=_detail_row(), counts=_counts())
    body = get(conn, f"/api/policy-question/{QID}", {"state": "Georgia", "city": " DeKalb "}).json()
    assert body["scope"] == {"level": "city", "state_code": "GA", "city": "DeKalb"}
    assert conn.params_for("count(*) filter") == (QID, "GA", "%DeKalb%")


def test_detail_counts_come_from_outcome_family_column() -> None:
    sql = policy_questions._SCOPED_COUNTS_SQL
    for fam in ("approved", "denied", "deferred", "moratorium", "other"):
        assert f"qi.outcome_family = '{fam}'" in sql
    assert "public.question_instance" in sql


def test_detail_money_total_is_sum_of_listed_sources(get) -> None:
    money = [dict(event_decision_id="d1", title="Data Center Regulations and Baseline Assessment Deferred",
                  jurisdiction_name="DeKalb County", state_code="GA", outcome_family="deferred",
                  occurred_at=None, net_dollar_impact=15000.0)]
    body = get(_Conn(row=_detail_row(money_total=99999), counts=_counts(), money=money),
               f"/api/policy-question/{QID}").json()
    # Traceable: the figure is the sum of the rows returned with it, not the mart constant.
    assert body["money_total"] == 15000
    assert body["money_sources"][0]["event_decision_id"] == "d1"


def test_detail_links_topic_named_like_an_alias(get) -> None:
    body = get(_Conn(row=_detail_row(), counts=_counts(), topic={"topic_id": 100001, "topic_name": "Data centers"}),
               f"/api/policy-question/{QID}").json()
    assert body["topic_id"] == 100001 and body["topic_name"] == "Data centers"


def test_instances_filter_by_scope_and_outcome(get) -> None:
    conn = _Conn(rows=[dict(instance_id="i1", source_type="local_decision", source_id="d1",
                            state_code="AL", outcome_normalized="moratorium", outcome_family="moratorium")])
    body = get(conn, f"/api/policy-question/{QID}/instances", {"state": "AL", "outcome": "moratorium"}).json()
    assert body[0]["outcome_family"] == "moratorium"
    sql, params = conn.calls[0]
    assert "qi.outcome_family = $4" in sql
    assert params[:4] == (QID, "AL", None, "moratorium")


def test_instances_reject_unknown_outcome(get) -> None:
    assert get(_Conn(), f"/api/policy-question/{QID}/instances", {"outcome": "won"}).status_code == 422


# ── #499: meetings carry their evidence, newest first ──


def test_meetings_carry_evidence_and_jump_url(get) -> None:
    rows = [dict(video_id="abc", event_title="City Council", event_date="2026-11-02", state_code="WA",
                 video_url="https://www.youtube.com/watch?v=abc", n_alias_hits=1,
                 evidence="a new <mark>data</mark> <mark>center</mark> proposal", start_seconds=754.2),
            dict(video_id="def", event_title="Planning", event_date="2026-10-01", state_code="WA",
                 video_url="https://www.youtube.com/watch?v=def", n_alias_hits=2,
                 evidence="<mark>hyperscale</mark> campus", start_seconds=None)]
    conn = _Conn(rows=rows)
    body = get(conn, f"/api/policy-question/{QID}/meetings", {"state": "WA", "limit": 2, "offset": 2}).json()
    assert body[0]["evidence"].startswith("a new <mark>data</mark>")
    assert body[0]["jump_url"] == "https://www.youtube.com/watch?v=abc&t=754s"
    assert body[1]["jump_url"] is None  # untimed transcript: no fake jump time
    assert conn.calls[0][1] == (QID, "WA", None, 2, 2)


def test_meetings_sort_newest_first_with_future_dates_last() -> None:
    sql = policy_questions._MEETINGS_SQL
    order = sql[sql.index("order by"):]
    assert order.index("l.event_date > current_date") < order.index("l.event_date desc") < order.index("n_alias_hits desc")


def test_list_passes_moratorium_count_through(get) -> None:
    rows = [dict(question_id=QID, canonical_text="Should we allow new data centers?", moratorium_count=5,
                 instances_total=25, jurisdictions_total=15, jurisdictions_approved=3,
                 is_featured=True, display_order=1)]
    body = get(_Conn(rows=rows), "/api/policy-question/", {"featured": "true"}).json()
    assert body[0]["moratorium_count"] == 5
