"""#800: the failed-items grid for every stage.

Pure checks always run. The SQL checks run against a real Postgres only when TEST_PG_DSN is set
(they build a throwaway bronze.bronze_event_youtube); otherwise they are skipped.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "api" / "batch_jobs" / "failure_reasons.py"
_spec = importlib.util.spec_from_file_location("failure_reasons_grid_under_test", _PATH)
fr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fr)


def test_every_grid_stage_has_its_own_error_column_and_a_log_hint():
    assert fr.STAGE_ERROR_COLUMN == {
        "videos": "transcript_file_error",
        "transcripts": "transcript_file_error",
        "analyses_light": "policy_analysis_error",
        "reports_light": "policy_report_error",
        "analyses_full": "policy_analysis_full_error",
        "reports_full": "policy_report_full_error",
    }
    assert set(fr.STAGE_WHERE_TO_LOOK) == set(fr.STAGE_ERROR_COLUMN)


def test_sort_allow_list_matches_the_contract():
    assert set(fr.SORT_KEYS) == {
        "video_id", "title", "state_code", "jurisdiction_name", "error",
        "last_updated", "event_date", "meeting_type",
    }
    sortable = {c["key"] for c in fr.GRID_COLUMNS if c["sortable"]}
    assert sortable <= set(fr.SORT_KEYS)


class _NoDb:
    def cursor(self):  # pragma: no cover - must never be reached
        raise AssertionError("validation must fail before any SQL")


@pytest.mark.parametrize(
    "kw",
    [
        {"stage": "nope"},
        {"stage": "videos", "sort": "title; drop table x"},
        {"stage": "videos", "group": "not_a_group"},
    ],
)
def test_bad_stage_sort_or_group_is_rejected_before_sql(kw):
    with pytest.raises(ValueError):
        fr.failure_grid(_NoDb(), cohort=None, state=None, **kw)


DSN = os.environ.get("TEST_PG_DSN")


@pytest.fixture()
def conn(monkeypatch):
    if not DSN:
        pytest.skip("TEST_PG_DSN not set")
    import psycopg2

    c = psycopg2.connect(DSN)
    cur = c.cursor()
    cur.execute("DROP SCHEMA IF EXISTS bronze CASCADE; CREATE SCHEMA bronze")
    cur.execute(
        """CREATE TABLE bronze.bronze_event_youtube (
            event_id text, video_id text, jurisdiction_id text, jurisdiction_name text, state_code text,
            channel_id text, channel_url text, title text, event_date date, meeting_type text,
            last_updated timestamp, transcript_file_error text, policy_analysis_error text,
            policy_report_error text, policy_analysis_full_error text, policy_report_full_error text)"""
    )
    rows = [
        ("e1", "aaaaaaaaaa1", "j1", "Tuscaloosa", "AL", "c1", "u", "Council meeting", "2026-01-02", "City Council",
         "2026-02-01", "Sign in to confirm you're not a bot", None, None, None, None),
        ("e2", "aaaaaaaaaa2", "j2", "Mobile", "AL", "c2", "u", "Budget hearing", "2026-01-05", "Budget",
         "2026-02-03", "HTTP Error 429: Too Many Requests", "model returned no JSON", None, None, None),
        ("e3", "aaaaaaaaaa3", "j3", "Austin", "TX", "c3", "u", "Zoning", "2026-01-09", "Planning",
         "2026-02-02", "Subtitles are disabled for this video", None, "report failed", None, None),
        ("e4", "aaaaaaaaaa4", "j3", "Austin", "TX", "c3", "u", "Fine one", "2026-01-10", "Planning",
         "2026-02-04", None, None, None, None, None),
    ]
    cur.executemany("INSERT INTO bronze.bronze_event_youtube VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", rows)
    c.commit()
    monkeypatch.setattr(fr, "_scope_params", lambda cohort, state, conn: (None, None, (state or "").upper() or None))
    yield c
    c.close()


def _grid(conn, **kw):
    kw.setdefault("stage", "transcripts")
    return fr.failure_grid(conn, cohort=None, state=kw.pop("state", None), **kw)


def test_total_equals_the_stage_report_failed_count(conn):
    cur = conn.cursor()
    for stage, col in fr.STAGE_ERROR_COLUMN.items():
        cur.execute(f"SELECT COUNT(*) FROM bronze.bronze_event_youtube WHERE {col} IS NOT NULL")
        assert _grid(conn, stage=stage)["total"] == cur.fetchone()[0], stage


def test_other_stages_read_their_own_error_column(conn):
    out = _grid(conn, stage="analyses_light")
    assert out["total"] == 1 and out["rows"][0]["error"] == "model returned no JSON"


def test_sort_both_ways_and_paging(conn):
    asc = [r["video_id"] for r in _grid(conn, sort="video_id", direction="asc")["rows"]]
    desc = [r["video_id"] for r in _grid(conn, sort="video_id", direction="desc")["rows"]]
    assert asc == sorted(asc) and desc == asc[::-1]
    page2 = _grid(conn, sort="video_id", direction="asc", limit=1, offset=1)
    assert page2["total"] == 3 and [r["video_id"] for r in page2["rows"]] == [asc[1]]


def test_search_state_and_group_filters(conn):
    assert _grid(conn, q="BUDGET")["total"] == 1
    assert _grid(conn, q="tuscaloosa")["rows"][0]["video_id"] == "aaaaaaaaaa1"
    assert _grid(conn, q="100%")["total"] == 0  # % is plain text, not a wildcard
    assert _grid(conn, state="tx")["total"] == 1
    g = _grid(conn, group="rate_limit")
    assert g["total"] == 1 and g["rows"][0]["group"] == "rate_limit" and g["rows"][0]["retryable"]
    assert _grid(conn, group="no_captions")["rows"][0]["retryable"] is False


def test_rows_carry_troubleshooting_detail(conn):
    r = _grid(conn, q="council")["rows"][0]
    assert r["channel_id"] == "c1" and r["event_date"] == "2026-01-02" and r["meeting_type"] == "City Council"
    assert r["group_label"] and r["advice"] and r["last_updated"].startswith("2026-02-01")
