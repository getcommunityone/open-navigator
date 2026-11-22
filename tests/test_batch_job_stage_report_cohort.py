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
    return (
        st,
        vids_ok,
        0,
        vids_ok,
        0,
        vids_ok,
        0,
        ts,
        ts,
        ts,
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
        if "bronze_event_youtube" in sql and "GROUP BY" in sql:
            ok = self._filtered_yt_ok if cohort_filtered else self._national_yt_ok
            return [_yt_row("AL", ok), _yt_row("TX", 0 if cohort_filtered else 50)]
        if "int_events_union" in sql:
            ok = self._filtered_yt_ok if cohort_filtered else self._national_yt_ok
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


def _all_videos(report: dict) -> int:
    row = next(
        r for r in report["rows"] if r["scope"] == "ALL" and r["stage"] == "videos"
    )
    return int(row["done"])


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

    yt_calls = [
        c for c in cur.calls if "bronze_event_youtube y" in c[0] and "GROUP BY" in c[0]
    ]
    assert len(yt_calls) == 2
    assert tuple(set(yt_calls[1][1][0])) == tuple(set(dc_jids))
    assert yt_calls[1][1][0] == yt_calls[1][1][1]
    # state filter unused for data_centers
    assert yt_calls[1][1][2] is None

    assert _all_videos(filtered) <= _all_videos(national)
    assert set(filtered["states"]) <= {"AL", "TX"}


def test_pipeline_stage_report_priority_filters_by_state(monkeypatch: pytest.MonkeyPatch):
    cur = _RecordingCursor(filtered_yt_ok=7, national_yt_ok=200)
    with _mock_conn(cur) as conn:
        national = pipeline_stage_report(conn, cohort=None)
        filtered = pipeline_stage_report(conn, cohort="priority")

    yt_calls = [
        c for c in cur.calls if "bronze_event_youtube y" in c[0] and "GROUP BY" in c[0]
    ]
    assert len(yt_calls) == 2
    assert yt_calls[1][1][0] is None  # no jid filter
    assert set(yt_calls[1][1][2]) == set(PRIORITY_STATE_CODES)
    assert _all_videos(filtered) <= _all_videos(national)
