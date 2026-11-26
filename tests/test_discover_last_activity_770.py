"""#770: Discover Last activity reads channel_checked_at as well as discovered_at."""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock

from api.batch_jobs import batch_job_db as bj


def _conn(count: int):
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = (count,)
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value = MagicMock(__enter__=MagicMock(return_value=cur), __exit__=MagicMock(return_value=False))
    return conn, cur


def test_both_tables_with_the_column_use_greatest():
    conn, cur = _conn(2)
    assert bj.discover_last_at_sql(conn) == "GREATEST(discovered_at, channel_checked_at)"
    sql = cur.execute.call_args.args[0]
    assert "information_schema.columns" in sql and "ALTER" not in sql.upper()


def test_without_the_column_it_reads_discovered_at_only():
    conn, _ = _conn(1)
    assert bj.discover_last_at_sql(conn) == "discovered_at"


def test_a_failed_lookup_falls_back_to_discovered_at():
    conn, cur = _conn(2)
    cur.execute.side_effect = RuntimeError("permission denied")
    assert bj.discover_last_at_sql(conn) == "discovered_at"
    conn.rollback.assert_called()


def test_pipeline_stage_report_uses_it_for_the_discover_stage():
    src = inspect.getsource(bj.pipeline_stage_report)
    assert "discover_last_at_sql(conn)" in src
    assert "MAX(s.activity_at)" in src and "MAX(activity_at)" in src
