"""Tests for bronze_event_youtube transcript download tracking."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from scrapers.youtube.bronze_transcript_tracking import (
    ensure_bronze_youtube_transcript_columns,
    record_transcript_download_error,
    record_transcript_download_success,
    transcript_path_for_storage,
)


def test_transcript_path_for_storage_relative():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        f = repo / "data" / "cache" / "test.json"
        f.parent.mkdir(parents=True)
        f.write_text("{}", encoding="utf-8")
        # Patch _REPO_ROOT by using path under a fake repo root
        import scrapers.youtube.bronze_transcript_tracking as mod

        old = mod._REPO_ROOT
        mod._REPO_ROOT = repo
        try:
            assert transcript_path_for_storage(f) == "data/cache/test.json"
        finally:
            mod._REPO_ROOT = old


def test_record_success_and_error_sql():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur

    record_transcript_download_success(
        conn, "abc123", Path("/tmp/x.json"), commit=False
    )
    assert cur.execute.call_count == 1
    sql = cur.execute.call_args[0][0]
    assert "transcript_download_at" in sql
    assert "transcript_file_error = NULL" in sql
    assert "transcript_download_attempts" in sql

    record_transcript_download_error(conn, "abc123", "no captions", commit=False)
    sql2 = cur.execute.call_args[0][0]
    assert "transcript_file_error" in sql2
    assert "transcript_file_path = NULL" in sql2
    assert "transcript_download_attempts = COALESCE" in sql2


def test_ensure_columns_runs_no_ddl_when_present(monkeypatch):
    # #534: no ALTER when the columns and index already exist, so a loader never
    # queues an ACCESS EXCLUSIVE lock behind a long read.
    import scrapers.youtube.schema_guard as sg

    monkeypatch.setattr(sg, "missing_columns", lambda *a, **k: [])
    monkeypatch.setattr(sg, "index_exists", lambda *a, **k: True)
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    ensure_bronze_youtube_transcript_columns(conn)
    assert not any("ALTER TABLE" in str(c.args[0]) for c in cur.execute.call_args_list)
    conn.commit.assert_called_once()


def test_ensure_columns_adds_missing_columns_once(monkeypatch):
    import scrapers.youtube.schema_guard as sg

    monkeypatch.setattr(sg, "missing_columns", lambda *a, **k: ["transcript_download_at"])
    monkeypatch.setattr(sg, "index_exists", lambda *a, **k: False)
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    ensure_bronze_youtube_transcript_columns(conn)
    sqls = [str(c.args[0]) for c in cur.execute.call_args_list]
    assert sum("ALTER TABLE bronze.bronze_event_youtube" in q for q in sqls) == 1
    assert sum("CREATE INDEX IF NOT EXISTS idx_bronze_youtube_transcript_downloaded" in q for q in sqls) == 1
    conn.commit.assert_called_once()
