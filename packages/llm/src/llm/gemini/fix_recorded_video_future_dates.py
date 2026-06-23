#!/usr/bin/env python3
"""Batch-fix future meeting_date values on recorded-video event_meeting rows."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

import psycopg2
from loguru import logger
from psycopg2.extras import RealDictCursor

from llm.gemini.meeting_date_qa import (
    is_future_meeting_date,
    suggest_recorded_video_meeting_date,
)

_REPO = Path(__file__).resolve().parents[5]

# Hand-verified corrections when title + meeting_id are also wrong.
_MANUAL_CORRECTIONS: dict[int, tuple[str, str]] = {
    4906: ("2026-04-27", "title year typo (2028→2026)"),
    4957: ("2025-11-25", "transcript opening: November 25th, 2025"),
    4820: ("2025-12-17", "transcript opening: December 17th (2025 session)"),
    4077: ("2026-05-26", "promo video; capped to transcript_download_at"),
}


def _database_url() -> str:
    return os.getenv(
        "NEON_DATABASE_URL_DEV",
        "postgresql://postgres:%s@localhost:5433/open_navigator"
        % os.getenv("POSTGRES_PASSWORD", "password"),
    )


def _load_transcript_text(conn, video_id: str) -> str:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT transcript_file_path, policy_analysis_path
            FROM bronze.bronze_event_youtube
            WHERE video_id = %s
            """,
            (video_id,),
        )
        row = cur.fetchone()
    if not row:
        return ""
    for rel in (row.get("transcript_file_path"), row.get("policy_analysis_path")):
        if not rel:
            continue
        path = _REPO / str(rel)
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            yt = data.get("youtube") if isinstance(data.get("youtube"), dict) else {}
            text = yt.get("raw_text") if isinstance(yt, dict) else None
            if text:
                return str(text)
    return ""


def _resolve_correction(
    row: dict[str, Any],
    *,
    transcript_text: str,
    as_of: date,
) -> Optional[tuple[str, str]]:
    event_meeting_id = int(row["event_meeting_id"])
    if event_meeting_id in _MANUAL_CORRECTIONS:
        return _MANUAL_CORRECTIONS[event_meeting_id]

    suggested = suggest_recorded_video_meeting_date(
        title=str(row.get("title") or row.get("body_name") or ""),
        meeting_id=str(row.get("meeting_id") or ""),
        transcript_text=transcript_text,
        as_of=as_of,
    )
    if suggested:
        return suggested, "auto (title/meeting_id/transcript)"
    return None


def _patch_analysis_json(analysis: dict[str, Any], new_date: str) -> dict[str, Any]:
    out = json.loads(json.dumps(analysis))
    meeting = out.get("meeting")
    if isinstance(meeting, dict):
        meeting["meeting_date"] = new_date
    if out.get("event_date"):
        out["event_date"] = new_date
    notes = out.setdefault("_meeting_date_qa", [])
    if isinstance(notes, list):
        notes.append(f"batch_fix_recorded_video_future_dates → {new_date}")
    return out


def fix_rows(*, dry_run: bool = False, as_of: Optional[date] = None) -> int:
    ref = as_of or datetime.now(timezone.utc).date()
    conn = psycopg2.connect(_database_url())
    fixed = 0
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT em.event_meeting_id,
                       em.video_id,
                       em.meeting_id,
                       em.meeting_date,
                       em.body_name,
                       yt.title,
                       yt.transcript_download_at
                FROM gold.event_meeting em
                LEFT JOIN bronze.bronze_event_youtube yt USING (video_id)
                WHERE em.video_id IS NOT NULL
                  AND em.meeting_date ~ '^\\d{4}-\\d{2}-\\d{2}$'
                  AND em.meeting_date::date > %s::date
                ORDER BY em.event_meeting_id
                """,
                (ref.isoformat(),),
            )
            rows = cur.fetchall()

        for row in rows:
            current = str(row["meeting_date"])[:10]
            transcript = _load_transcript_text(conn, row["video_id"])
            resolved = _resolve_correction(row, transcript_text=transcript, as_of=ref)
            if not resolved:
                logger.warning(
                    "No correction for event_meeting_id={} video_id={} date={}",
                    row["event_meeting_id"],
                    row["video_id"],
                    current,
                )
                continue
            new_date, reason = resolved
            if not is_future_meeting_date(new_date, as_of=ref):
                logger.info(
                    "{} ({}) {} → {} ({})",
                    row["event_meeting_id"],
                    row["video_id"],
                    current,
                    new_date,
                    reason,
                )
            else:
                logger.warning(
                    "Skipping {} — proposed {} is still future",
                    row["event_meeting_id"],
                    new_date,
                )
                continue

            if dry_run:
                fixed += 1
                continue

            event_meeting_id = int(row["event_meeting_id"])
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "UPDATE gold.event_meeting SET meeting_date = %s WHERE event_meeting_id = %s",
                    (new_date, event_meeting_id),
                )
                cur.execute(
                    """
                    UPDATE bronze.bronze_meetings_from_ai
                    SET meeting_date = %s
                    WHERE source_event_id = %s
                    """,
                    (new_date, event_meeting_id),
                )
                cur.execute(
                    """
                    UPDATE bronze.bronze_event_youtube
                    SET event_date = %s::date
                    WHERE video_id = %s
                    """,
                    (new_date, row["video_id"]),
                )
                cur.execute(
                    """
                    SELECT structured_analysis
                    FROM bronze.bronze_events_analysis_ai
                    WHERE id = %s
                    """,
                    (event_meeting_id,),
                )
                analysis_row = cur.fetchone()
                if analysis_row and isinstance(analysis_row["structured_analysis"], dict):
                    patched = _patch_analysis_json(analysis_row["structured_analysis"], new_date)
                    cur.execute(
                        """
                        UPDATE bronze.bronze_events_analysis_ai
                        SET structured_analysis = %s::jsonb
                        WHERE id = %s
                        """,
                        (json.dumps(patched), event_meeting_id),
                    )
            conn.commit()
            fixed += 1
    finally:
        conn.close()

    logger.success("Fixed {} recorded-video future date(s)", fixed)
    return fixed


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    fix_rows(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
