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


def test_ensure_columns_idempotent():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    ensure_bronze_youtube_transcript_columns(conn)
    assert cur.execute.call_count == 2
    conn.commit.assert_called_once()
