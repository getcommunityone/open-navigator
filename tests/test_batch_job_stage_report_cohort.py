"""Stage report cohort filters (data_centers jurisdiction ids, priority states)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple
from unittest.mock import MagicMock

import pytest

from api.batch_jobs.batch_job_db import pipeline_stage_report
from api.batch_jobs.cohorts import PRIORITY_STATE_CODES


def _yt_row(st: str, vids_ok: int) -> Tuple[Any, ...]:
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # Matches pipeline_stage_report SELECT (#755 light + full stamps).
    return (
        st,
        vids_ok,  # vids_ok
        0,  # vids_fail
        vids_ok,  # analyses_light
        0,  # analysis_light_err
        vids_ok,  # reports_light
        0,  # report_light_err
        0,  # analyses_full
        0,  # analysis_full_err
        0,  # reports_full
        0,  # report_full_err
        ts,  # last_video
        ts,  # last_analysis_light
        ts,  # last_report_light
        None,  # last_analysis_full
        None,  # last_report_full
    )


def _params_filtered(params: Optional[tuple]) -> bool:
    """True when either jurisdiction_id or state_code filter arrays are set."""
    if params is None:
        return False
    # (jf_a, jf_b, sf_a, sf_b) for youtube / transcripts; discover varies.
    return any(p is not None for p in params)


class _RecordingCursor:
    def __init__(self, *, filtered_yt_ok: int, national_yt_ok: int) -> None:
        self.calls: List[Tuple[str, Optional[tuple]]] = []
        self._filtered_yt_ok = filtered_yt_ok
        self._national_yt_ok = national_yt_ok

    def execute(self, sql: str, params: Optional[tuple] = None) -> None:
        self.calls.append((sql, params))

    def fetchall(self) -> list:
        sql, params = self.calls[-1]
        cohort_filtered = _params_filtered(params)
        ok = self._filtered_yt_ok if cohort_filtered else self._national_yt_ok
        # Videos stage aggregate (stamps).
        if "AS vids_ok" in sql and "bronze_event_youtube" in sql:
            return [_yt_row("AL", ok), _yt_row("TX", 0 if cohort_filtered else 50)]
        # Transcripts stage over the same attempted YouTube set (#683).
        if "bronze_event_youtube_transcript" in sql and "bronze_event_youtube" in sql:
            return [
                ("AL", max(ok, 1), ok, ""),
                ("TX", 0 if cohort_filtered else 50, 0 if cohort_filtered else 40, ""),
            ]
        if "discover" in sql or "counties_scraped" in sql or "int_jurisdictions" in sql:
            return []
        if "percentile_cont" in sql:
            return [(60.0, "/p", datetime.now(timezone.utc), 0.0)]
        return []

    def __enter__(self) -> "_RecordingCursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None


@contextmanager
def _mock_conn(cursor: _RecordingCursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    yield conn


def _all_stage(report: dict, stage: str) -> tuple[int, int]:
    row = next(
        r for r in report["rows"] if r["scope"] == "ALL" and r["stage"] == stage
    )
    return int(row["done"]), int(row["total"])


def test_pipeline_stage_report_data_centers_smaller_all_rollup(monkeypatch: pytest.MonkeyPatch):
    dc_jids = ["county_01001", "municipality_0107000"]
    monkeypatch.setattr(
        "api.batch_jobs.cohorts.data_center_jurisdiction_ids",
        lambda _conn: set(dc_jids),
    )

    cur = _RecordingCursor(filtered_yt_ok=5, national_yt_ok=200)
    with _mock_conn(cur) as conn:
        national = pipeline_stage_report(conn, cohort=None)
        filtered = pipeline_stage_report(conn, cohort="data_centers")

    yt_stamp_calls = [
        c
        for c in cur.calls
        if "AS vids_ok" in c[0] and "bronze_event_youtube" in c[0]
    ]
    assert len(yt_stamp_calls) == 2
    assert tuple(set(yt_stamp_calls[1][1][0])) == tuple(set(dc_jids))
    assert yt_stamp_calls[1][1][0] == yt_stamp_calls[1][1][1]
    # state filter unused for data_centers
    assert yt_stamp_calls[1][1][2] is None

    vid_f, tot_f = _all_stage(filtered, "videos")
    vid_n, tot_n = _all_stage(national, "videos")
    assert vid_f <= vid_n
    tx_f, tx_tot_f = _all_stage(filtered, "transcripts")
    tx_n, tx_tot_n = _all_stage(national, "transcripts")
    # Transcripts share the YouTube attempted population — not the events union.
    assert tx_tot_f <= tot_f or tx_tot_f == tx_f  # attempted-sized (or clamp)
    assert tx_tot_f < tx_tot_n or tx_f <= tx_n
    assert set(filtered["states"]) <= {"AL", "TX"}


def test_pipeline_stage_report_priority_filters_by_state(monkeypatch: pytest.MonkeyPatch):
    cur = _RecordingCursor(filtered_yt_ok=7, national_yt_ok=200)
    with _mock_conn(cur) as conn:
        national = pipeline_stage_report(conn, cohort=None)
        filtered = pipeline_stage_report(conn, cohort="priority")

    yt_stamp_calls = [
        c
        for c in cur.calls
        if "AS vids_ok" in c[0] and "bronze_event_youtube" in c[0]
    ]
    assert len(yt_stamp_calls) == 2
    assert yt_stamp_calls[1][1][0] is None  # no jid filter
    assert set(yt_stamp_calls[1][1][2]) == set(PRIORITY_STATE_CODES)
    assert _all_stage(filtered, "videos")[0] <= _all_stage(national, "videos")[0]


def test_transcripts_sql_uses_youtube_not_events_union(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "api.batch_jobs.cohorts.data_center_jurisdiction_ids",
        lambda _conn: {"county_01001"},
    )
    cur = _RecordingCursor(filtered_yt_ok=3, national_yt_ok=100)
    with _mock_conn(cur) as conn:
        pipeline_stage_report(conn, cohort="data_centers")

    tx_sql = [
        c[0]
        for c in cur.calls
        if "bronze_event_youtube_transcript" in c[0]
    ]
    assert tx_sql, "expected a transcripts query"
    assert all("int_events_union" not in s for s in tx_sql)
    assert any("transcript_download_at IS NOT NULL" in s for s in tx_sql)
