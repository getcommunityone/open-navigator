"""
Update ``bronze.bronze_events_youtube`` transcript download columns after caption fetch.

Mirrors audio tracking (``006_add_audio_tracking_fields.sql`` / ``download_audio_to_drive.py``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MAX_ERROR_LEN = 2000


def transcript_path_for_storage(file_path: Union[str, Path]) -> str:
    """Store repo-relative POSIX path when under the repo root."""
    p = Path(file_path).resolve()
    try:
        rel = p.relative_to(_REPO_ROOT)
        return rel.as_posix()
    except ValueError:
        return p.as_posix()


def transcript_file_size_bytes(file_path: Union[str, Path]) -> int:
    p = Path(file_path)
    if not p.is_file():
        return 0
    return int(p.stat().st_size)


def ensure_bronze_youtube_transcript_columns(conn: Any) -> None:
    """Apply migration 072 columns if missing (idempotent)."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            ALTER TABLE bronze.bronze_events_youtube
            ADD COLUMN IF NOT EXISTS transcript_download_at TIMESTAMP,
            ADD COLUMN IF NOT EXISTS transcript_file_path VARCHAR(500),
            ADD COLUMN IF NOT EXISTS transcript_file_size BIGINT,
            ADD COLUMN IF NOT EXISTS transcript_file_error TEXT,
            ADD COLUMN IF NOT EXISTS transcript_download_attempts INTEGER NOT NULL DEFAULT 0
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_bronze_youtube_transcript_downloaded
            ON bronze.bronze_events_youtube (transcript_download_at)
            WHERE transcript_download_at IS NOT NULL
            """
        )
    finally:
        cur.close()
    conn.commit()


def record_transcript_download_success(
    conn: Any,
    video_id: str,
    file_path: Optional[Union[str, Path]],
    *,
    commit: bool = True,
) -> None:
    """Mark a successful transcript download on ``bronze_events_youtube``."""
    vid = (video_id or "").strip()
    if not vid:
        return
    rel_path: Optional[str] = None
    size_bytes: Optional[int] = None
    if file_path:
        rel_path = transcript_path_for_storage(file_path)
        size_bytes = transcript_file_size_bytes(file_path)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE bronze.bronze_events_youtube
            SET
                transcript_download_at = CURRENT_TIMESTAMP,
                transcript_file_path = %s,
                transcript_file_size = %s,
                transcript_file_error = NULL,
                transcript_download_attempts = COALESCE(transcript_download_attempts, 0) + 1
            WHERE video_id = %s
            """,
            (rel_path, size_bytes, vid),
        )
    finally:
        cur.close()
    if commit:
        conn.commit()


def record_transcript_download_error(
    conn: Any,
    video_id: str,
    error: str,
    *,
    commit: bool = True,
) -> None:
    """Record caption download failure (clears path/size)."""
    vid = (video_id or "").strip()
    if not vid:
        return
    msg = (error or "unknown error").strip()[:_MAX_ERROR_LEN]
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE bronze.bronze_events_youtube
            SET
                transcript_download_at = CURRENT_TIMESTAMP,
                transcript_file_path = NULL,
                transcript_file_size = NULL,
                transcript_file_error = %s,
                transcript_download_attempts = COALESCE(transcript_download_attempts, 0) + 1
            WHERE video_id = %s
            """,
            (msg, vid),
        )
    finally:
        cur.close()
    if commit:
        conn.commit()
