"""promote_to_c1_event copies the healed jurisdiction_name, not the raw bronze one (#501).

Raw bronze can carry the jurisdiction id as the name (``chilton_01021``); the dbt
staging view resolves it. civic_event feeds event_meeting and every event_* mart.
"""

from __future__ import annotations

from ingestion.youtube import promote_to_c1_event as promote


class _Cursor:
    def __init__(self, sink):
        self.sink = sink

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, args):
        self.sink.append((sql, args))

    def fetchall(self):
        return []


class _Conn:
    def __init__(self):
        self.calls: list = []

    def cursor(self, cursor_factory=None):
        return _Cursor(self.calls)


def test_name_comes_from_staging_and_where_is_qualified():
    conn = _Conn()
    assert promote.load_youtube_rows(conn, ("AL",), all_dated=False) == []
    sql, args = conn.calls[0]
    assert "LEFT JOIN staging.stg_youtube__event s ON s.video_id = y.video_id" in sql
    assert "s.jurisdiction_name" in sql
    assert "y.jurisdiction_name" not in sql
    assert "y.state_code = ANY(%s)" in sql and "y.policy_analysis_at IS NOT NULL" in sql
    assert args == [["AL"]]
